"""Streamlit entry point for the Phase 1 online AI EOD Assistant MVP."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, time
from pathlib import Path
import sys
import subprocess
from typing import Iterator

import streamlit as st

# Streamlit executes this file directly; add the repository root for package imports.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_eod_assistant.auth import authenticate, change_password, create_member, create_team_admin, initialize_auth, recover_root_admin, team_members
from ai_eod_assistant.ai.providers import build_provider
from ai_eod_assistant.ai.stt import transcribe_audio
from ai_eod_assistant.config.settings import get_settings
from ai_eod_assistant.backend.eod_service import EODService
from ai_eod_assistant.database.db import get_connection, initialize_database
from ai_eod_assistant.processing.workspace import format_workspace_evidence, scan_remote_workspace, scan_workspace
from ai_eod_assistant.ui.voice import render_speech_controls


NAVIGATION = [
    "Dashboard",
    "Add activity",
    "Workspace activity",
    "External activity",
    "Generate EOD",
    "EOD history",
    "Team administration",
    "Settings",
]


def render_app_shell() -> str:
    """Render the fixed app header and return the selected page."""
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none; }
        [data-testid="stAppViewContainer"] { background: linear-gradient(135deg, #f5fbfa 0%, #fff7f2 48%, #f4f0ff 100%); }
        [data-testid="stHeader"] { background: transparent; }
        .main .block-container { max-width: 1240px; padding: 2rem 2.5rem 4rem; }
        .st-key-top_nav { position: sticky; top: 0; z-index: 1000; margin: -2rem -2.5rem 2rem; padding: 1rem max(2.5rem, calc((100vw - 1240px) / 2)); background: rgba(255, 255, 255, 0.94); border-bottom: 1px solid rgba(20, 52, 58, 0.12); box-shadow: 0 12px 30px rgba(20, 52, 58, 0.08); backdrop-filter: blur(18px); }
        .st-key-top_nav [data-testid="stMarkdownContainer"] p { margin: 0; }
        .brand-mark { display: flex; align-items: center; gap: .75rem; color: #14343a; }
        .brand-dot { width: 2.35rem; height: 2.35rem; display: grid; place-items: center; border-radius: 10px; color: white; font-weight: 800; background: linear-gradient(135deg, #087f8c, #ef8354); box-shadow: 0 8px 18px rgba(8, 127, 140, .24); }
        .brand-name { font-size: 1.05rem; font-weight: 800; letter-spacing: .01em; }
        .brand-caption { color: #60757a; font-size: .78rem; margin-top: .1rem; }
        .st-key-top_nav [data-testid="stSegmentedControl"] { margin-top: .8rem; }
        .st-key-top_nav [data-baseweb="segmented-control"] { background: #edf5f3; border-radius: 10px; padding: .2rem; }
        .st-key-top_nav [data-baseweb="segmented-control"] button { border-radius: 8px; color: #426066; font-size: .82rem; }
        .st-key-top_nav [data-baseweb="segmented-control"] button[aria-checked="true"] { color: white; background: linear-gradient(135deg, #087f8c, #139a91); }
        h1, h2, h3 { color: #14343a; }
        [data-testid="stMetric"] { background: rgba(255, 255, 255, .72); border: 1px solid rgba(20, 52, 58, .1); border-radius: 12px; padding: 1rem; }
        @media (max-width: 760px) {
            .main .block-container { padding: 1rem 1rem 3rem; }
            .st-key-top_nav { margin: -1rem -1rem 1.5rem; padding: .75rem 1rem; }
            .brand-caption { display: none; }
            .st-key-top_nav [data-baseweb="segmented-control"] { overflow-x: auto; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    if st.session_state["auth_user"].role == "admin":
        navigation = ["EOD history", "Team administration", "Settings"]
    else:
        navigation = [item for item in NAVIGATION if item != "Team administration"]
    with st.container(key="top_nav"):
        st.markdown(
            '<div class="brand-mark"><div class="brand-dot">E</div><div><div class="brand-name">EOD assistant</div><div class="brand-caption">Clear work summaries, grounded in your evidence</div></div></div>',
            unsafe_allow_html=True,
        )
        selected = st.segmented_control(
            "Navigate",
            navigation,
            default=st.session_state.get("page", navigation[0]) if st.session_state.get("page") in navigation else navigation[0],
            key="page_navigation",
            label_visibility="collapsed",
        )
        if st.button(f"Sign out · {st.session_state['auth_user'].username}", icon=":material/logout:"):
            del st.session_state["auth_user"]
            st.rerun()
    page = selected or st.session_state.get("page", navigation[0])
    st.session_state["page"] = page
    return page


@contextmanager
def service_context() -> Iterator[EODService]:
    """Yield an initialized backend service and close its SQLite connection."""
    connection = get_connection()
    try:
        yield EODService(connection, st.session_state.get("auth_user"))
    finally:
        connection.close()


def render_dashboard() -> None:
    st.title("AI EOD Assistant")
    today = date.today()
    with service_context() as service:
        inputs = service.build_preview(today).inputs
        reports = service.recent_reports(5)
    st.metric("Today's text entries", len(inputs))
    st.subheader("Recent reports")
    for report in reports:
        st.write(f"{report.date.isoformat()} — {report.ai_provider}")


def render_login() -> None:
    st.markdown("<div class='login-panel'>", unsafe_allow_html=True)
    st.title("Welcome back")
    st.caption("Sign in to create daily EODs and access your team workspace.")
    username = st.text_input("User ID")
    password = st.text_input("Password", type="password")
    if st.button("Sign in", type="primary", icon=":material/login:"):
        with get_connection() as connection:
            initialize_database(connection)
            initialize_auth(connection)
            user = authenticate(connection, username, password)
        if user:
            st.session_state["auth_user"] = user
            st.rerun()
        st.error("Invalid user ID or password.")
    st.caption("Initial admin: admin / admin123. Change this account before sharing the app.")
    with st.expander("Forgot root admin password"):
        st.caption("This recovery requires the local ADMIN_RECOVERY_KEY from your .env file.")
        recovery_key = st.text_input("Recovery key", type="password")
        recovery_password = st.text_input("New admin password", type="password")
        if st.button("Reset root admin password"):
            try:
                settings = get_settings()
                with get_connection() as connection:
                    initialize_database(connection)
                    initialize_auth(connection)
                    recover_root_admin(connection, recovery_key, recovery_password, settings.admin_recovery_key)
                st.success("Root admin password reset. Sign in with the new password.")
            except (PermissionError, ValueError) as exc:
                st.error(str(exc))
    st.markdown("</div>", unsafe_allow_html=True)


def render_team_administration() -> None:
    user = st.session_state["auth_user"]
    st.header("Team administration")
    st.caption(f"Team: {user.team_name} · Team leader access")
    with st.container(border=True):
        st.subheader("Add team member")
        member_id = st.text_input("Member user ID")
        member_password = st.text_input("Temporary password", type="password")
        if st.button("Add member", type="primary", icon=":material/person_add:"):
            try:
                with get_connection() as connection:
                    create_member(connection, member_id, member_password, user.team_id)
                st.success(f"Member {member_id.strip()} added to {user.team_name}.")
            except Exception as exc:  # noqa: BLE001 - validation and uniqueness errors are user-facing.
                st.error(f"Could not add member: {exc}")
    with get_connection() as connection:
        members = team_members(connection, user.team_id)
    st.dataframe(members, hide_index=True, width="stretch")
    with st.container(border=True):
        st.subheader("Change a password")
        password_user = st.selectbox("Account", [str(member["username"]) for member in members])
        new_password = st.text_input("New password", type="password")
        if st.button("Change password", icon=":material/key:"):
            try:
                with get_connection() as connection:
                    change_password(connection, user, password_user, new_password)
                st.success(f"Password changed for {password_user}.")
            except (PermissionError, ValueError) as exc:
                st.error(str(exc))
    if user.username == "admin":
        with st.container(border=True):
            st.subheader("Create another team leader")
            admin_id = st.text_input("Admin user ID")
            admin_password = st.text_input("Admin password", type="password")
            team_name = st.text_input("New team name")
            if st.button("Create team leader", icon=":material/admin_panel_settings:"):
                try:
                    with get_connection() as connection:
                        create_team_admin(connection, admin_id, admin_password, team_name)
                    st.success(f"Team leader {admin_id.strip()} created for {team_name.strip()}.")
                except Exception as exc:  # noqa: BLE001 - validation and uniqueness errors are user-facing.
                    st.error(f"Could not create team leader: {exc}")
    with st.container(border=True):
        st.subheader("Clear all EOD history")
        st.warning("This permanently deletes every saved EOD report for every team.")
        confirm_clear = st.checkbox("I understand this cannot be undone")
        if st.button("Delete all EOD reports", disabled=not confirm_clear, icon=":material/delete_forever:"):
            with service_context() as service:
                deleted = service.clear_all_reports()
            st.success(f"Deleted {deleted} EOD report(s).")


def render_add_activity() -> None:
    st.header("Add activity")
    task_title = st.text_input("Task title", placeholder="e.g., Build monitoring EOD workflow")
    task_description = st.text_area("What is this task about?", height=90)
    if st.button("Add task", icon=":material/add_task:"):
        if not task_title.strip():
            st.warning("Enter a task title first.")
        else:
            with service_context() as service:
                service.add_task(task_title, task_description)
            st.success("Task added. Select it when saving monitoring activity.")

    text_tab, voice_tab = st.tabs(["Text", "Voice"])
    with text_tab:
        content = st.text_area("What did you work on today?", height=180, key="text_activity")
        if st.button("Save text activity", type="primary", icon=":material/save:"):
            if not content.strip():
                st.warning("Please enter work details before saving.")
            else:
                with service_context() as service:
                    service.add_text_activity(content)
                st.success("Activity saved as confirmed user-provided evidence.")
    with voice_tab:
        st.caption("Record a short update, transcribe it with Gemini, then review before saving.")
        audio = st.audio_input("Record your work update", sample_rate=16000, key="voice_recording")
        settings = get_settings()
        mode = st.session_state.get("ai_mode") or settings.ai_mode
        api_key = st.session_state.get("gemini_api_key") or settings.gemini_api_key
        model = st.session_state.get("ai_model") or (settings.gemini_model if mode == "Online (Gemini)" else settings.ollama_model)
        ollama_base_url = st.session_state.get("ollama_base_url") or settings.ollama_base_url
        if st.button("Transcribe recording", icon=":material/transcribe:", disabled=audio is None):
            if not api_key:
                st.error("Add GEMINI_API_KEY in Settings before transcribing audio.")
            else:
                try:
                    st.session_state["voice_transcript"] = transcribe_audio(
                        build_provider(mode, gemini_api_key=api_key, model=model, ollama_base_url=ollama_base_url),
                        audio.getvalue(), getattr(audio, "type", "audio/wav")
                    )
                except Exception as exc:  # noqa: BLE001 - provider errors are user-facing.
                    st.error(f"Could not transcribe recording: {exc}")
        transcript = st.text_area("Review transcript before saving", height=180, key="voice_transcript")
        if st.button("Save reviewed voice activity", type="primary", icon=":material/save:"):
            if not transcript.strip():
                st.warning("Record and transcribe an update, or enter a reviewed transcript first.")
            else:
                with service_context() as service:
                    service.add_voice_activity(transcript)
                st.success("Reviewed voice transcript saved as evidence.")


def render_workspace_monitor() -> None:
    st.header("Workspace activity")
    st.info("This scanner runs only when you click it and reads only the folder you choose. It tracks file modification metadata, not keystrokes, clipboard, screen content, or application windows.")
    connector_process = st.session_state.get("connector_process")
    if connector_process and connector_process.poll() is None:
        st.success("Local connector is running on this computer.", icon=":material/check_circle:")
    elif st.button("Start local connector", icon=":material/play_arrow:", help="Starts the connector on the machine running Streamlit."):
        try:
            st.session_state["connector_process"] = subprocess.Popen(
                [sys.executable, "-m", "ai_eod_assistant.local_connector"],
                cwd=Path(__file__).resolve().parent.parent,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            st.success("Local connector started. Scan your workspace now.")
        except OSError as exc:
            st.error(f"Could not start the local connector: {exc}")
    default_path = str(Path.cwd())
    workspace_path = st.text_input("Workspace folder", value=st.session_state.get("workspace_path", default_path), key="workspace_path")
    since_date = st.date_input("Find files modified since", value=date.today(), key="workspace_since")
    connector_url = st.text_input("Local connector URL", value=st.session_state.get("ollama_connector_url", "http://127.0.0.1:8765"), key="ollama_connector_url", help="Use the connector running on this computer, or a private VPN address for a hosted app.")
    with service_context() as service:
        tasks = service.active_tasks()
    task_options = {"No task selected": None, **{f"{task.title} (#{task.id})": task for task in tasks}}
    selected_task = st.selectbox("Task this monitoring activity belongs to", list(task_options))
    if st.button("Scan selected workspace", type="primary", icon=":material/folder_open:"):
        try:
            since = datetime.combine(since_date, time.min).astimezone()
            if connector_url.strip():
                changes = scan_remote_workspace(connector_url, workspace_path, since)
            else:
                changes = scan_workspace(workspace_path, since)
            st.session_state["workspace_changes"] = changes
            st.session_state["workspace_evidence"] = format_workspace_evidence(changes)
        except (OSError, ValueError) as exc:
            st.error(f"Could not scan workspace: {exc}")

    changes = st.session_state.get("workspace_changes", [])
    if changes:
        st.metric("Files modified", len(changes))
        st.dataframe(
            [
                {
                    "Project": item.project_name,
                    "File": item.relative_path,
                    "Type": item.language_hint,
                    "Modified (UTC)": item.modified_at.isoformat(),
                }
                for item in changes
            ],
            hide_index=True,
        )
        with st.expander("Review workspace evidence", expanded=True):
            st.code(st.session_state["workspace_evidence"])
        if st.button("Save reviewed workspace activity", type="primary", icon=":material/save:"):
            task = task_options[selected_task]
            evidence = st.session_state["workspace_evidence"]
            if task:
                task_context = f"Task context: {task.title}"
                if task.description:
                    task_context += f" - {task.description}"
                evidence = f"{task_context}\n{evidence}"
            with service_context() as service:
                service.add_workspace_activity(evidence)
            st.success("Workspace activity saved as cautious evidence.")
    elif "workspace_changes" in st.session_state:
        st.info("No file modifications found in the selected time range.")


def render_integrations() -> None:
    st.header("External activity import")
    st.caption("Connect another tool safely by exporting a summary from that tool and importing only the activity you want included. This MVP does not silently observe other applications.")
    source = st.text_input("Source application", placeholder="e.g., Jira, GitHub, Figma, VS Code extension")
    content = st.text_area("Reviewed activity summary", height=180, placeholder="Paste an exported task or activity summary here.")
    if st.button("Save imported activity", type="primary", icon=":material/upload:"):
        if not source.strip() or not content.strip():
            st.warning("Enter both the source application and a reviewed activity summary.")
        else:
            with service_context() as service:
                service.add_external_activity(source, content)
            st.success("Imported activity saved as evidence.")


def render_generate_eod() -> None:
    st.header("Generate EOD")
    report_date = st.date_input("Report date", value=date.today())
    settings = get_settings()
    mode = st.session_state.get("ai_mode") or settings.ai_mode
    api_key = st.session_state.get("gemini_api_key") or settings.gemini_api_key
    model = st.session_state.get("ai_model") or (settings.gemini_model if mode == "Online (Gemini)" else settings.ollama_model)
    ollama_base_url = st.session_state.get("ollama_base_url") or settings.ollama_base_url
    with service_context() as service:
        preview = service.build_preview(report_date)
    evidence = preview.evidence
    with st.expander("Evidence that will be sent to Gemini", expanded=True):
        st.code(evidence or "No confirmed evidence for this date yet.")
    if st.button("Generate and save EOD", type="primary"):
        try:
            provider = build_provider(mode, gemini_api_key=api_key, model=model, ollama_base_url=ollama_base_url)
            with service_context() as service:
                saved_report = service.generate_and_save_eod(report_date, provider, f"gemini:{model}")
            st.session_state["last_generated_report"] = saved_report.content
            st.success("EOD generated and saved.")
        except Exception as exc:  # noqa: BLE001 - UI should show friendly provider failures.
            st.error(f"Could not generate EOD: {exc}")
    report_content = st.session_state.get("last_generated_report", "")
    if report_content:
        st.markdown(report_content)
        render_speech_controls(report_content, key="latest_report_tts")


def render_history() -> None:
    st.header("EOD History")
    with service_context() as service:
        current_user = st.session_state["auth_user"]
        if current_user.role == "admin":
            with get_connection() as connection:
                members = team_members(connection, current_user.team_id)
            member_options = {"All members": None, **{str(member["username"]): int(member["id"]) for member in members}}
            with st.form("history_filters"):
                selected_member = st.selectbox("Member", list(member_options))
                selected_date = st.date_input("Date", value=None)
                search_text = st.text_input("Search reports", placeholder="Search member or EOD text")
                st.form_submit_button("Apply filters", icon=":material/search:")
            reports = service.search_team_reports(member_options[selected_member], selected_date, search_text)
        else:
            reports = service.recent_reports(30)
    if not reports:
        st.info("No EOD reports saved yet.")
    for report in reports:
        owner = f" · {report.username}" if report.username else ""
        with st.expander(f"{report.date.isoformat()} — {report.ai_provider}{owner}"):
            st.markdown(report.content)
            render_speech_controls(report.content, key=f"report_tts_{report.id}")


def render_settings() -> None:
    st.header("Settings")
    settings = get_settings()
    st.caption("API keys are kept in memory for this Streamlit session or loaded from .env. They are not saved to SQLite.")
    mode = st.selectbox("AI mode", ["Online (Gemini)", "Offline (Ollama)"], index=["Online (Gemini)", "Offline (Ollama)"].index(st.session_state.get("ai_mode", settings.ai_mode)))
    api_key = st.text_input("Gemini API key", value=st.session_state.get("gemini_api_key", ""), type="password", disabled=mode != "Online (Gemini)")
    model_default = settings.gemini_model if mode == "Online (Gemini)" else settings.ollama_model
    model = st.text_input("Model name", value=st.session_state.get("ai_model", model_default))
    ollama_base_url = st.text_input("Ollama server URL", value=st.session_state.get("ollama_base_url", settings.ollama_base_url), disabled=mode != "Offline (Ollama)")
    if mode == "Offline (Ollama)":
        st.info("Install Ollama, start its server, then run `ollama pull llama3.2:3b`. This downloads a free local model once; generation then stays on this computer.")
        st.link_button("Download Ollama", "https://ollama.com/download", icon=":material/download:")
    if st.button("Apply settings"):
        st.session_state["gemini_api_key"] = api_key.strip()
        st.session_state["ai_mode"] = mode
        st.session_state["ai_model"] = model.strip() or model_default
        st.session_state["ollama_base_url"] = ollama_base_url.strip() or settings.ollama_base_url
        with service_context() as service:
            service.save_ai_settings(mode, st.session_state["ai_model"], st.session_state["ollama_base_url"])
        st.success("Settings applied for this session.")


def main() -> None:
    st.set_page_config(page_title="AI EOD Assistant", page_icon=":material/description:", layout="wide")
    st.session_state.setdefault("voice_transcript", "")
    if "auth_user" not in st.session_state:
        render_login()
        return
    page = render_app_shell()
    if page == "Dashboard":
        render_dashboard()
    elif page == "Add activity":
        render_add_activity()
    elif page == "Workspace activity":
        render_workspace_monitor()
    elif page == "External activity":
        render_integrations()
    elif page == "Generate EOD":
        render_generate_eod()
    elif page == "EOD history":
        render_history()
    elif page == "Team administration":
        render_team_administration()
    else:
        render_settings()


if __name__ == "__main__":
    main()
