# =====================================================================
# File: app.py
# Version: v4.4
# Date: 2026-10-28
# Description: Flask backend for Clickbait Buster & Article Skimmer v4.4.
#              Supports floating GPU monitoring, persistent link history (history.json),
#              multi-site round-robin aggregation, ephemeral text mode, and port 5001.
# =====================================================================

import os
import json
import time
import shutil
import subprocess
import requests
from flask import Flask, render_template, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor
from itertools import zip_longest

app = Flask(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"
OLLAMA_MODEL = "qwen3:8b"
HISTORY_FILE = "history.json"

def load_history():
    """Loads saved link history from local JSON file in the same folder."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"single": [], "batch": [], "aggregator": []}
    return {"single": [], "batch": [], "aggregator": []}

def save_history_item(category, url):
    """Appends a new URL to history and persists to history.json."""
    if not url or not url.strip():
        return
    url = url.strip()
    history = load_history()
    if category not in history:
        history[category] = []
    if url not in history[category]:
        history[category].insert(0, url)
        history[category] = history[category][:30]
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            print(f"Error saving history: {e}")

def is_ollama_running():
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def ensure_ollama_running():
    if is_ollama_running():
        return True
    
    print("⚠️ Ollama server not detected. Automatically launching `ollama serve`...")
    try:
        subprocess.Popen(
            ["ollama", "serve"], 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )
        for _ in range(12):
            time.sleep(0.5)
            if is_ollama_running():
                print("✅ Ollama server successfully started!")
                return True
    except Exception as e:
        print(f"❌ Failed to auto-start Ollama: {e}")
        
    return False

def extract_article_content(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find('h1')
        title_text = title.get_text().strip() if title else (soup.title.string if soup.title else "No Title Found")
        
        paragraphs = soup.find_all('p')
        article_text = " ".join([p.get_text().strip() for p in paragraphs])
        
        return title_text, article_text
    except Exception as e:
        return None, str(e)

def scrape_site_articles(website_url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(website_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        parsed_base = urlparse(website_url)
        base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"
        
        seen_links = set()
        articles = []
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            full_url = urljoin(base_domain, href)
            
            parsed_link = urlparse(full_url)
            if parsed_link.netloc == parsed_base.netloc:
                link_text = a_tag.get_text().strip()
                if len(link_text) > 25 and full_url not in seen_links:
                    seen_links.add(full_url)
                    articles.append({
                        "url": full_url,
                        "headline": link_text,
                        "source_domain": parsed_base.netloc
                    })
        return articles
    except Exception as e:
        print(f"Error scraping {website_url}: {e}")
        return []

def get_agent_system_prompt(title, content, smart_summary=True):
    summary_rule = """
    - SUMMARY LENGTH RULE (Smart Mode): If worth_reading is "Yes", provide an expanded, detailed summary (3-4 sentences) covering full context and key findings. If "No" or "Skim Only", keep detailed_summary extremely brief (1 short sentence max or empty).
    """ if smart_summary else """
    - SUMMARY LENGTH RULE (Uniform Mode): Provide a standard, equal-length summary (2-3 sentences) across all articles regardless of worth_reading rating.
    """

    return f"""
    You are an expert content strategist, media critic, and ultra-fast article skimmer. 
    Your job is to analyze articles, news links, or pasted text—especially clickbait or sensationalized headlines—and instantly extract the core facts, revealing whether the article actually delivers on its promises.

    CORE DIRECTIVES:
    1. Reveal the "Clickbait Payload": Immediately answer the core promise or question posed by the headline.
    2. Strict Time-Value Rating: Rate whether the article is worth reading in full on a scale of 1 to 5 (1 = Pure Filler/Skip, 5 = Highly Valuable/Must Read).
    3. Fluff vs. Substance Analysis: Distinguish between hard facts and background fluff added just to drive impressions.
    {summary_rule}

    ARTICLE HEADLINE: "{title}"
    ARTICLE TEXT: "{content[:4000]}"

    Respond strictly in valid JSON format matching this exact schema:
    {{
      "tldr": "1-2 sentences answering the core headline premise directly and revealing the clickbait payload in layman terms.",
      "detailed_summary": "Detailed summary structured according to the SUMMARY LENGTH RULE.",
      "takeaways": [
        "First key takeaway fact.",
        "Second key takeaway fact.",
        "Third key takeaway fact."
      ],
      "worth_reading": "Yes / No / Skim Only",
      "value_rating": "X/5",
      "reason": "Brief explanation (e.g., '90% of the article is repeated historical background, only 1 paragraph contains new news.').",
      "clickbait_percentage": 85,
      "clickbait_verdict": "Explanation of headline match vs sensationalism.",
      "red_flags": "Note if the article uses repetitive text, unsourced claims, heavy sensationalism, or misleading statistics."
    }}
    """

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/history', methods=['GET'])
def get_history():
    return jsonify(load_history())

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"ollama_online": is_ollama_running()})

@app.route('/gpu-stats', methods=['GET'])
def get_gpu_stats():
    """Queries nvidia-smi for real-time local GPU VRAM & load metrics."""
    try:
        if not shutil.which("nvidia-smi"):
            return jsonify({"available": False})

        cmd = ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        line = result.stdout.strip().split("\n")[0]
        parts = [p.strip() for p in line.split(",")]

        if len(parts) >= 3:
            return jsonify({
                "available": True,
                "gpu_utilization": f"{parts[0]}%",
                "gpu_util_num": int(parts[0]),
                "vram_used": f"{parts[1]} MB",
                "vram_total": f"{parts[2]} MB"
            })
    except Exception:
        pass
    return jsonify({"available": False})

@app.route('/analyze', methods=['POST'])
def analyze():
    if not ensure_ollama_running():
        return jsonify({'error': 'Ollama server is offline and auto-launch failed'}), 503

    data = request.get_json()
    url = data.get('url')
    smart_summary = data.get('smart_summary', True)
    
    if not url:
        return jsonify({'error': 'Please provide a valid URL'}), 400
        
    save_history_item("single", url)
    title, content = extract_article_content(url)
    if not content or title is None:
        return jsonify({'error': f'Failed to fetch article: {content}'}), 500

    prompt = get_agent_system_prompt(title, content, smart_summary)
    
    try:
        res = requests.post(OLLAMA_GENERATE_URL, json={
            "model": OLLAMA_MODEL, 
            "prompt": prompt, 
            "format": "json", 
            "stream": False,
            "keep_alive": "10m"
        }, timeout=120)
        res.raise_for_status()
        result_json = json.loads(res.json().get('response', '{}'))
        result_json['original_title'] = title
        result_json['url'] = url
        return jsonify(result_json)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/scan-website', methods=['POST'])
def scan_website():
    data = request.get_json()
    website_url = data.get('url')
    
    if not website_url:
        return jsonify({'error': 'Provide a valid website URL'}), 400
        
    save_history_item("batch", website_url)
    articles = site_scraper_safe(website_url)
    if not articles:
        return jsonify({'error': 'Failed to extract articles from the URL'}), 500
        
    return jsonify({"articles": articles, "total_found": len(articles)})

@app.route('/aggregate-websites', methods=['POST'])
def aggregate_websites():
    data = request.get_json()
    urls = data.get('urls', [])
    
    valid_urls = [u.strip() for u in urls if u and u.strip()][:5]
    if not valid_urls:
        return jsonify({'error': 'Provide at least one valid news website URL'}), 400

    for u in valid_urls:
        save_history_item("aggregator", u)

    portal_article_lists = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(site_scraper_safe, valid_urls)
        for article_list in results:
            if article_list:
                portal_article_lists.append(article_list)

    if not portal_article_lists:
        return jsonify({'error': 'Failed to extract articles from any of the provided URLs'}), 500

    interleaved_articles = []
    seen_urls = set()
    zipped_matrix = zip_longest(*portal_article_lists, fillvalue=None)
    
    for portal_items in zipped_matrix:
        for art in portal_items:
            if art and art['url'] not in seen_urls:
                seen_urls.add(art['url'])
                interleaved_articles.append(art)

    return jsonify({"articles": interleaved_articles, "total_found": len(interleaved_articles), "sources_scanned": len(portal_article_lists)})

def site_scraper_safe(url):
    try:
        return scrape_site_articles(url)
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return []

@app.route('/batch-analyze', methods=['POST'])
def batch_analyze():
    if not ensure_ollama_running():
        return jsonify({'error': 'Ollama server is offline and auto-launch failed'}), 503

    data = request.get_json()
    urls = data.get('urls', [])
    smart_summary = data.get('smart_summary', True)
    
    urls = urls[:10]
    if not urls:
        return jsonify({'error': 'No article URLs provided'}), 400
        
    results = []
    for url in urls:
        title, content = extract_article_content(url)
        if not content or title is None:
            results.append({"url": url, "error": "Failed to fetch content"})
            continue
            
        prompt = get_agent_system_prompt(title, content, smart_summary)
        try:
            res = requests.post(OLLAMA_GENERATE_URL, json={
                "model": OLLAMA_MODEL, 
                "prompt": prompt, 
                "format": "json", 
                "stream": False,
                "keep_alive": "10m"
            }, timeout=120)
            res.raise_for_status()
            item_json = json.loads(res.json().get('response', '{}'))
            item_json['original_title'] = title
            item_json['url'] = url
            results.append(item_json)
        except Exception as e:
            results.append({"url": url, "original_title": title, "error": str(e)})
            
    return jsonify({"results": results})

@app.route('/summarize-text', methods=['POST'])
def summarize_text():
    if not ensure_ollama_running():
        return jsonify({'error': 'Ollama server is offline and auto-launch failed'}), 503

    data = request.get_json()
    raw_text = data.get('text', '')
    
    if not raw_text or len(raw_text.strip()) < 10:
        return jsonify({'error': 'Please provide sufficient text or email content to summarize'}), 400

    prompt = f"""
    You are an ultra-fast text and email summarizer. 
    Analyze the provided raw text/email and extract key information without storing or retaining any context.

    INPUT TEXT:
    "{raw_text[:8000]}"

    Respond strictly in valid JSON format matching this exact schema:
    {{
      "tldr": "1-2 sentence core executive summary answering what this text/email is about.",
      "key_takeaways": [
        "First key takeaway or observation.",
        "Second key takeaway or observation.",
        "Third key takeaway or observation."
      ],
      "action_items": [
        "Action required 1 (or 'None' if purely informational)."
      ],
      "sentiment_urgency": "Low / Medium / High Urgency",
      "reading_time_saved": "Estimated minutes saved by reading this summary."
    }}
    """
    try:
        res = requests.post(OLLAMA_GENERATE_URL, json={
            "model": OLLAMA_MODEL, 
            "prompt": prompt, 
            "format": "json", 
            "stream": False,
            "keep_alive": "10m"
        }, timeout=90)
        res.raise_for_status()
        return jsonify(json.loads(res.json().get('response', '{}')))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)