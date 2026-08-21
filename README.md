# AI EOD Assistant

Phase 1 is an online MVP for preparing factual daily End-of-Day reports from explicit user-entered text.

## What is included in Phase 1

- Streamlit desktop-friendly web UI with fixed top navigation and gradient theme
- Backend service layer for the Phase 1 EOD workflow
- SQLite persistence with safe table creation
- User-entered text activity capture
- Reviewed microphone transcription (STT) using Gemini audio input
- Browser-local report playback (TTS)
- User-defined tasks that explain what monitored workspace activity is about
- Explicit, local-only workspace file activity scans with project and changed-file summaries
- Reviewed activity imports from external tools
- Gemini API provider behind an `AIProvider` abstraction
- Online Gemini or offline Ollama provider selection
- Team login with seeded alpha admin, team leaders, and member-scoped EOD history
- Factual EOD prompt with evidence priority rules
- Save and view generated EOD history
- Session/.env-based settings without hardcoded secrets
- Basic backend and snapshot tests for core logic

## Privacy stance

The MVP does **not** implement keylogging, credential capture, covert monitoring, document scanning, chat scraping, or automatic device activity capture. Audio is transcribed only after you record it and choose to transcribe it; transcripts and reviewed activity are stored and sent to Gemini for EOD generation.

## Team login

The first database initialization creates team `alpha` and an admin account:

```text
User ID: admin
Password: admin123
```

Sign in as `admin` to add members to alpha or create a team leader for another team. Team leaders can add members only to their own team and can view that team's EOD history. Members can create their own daily EODs and view only their own history. Change the seeded password before sharing the app.

Admins have a read-only EOD history workspace with member, date, and text search filters. Search is applied when the filter form is submitted, so typing does not trigger a database query for every character. Admins can change passwords for accounts in their scope and permanently clear all saved EOD reports from Team administration. To recover the root admin, set a private `ADMIN_RECOVERY_KEY` in `.env` and use **Forgot root admin password** on the login screen. Newly authenticated accounts cannot see unowned legacy records or another member's records.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:

```bash
GEMINI_API_KEY=your_key_here
```

## Offline mode with Ollama

1. Install Ollama from [ollama.com/download](https://ollama.com/download).
2. Start Ollama. Its default local server is `http://127.0.0.1:11434`.
3. Download a free local model once:

```bash
ollama pull llama3.2:3b
```

4. Open **Settings**, choose **Offline (Ollama)**, enter `llama3.2:3b`, and click **Apply settings**.
5. Generate EOD reports without sending evidence to the internet. The model files and prompts stay on the local machine.

The computer needs internet only for the initial Ollama/model download. After that, offline EOD generation works while Ollama is running. Offline voice transcription is not enabled for the default text-only model; use text activity in offline mode or select Online (Gemini) for audio transcription.

## Free persistent cloud database

For a shared Streamlit Cloud deployment, create a free Supabase project and copy its PostgreSQL connection string from **Connect -> Transaction pooler**. In Streamlit Cloud, open the app's **Settings -> Secrets** and add:

```toml
DATABASE_URL = "postgresql://postgres.[project-ref]:[PASSWORD]@[pooler-host]:6543/postgres?sslmode=require"
GEMINI_API_KEY = "your-gemini-key"
ADMIN_RECOVERY_KEY = "your-long-private-recovery-key"
```

Do not commit `DATABASE_URL` or passwords to GitHub. When `DATABASE_URL` is present, the app uses Supabase PostgreSQL; otherwise it uses local SQLite. The schema and seeded `admin` account are created automatically on first startup. The free Supabase tier is suitable for a 10-50 person team with normal EOD usage, subject to Supabase's current quotas and inactivity pause policy.

The default model is `gemini-3.5-flash-lite`, a low-latency, cost-effective multimodal model. You can change `GEMINI_MODEL` in `.env`.

## Run

```bash
streamlit run ai_eod_assistant/app.py
```

## Manual MVP workflow

1. Open **Add Activity**.
2. Add a task title and description so the model knows what the work is about.
3. Enter confirmed work you performed today, or record an update and review its Gemini transcript before saving.
4. Optionally open **Workspace activity**, select a folder and task, and review the changed-file summary before saving it.
5. Optionally import a reviewed activity summary from another application.
6. Open **Generate EOD** and review the evidence block that will be sent to Gemini.
7. Generate and save the report. Use **Speak report** to play it through the browser's local speech engine.
8. Open **EOD History** to review saved reports.

## Privacy and workspace activity

Workspace scanning is opt-in and runs only after selecting a folder and clicking **Scan selected workspace**. It records file modification metadata from that folder (project name, relative path, type, and timestamp). It does not collect keystrokes, clipboard contents, screenshots, window titles, credentials, or application content.

For other applications, use **External activity** to import an exported, reviewed summary. This keeps the MVP transparent and avoids covert cross-application monitoring.

## Tests

```bash
pytest
```

Snapshot tests live in `ai_eod_assistant/tests/snapshots/` and verify the stable prompt/evidence/report contracts used by the backend service.

## Future milestones

- Phase 2: richer STT + voice input + TTS
- Phase 3: PDF/DOCX/XLSX/TXT processing
- Phase 4: Imported chat analysis
- Phase 5: Local device activity monitoring
- Phase 6: Activity grouping, project detection, confidence scoring
- Phase 7: Advanced EOD generation
- Phase 8: Offline local LLM
- Phase 9: Online/offline provider switch
- Phase 10: Windows packaging and optimization
