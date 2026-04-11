# AI Assistant Project Overview: Instagram Auto Post

This document provides a technical overview of the **Instagram Auto Post** application to help AI agents understand the codebase, its architecture, and recent feature updates.

## 🚀 Project Goal
Automate the creation and publication of Instagram content (Images/Reels/Stories) using a Google Sheet as the source of truth, integrated with AI for content generation and viewer engagement.

## 🛠 Tech Stack
- **Core:** Python, Streamlit (Dashboard UI).
- **APIs:** 
  - **Instagram Graph API:** Post creation, publication, and comment management.
  - **Google Sheets API:** Content scheduling and status tracking.
  - **Pollinations API:** Image (FLUX), Video (Grok/Wan), and Text (GPT-style) generation.
  - **Cloudinary:** Media hosting for direct Instagram publishing.
- **Automation:** Playwright (Playwright is used in some background auth flows).

## 📁 Key Components
- `app.py`: Main entry point for the Streamlit dashboard.
- `instagram_poster/`:
  - `config.py`: Configuration management with a persistence layer (`.config_overrides.json`) that survives restarts and page switches.
  - `ig_client.py`: Wrapper for Instagram Graph API. Handles media creation, polling, and publishing.
  - `sheets_client.py`: Logic for reading/writing post data to Google Sheets.
  - `comment_autoreply.py`: Background logic for AI-powered comment replies. Enforces English responses and context-awareness.
  - `image_generator.py`: Converts quotes into visual prompts and generates images.
  - `reel_generator.py`: Handles AI video generation and synchronization.
  - `providers/`: Multi-provider support (Pollinations, Gemini, NVIDIA, etc.).

## ✨ Recent Critical Updates
1. **AI Autoreply System:**
   - Uses Pollinations API to reply to Instagram comments.
   - **Persistence:** The AI toggle state is persistent across page navigations in Streamlit via `config.py`.
   - **Resilience:** Implemented retry loops with exponential backoff for Pollinations API calls (handling 521/500 errors).
   - **Language Policy:** Strictly English responses via system prompts.
2. **Comment Logic Fixes:**
   - Resolved `@?` mention issue by fixing username extraction from nested `from` objects in the Instagram API response.
   - Strict deduplication ensures only one reply per comment.
3. **Module Stability:**
   - Refactored imports to prevent circular dependencies and `ImportError` during Streamlit's runtime.

## 📋 Google Sheet Structure
The project expects a sheet (default `Folha1`) with:
1. `Date` (YYYY-MM-DD)
2. `Time` (HH:MM)
3. `Image Text` (Overlay quote)
4. `Caption` (Post text)
5. `Gemini_Prompt` (Visual prompt)
6. `Status` (ready/posted)
7. `Published` (yes/empty)
... and other metadata columns.

## 🚦 Running the App
- Port: `8502`
- Run Command: `streamlit run app.py` (or through `run.sh`/`run.bat`)
- Background processes (like `autopublish`) are managed via sessions and file-based locking.

---
*Generated for OpenClaw / AI Interaction context.*
