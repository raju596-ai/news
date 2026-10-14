# Enterprise Real-Time AI News Video Generation Platform

An autonomous, multi-agent AI broadcast news platform built with **Python (uv)**, **FastAPI**, **FFmpeg**, and **Google Gemini** (`gemini-3.8-flash`), producing full **5-Minute broadcast-quality YouTube videos** (1080p, 16:9, 30 FPS, AAC 48 kHz).

---

## 🚀 How to Run the Project

### Option 1: One-Click Startup (Windows)
Double-click either of the startup scripts in the project root:
- **`run.bat`** (Command Prompt / Explorer)
- **`run.ps1`** (Right-click -> Run with PowerShell)

### Option 2: Terminal / Command Line
Open a terminal in `D:\news` and run:
```bash
uv run uvicorn news.api.main:app --host 127.0.0.1 --port 8000 --reload
```
*(If `uv` is not globally in your PATH, you can use `%USERPROFILE%\.local\bin\uv.exe` or your virtual environment).*

### Option 3: Access the Live Dashboard
Once the server is running, open your browser to:
- 🌐 **Web Dashboard**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- 📚 **Interactive Swagger API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🎬 How to Generate 5-Minute News Videos

1. Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser.
2. Click **"Start AI Video Workflow"**.
3. The platform will automatically execute the 6-agent pipeline:
   - **Ingestion & Ranking**: Extracts and curates the **Top 2 World Stories** and **Top 2 India Stories** from verified real-time feeds from the last 24 hours.
   - **5-Minute Script Generation**: Drafts an authoritative, comprehensive ~600–680 word broadcast script divided into 22–26 timed scenes.
   - **Real-Time Visual Fetching**: Downloads verified, topic-specific high-resolution news imagery for each scene.
   - **Voice Narration**: Synthesizes high-clarity broadcast voiceover (~280–290 seconds).
   - **FFmpeg 1080p Assembly**:
     - Prepends `start.mp4` (10s Intro).
     - Renders body news slides with smooth transitions every 10–15 seconds synced to audio.
     - Appends `end.mp4` (6s Outro).
     - **Total duration**: ~5 minutes (approx. 296–306 seconds).
4. Once rendered, click **▶ Preview** to watch the 1080p video directly in your browser, or **⬇ Download** to save the MP4 file.
5. Click **📋 YouTube Details** to view the ready-to-copy YouTube upload metadata:
   - Optimized Title
   - Structured Description (Summary, "In this video", Why it matters, Latest update, Sources, Hashtags)
   - 20+ Targeted Search Tags
   - Category (`News & Politics`) & Language
   - Suggested Playlist (India News / World News)
   - Custom 1280x720 Thumbnail preview & download

---

## ⏱️ 5-Minute Video Script Architecture

| Section | Target Duration | Word Count | Segments / Slide Transitions |
|---|---|---|---|
| **🎬 Intro Clip** (`start.mp4`) | 10 seconds | — | Channel branding intro |
| **1. 🎯 Hook** | 20–25 sec | ~45–55 words | 2 scenes (10–12s each) |
| **2. 📰 What Happened** | 50–60 sec | ~105–125 words | 4–5 scenes (12–15s each) |
| **3. 🔎 Key Details & Breakdown** | 100–120 sec | ~220–250 words | 8–10 scenes (12–15s each) |
| **4. 🌍 Why It Matters & Impact** | 50–60 sec | ~105–125 words | 4–5 scenes (12–15s each) |
| **5. 📌 Latest Update** | 45–55 sec | ~95–115 words | 3–4 scenes (12–15s each) |
| **6. 🎬 Anchor Sign-Off** | 15–20 sec | ~30–40 words | 1–2 scenes (10–15s each) |
| **🎬 Outro Clip** (`end.mp4`) | 6 seconds | — | Channel closing outro |
| **TOTAL** | **~5:00 min** (~300 sec) | **~600–680 words** | **22–26 distinct scenes** |

---

## 🤖 Multi-Agent Architecture

```
1. Master Orchestrator (LangGraph State Machine)
   ├── 2. News Collector & Ranker (Gemini 3.8 Flash) -> Top 2 World + Top 2 India
   ├── 3. Scriptwriter Agent (6-Section 5-Min Script, 22-26 Scenes)
   ├── 4. Image Isolation & Visual Curation Agent (High-Res Photographic Slides)
   ├── 5. Voice Synthesis Agent (High-Quality 48kHz Audio Track)
   ├── 6. FFmpeg Assembly Agent (start.mp4 + 10-15s Slide Video + end.mp4 -> 1080p MP4)
   └── 7. YouTube Metadata & Thumbnail Generator (Title, Description, 20+ Tags, Thumbnail)
```
