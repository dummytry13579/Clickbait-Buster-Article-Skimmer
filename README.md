# Clickbait-Buster-Article-Skimmer
The Problem: Wasting time reading through sensational news articles that turn out to be clickbait or ad-heavy fluff. The Goal: Build an automated system to skim web articles, summarize them in layman's terms, extract hard facts, score headline validity, and auto-evaluate whether an article is worth a full read.

# 🚨 Clickbait Buster & Article Skimmer

## 1. Project Overview & Motivation
Modern news and media sites frequently rely on sensationalized, clickbait headlines that hook readers into spending valuable time reading long articles, only to discover the headline was exaggerated, misleading, or padded with endless filler and historical background. 

This project was built to solve that exact frustration:
* **The Problem:** Wasting time reading through sensational news articles that turn out to be clickbait or ad-heavy fluff.
* **The Goal:** Build an automated system to skim web articles, summarize them in layman's terms, extract hard facts, score headline validity, and auto-evaluate whether an article is worth a full read.

---

## 2. Summary of Changes: Phase 1 vs. Phase 2 (v2.4)

| Feature / Aspect | Phase 1 (Initial Blueprint) | Phase 2 (v2.4 Final Application) |
| :--- | :--- | :--- |
| **Port & Server** | Port `5000` | Port `5001` |
| **Local Model** | `qwen2.5` | `qwen3:8b` |
| **Input Capabilities** | Single URL analysis only | **Dual Mode:** Single URL + Full Website Batch Scanning |
| **Batch Pagination** | N/A | Lists discovered articles in **10 per page** batches |
| **Article Selection** | Single input box | Interactive checkbox list with a **Master "Select / Deselect All"** toggle |
| **Ollama Server Management** | Manual health check & alert | **Automated Startup:** Backend auto-launches `ollama serve` in WSL if offline |
| **Summarization Engine** | Standard summary across all inputs | **Smart Summary Mode:** Lengthens detailed summaries *only* for articles rated *"Worth Reading: Yes"*, keeping skips ultra-brief |

---

## 3. Project Architecture & File Structure

Organize your project directory with the following structure:

```text
clickbait-buster/
│
├── app.py                 # Flask backend v2.4 (Scraper, Ollama auto-start, Agent logic)
├── requirements.txt       # Python dependencies
├── README.md              # Project documentation & agent specification
└── templates/
    └── index.html         # Tailwind CSS v2.4 dashboard UI
```

---

## 4. Complete Agent System Specification

### Role & Purpose
You are an expert content strategist, media critic, and ultra-fast article skimmer. Your job is to analyze articles, news links, or pasted text—especially clickbait or sensationalized headlines—and instantly extract the core facts, revealing whether the article actually delivers on its promises.

### Core Directives
1. **Reveal the "Clickbait Payload":** Immediately answer the core promise or question posed by the headline (e.g., if the headline is "You Won't Believe What This Actor Did!", state right away what the actor actually did).
2. **Strict Time-Value Rating:** Rate whether the article is worth reading in full on a scale of 1 to 5 (1 = Pure Filler/Skip, 5 = Highly Valuable/Must Read).
3. **Fluff vs. Substance Analysis:** Distinguish between actual hard facts, primary sources, quotes, and background fluff added just to drive ad impressions or scroll time.
4. **Conditional Summary Rules:**
   * **Smart Summary Mode:** If `worth_reading` is `"Yes"`, generate an expanded detailed summary (3–4 sentences) covering full context and key findings. If `"No"` or `"Skim Only"`, keep the detailed summary extremely brief (1 sentence max or empty) to save user reading time.
   * **Uniform Mode:** Provide an equal, standard-length summary (2–3 sentences) across all inputs regardless of rating.

### Human-Readable Response Framework
* **The TL;DR (The Bottom Line):** 1–2 sentences answering the core headline premise directly.
* **Key Takeaways:** 3 bullet points summarizing the key facts or new information.
* **Readability & Value Score:** 
  * **Worth Reading?** [Yes / No / Skim Only]
  * **Value Rating:** [X/5]
  * **Reason:** Brief explanation (e.g., *"90% of the article is repeated historical background, only 1 paragraph contains new news."*).
* **Red Flags / Filler Warning:** Note if the article uses repetitive text, unsourced claims, heavy sensationalism, or misleading statistics.

### Structured Response Schema (JSON)
```json
{
  "tldr": "1-2 sentences answering the core headline premise directly in layman terms.",
  "detailed_summary": "Expanded or brief summary dictated by the SUMMARY LENGTH RULE.",
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
}
```

---

## 5. Pre-Conditions Before Running

Before launching the application, ensure you have:
1. **Python 3.10+** installed in your environment.
2. **Ollama** installed on your machine or inside **WSL (Windows Subsystem for Linux)**.
3. The `qwen3:8b` model pulled locally via Ollama:
   ```bash
   ollama pull qwen3:8b
   ```

---

## 6. Localizing Ollama & Automatic Startup

To maintain zero API costs and total privacy, all requests run locally:
* **Manual Verification:** You can verify your local server status by running:
  ```bash
  curl http://localhost:11434/api/tags
  ```
* **Automated Process Spawning (New in v2.4):** If the Ollama background daemon is inactive when a user submits an article, the Python backend automatically executes `subprocess.Popen(["ollama", "serve"])` in WSL and polls the port until the server is ready, ensuring zero manual terminal setup.

---

## 7. How to Install and Run

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Required packages: `Flask`, `requests`, `beautifulsoup4`)*

2. **Launch the Flask Server:**
   ```bash
   python app.py
   ```

3. **Access the Dashboard:**
   Open your browser and navigate to:
   ```text
   http://127.0.0.1:5001
   ```
