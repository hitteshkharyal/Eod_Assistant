# AI EOD Assistant

AI EOD Assistant is a multi-user Streamlit application for preparing factual daily End-of-Day reports from explicit, reviewed work evidence.

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

## Local setup

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

## Local Ollama connector for the hosted app

The Streamlit Cloud server cannot directly see Ollama on a user's computer. This repository includes a small local connector that detects Ollama and exposes the installed model list:

```bash
python -m ai_eod_assistant.local_connector
```

Check it locally:

```text
http://127.0.0.1:8765/health
http://127.0.0.1:8765/models
```

The connector forwards `/generate` requests to the user's Ollama server. Keep it bound to `127.0.0.1` for local-only use. To let a private hosted deployment reach it, use a private VPN such as Tailscale and set `OLLAMA_CONNECTOR_HOST` to the private interface plus `OLLAMA_CONNECTOR_TOKEN` to a secret token. Do not expose this connector or Ollama directly to the public internet.

The connector also exposes `/scan`. In the hosted app, each user must run the connector on their own device, open **Workspace activity**, enter the folder path as it exists on that device, and keep the connector running while clicking **Scan selected workspace**. The app sends the reviewed metadata to PostgreSQL with the user's account ownership. Example Windows start command:

```powershell
python -m ai_eod_assistant.local_connector
```

In a local Streamlit run, the **Start local connector** button on **Workspace activity** can launch this command automatically. A button in Streamlit Cloud cannot launch a terminal on a remote user's computer; use the command above or a separately installed local connector for that case.

For a local app, use `http://127.0.0.1:8765`. For a hosted app, `127.0.0.1` points to the cloud server; use a private VPN connector address or run the app locally on the same device instead.

The cloud app still saves the completed EOD to Supabase PostgreSQL. For the hosted Streamlit UI to invoke a user's connector, the connector URL must be reachable from the deployment through a private network, or a browser-side connector bridge must be added. A plain `127.0.0.1` URL entered in Streamlit Cloud points to the cloud server, not the user's computer.

When using a private VPN connector, enter its connector URL (for example `http://100.x.x.x:8765`) in the app's **Settings -> Ollama server URL**. The connector accepts Ollama's standard `/api/generate` path, so the existing Offline (Ollama) provider can forward prompts through it and save the resulting EOD in PostgreSQL.

## Deploy to Streamlit Community Cloud

This is the recommended free hosting path for this Streamlit app.

### 1. Create the persistent database

Create a free project at [Supabase](https://supabase.com/), open **Connect**, choose **Transaction pooler**, and copy the full PostgreSQL URI. Use the pooler URI, not the Supabase REST API URL. The URI normally uses port `6543` and includes `sslmode=require`.

### 2. Create the Streamlit app

1. Open [share.streamlit.io](https://share.streamlit.io/).
2. Choose **New app** and repository `hitteshkharyal/Eod_Assistant`.
3. Select branch `main`.
4. Set the main file to `ai_eod_assistant/app.py`.
5. Click **Deploy**.

The repository already includes `requirements.txt` and `.streamlit/config.toml`, so Streamlit Cloud installs the dependencies and loads the theme automatically.

### 3. Add secrets

In the deployed app, open **Manage app -> Settings -> Secrets** and add TOML like this:

```toml
DATABASE_URL = "postgresql://postgres.[project-ref]:[PASSWORD]@[pooler-host]:6543/postgres?sslmode=require"
GEMINI_API_KEY = "your-gemini-api-key"
ADMIN_RECOVERY_KEY = "use-a-long-private-random-value"
AI_MODE = "Online (Gemini)"
GEMINI_MODEL = "gemini-3.5-flash-lite"
```

Replace the placeholders with values from Supabase and Gemini. Do not paste secrets into source files or commit `.env`; `.env` and `.env.*` are ignored by Git.

### 4. First login and verification

On first startup, the app creates the PostgreSQL tables and seeds:

```text
Team: alpha
User ID: admin
Password: admin123
```

Sign in, immediately change the admin password, create team leaders/members, and generate a test EOD. Verify that a member sees only their own history and an admin sees only their team history. If the app sleeps, Supabase remains the persistent source for users and EOD reports.

### Cloud deployment limitations

- Streamlit Cloud can run the app for users on different networks.
- Supabase PostgreSQL stores shared EOD history persistently; SQLite is only the local fallback.
- Streamlit Cloud must use **Online (Gemini)**. It cannot reach Ollama installed on your Windows computer.
- Supabase Free and Streamlit Community Cloud have quotas, sleep behavior, and possible inactivity pauses. Check their current limits before production use.

The default model is `gemini-3.5-flash-lite`, a low-latency, cost-effective multimodal model. You can change `GEMINI_MODEL` in `.env` or Streamlit Secrets.

## Other hosting options

The app can also run on Railway, Render, Fly.io, or a small VPS. Use the same start command:

```bash
streamlit run ai_eod_assistant/app.py --server.address 0.0.0.0 --server.port $PORT
```

Configure the same environment variables as Streamlit Secrets, especially `DATABASE_URL`, `GEMINI_API_KEY`, and `ADMIN_RECOVERY_KEY`. Use a managed PostgreSQL database for shared history. Do not rely on local SQLite disk for a hosted multi-user deployment.

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
7. Generate and save the report. Use **Speak summary** to play it through the browser's local speech engine.
8. Open **EOD History** to review saved reports.

## Privacy and workspace activity

Workspace scanning is opt-in and runs only after selecting a folder and clicking **Scan selected workspace**. It records file modification metadata from that folder (project name, relative path, type, and timestamp). It does not collect keystrokes, clipboard contents, screenshots, window titles, credentials, or application content.

For other applications, use **External activity** to import an exported, reviewed summary. This keeps the MVP transparent and avoids covert cross-application monitoring.

## Tests

```bash
pytest
```

Snapshot tests live in `ai_eod_assistant/tests/snapshots/` and verify the stable prompt/evidence/report contracts used by the backend service.

## Current limitations

- The default offline model is text-only; voice transcription uses Gemini.
- Streamlit Cloud cannot directly reach Ollama on a user's computer. Use Online (Gemini), or connect a local Ollama connector through a private network.
- Workspace monitoring is opt-in and records file metadata only.
