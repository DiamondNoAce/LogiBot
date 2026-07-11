from __future__ import annotations

import base64
import html
import json
from pathlib import Path
from typing import Any

import streamlit as st

from storage import kb_loader as kb_json


def apply_global_styles() -> None:
    """Zentrales Hohenheim-inspiriertes Styling für alle Ansichten."""
    st.markdown(
        """
        <style>
            :root {
                --hoh-navy: #003B70;
                --hoh-blue: #004A87;
                --hoh-blue-2: #0069AA;
                --hoh-light-blue: #D8EEF7;
                --hoh-cyan: #42B7C8;
                --hoh-bg: #EEF2F6;
                --hoh-card: #FFFFFF;
                --hoh-border: #D8E2EC;
                --hoh-text: #1F2A36;
                --hoh-muted: #667085;
                --hoh-yellow: #E4E642;
                --hoh-green: #8FBF26;
                --hoh-shadow: 0 8px 24px rgba(0, 59, 112, 0.08);
            }

            html, body, [data-testid="stAppViewContainer"] {
                background: var(--hoh-bg) !important;
                color: var(--hoh-text) !important;
                font-family: Arial, Helvetica, sans-serif;
            }

            [data-testid="stHeader"] {
                background: rgba(238, 242, 246, 0.92) !important;
                backdrop-filter: blur(8px);
            }

            .block-container {
                max-width: 1360px;
                padding-top: 1.1rem;
                padding-bottom: 4rem;
            }

            [data-testid="stSidebar"] {
                background: #F7F9FC !important;
                border-right: 1px solid var(--hoh-border);
            }
            [data-testid="stSidebar"] * { color: var(--hoh-text) !important; }
            [data-testid="stSidebar"] h1,
            [data-testid="stSidebar"] h2,
            [data-testid="stSidebar"] h3 {
                color: var(--hoh-navy) !important;
            }

            .hoh-shell {
                border-radius: 0 0 14px 14px;
                margin-bottom: 1.4rem;
                box-shadow: var(--hoh-shadow);
                overflow: visible;
                background: var(--hoh-card);
                border: 1px solid var(--hoh-border);
            }

            .hoh-brand {
                background: #ffffff;
                border-top: 4px solid var(--hoh-cyan);
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 1.35rem 1.8rem 1.35rem 1.8rem;
                min-height: 112px;
                box-sizing: border-box;
            }

            .hoh-brand-left {
                display: flex;
                align-items: center;
                gap: 1.0rem;
                min-width: 0;
            }

            .hoh-logo-img {
                width: 74px;
                height: 74px;
                object-fit: contain;
                flex: 0 0 74px;
            }

            .hoh-logo-text {
                line-height: 1.06;
                min-width: 420px;
                overflow: visible;
                display: flex;
                flex-direction: column;
                justify-content: center;
            }

            .hoh-uni-line {
                display: block;
                font-family: Georgia, 'Times New Roman', serif;
                color: var(--hoh-blue);
                font-weight: 700;
                letter-spacing: 0.14em;
                font-size: 24px;
                line-height: 1.02;
                text-transform: uppercase;
                white-space: nowrap;
            }

            .hoh-subbrand {
                color: var(--hoh-muted);
                font-size: 13px;
                margin-top: 0.48rem;
                white-space: nowrap;
            }

            .hoh-project-badge {
                background: var(--hoh-light-blue);
                color: var(--hoh-navy);
                border: 1px solid #B9D9EA;
                border-radius: 999px;
                padding: 0.42rem 0.8rem;
                font-size: 13px;
                font-weight: 700;
                white-space: nowrap;
            }

            .hoh-nav-bar {
                background: var(--hoh-navy);
                padding: 0.55rem 0.85rem 0.7rem 0.85rem;
                border-top: 1px solid rgba(255,255,255,0.12);
            }

            .hoh-nav-hint {
                color: rgba(255,255,255,0.78);
                font-size: 12px;
                margin: 0.1rem 0 0.45rem 0.1rem;
            }

            .hoh-nav-button-row {
                width: 100%;
            }

            .hoh-nav-button-row div.stButton > button,
            .hoh-nav-button-row div[data-testid="stButton"] > button {
                width: 100% !important;
                min-height: 46px !important;
                padding: 0.45rem 0.35rem !important;
                font-size: 13px !important;
                line-height: 1.15 !important;
                text-align: center !important;
                white-space: nowrap !important;
                word-break: keep-all !important;
                overflow-wrap: normal !important;
                hyphens: none !important;
            }

            .hoh-nav-button-row div[data-testid="column"] {
                min-width: 0 !important;
            }

            .hoh-page-title {
                background: #ffffff;
                padding: 1.2rem 1.35rem 1.25rem 1.35rem;
                border-top: 1px solid rgba(0,0,0,0.05);
            }

            .hoh-page-title h1 {
                margin: 0;
                color: var(--hoh-navy);
                font-size: 34px;
                line-height: 1.15;
                font-weight: 800;
            }

            .hoh-page-title p {
                margin: 0.45rem 0 0 0;
                color: var(--hoh-muted);
                font-size: 15px;
                line-height: 1.55;
            }

            h1, h2, h3, h4 {
                color: var(--hoh-navy) !important;
                letter-spacing: -0.015em;
            }

            .hero-title {
                font-size: 36px;
                font-weight: 800;
                color: var(--hoh-navy);
                margin-bottom: 0.35rem;
            }
            .hero-subtitle {
                color: var(--hoh-muted);
                font-size: 15px;
                line-height: 1.55;
                margin-bottom: 1.2rem;
            }

            .card,
            .prop-panel,
            div[data-testid="stExpander"] details {
                border: 1px solid var(--hoh-border) !important;
                border-radius: 12px !important;
                background: var(--hoh-card) !important;
                box-shadow: 0 3px 10px rgba(0, 59, 112, 0.04);
            }
            .card {
                padding: 1rem 1.1rem;
                margin-bottom: 1rem;
            }

            .answer-card {
                border: 1px solid #BBD7EA;
                border-left: 6px solid var(--hoh-blue-2);
                border-radius: 10px;
                background: #ffffff;
                padding: 1rem 1.1rem;
                margin-top: 1rem;
                box-shadow: 0 3px 10px rgba(0, 59, 112, 0.05);
            }
            .answer-title {
                font-size: 13px;
                text-transform: uppercase;
                color: var(--hoh-blue);
                font-weight: 800;
                letter-spacing: 0.3px;
                margin-bottom: 0.55rem;
            }
            .answer-text { color: var(--hoh-text); font-size: 15px; line-height: 1.58; }

            .step-card {
                display: flex;
                gap: 12px;
                border: 1px solid var(--hoh-border);
                border-left: 5px solid var(--hoh-blue);
                border-radius: 8px;
                background-color: #ffffff;
                padding: 12px 14px;
                margin-bottom: 10px;
                box-shadow: 0 2px 8px rgba(0, 59, 112, 0.04);
            }
            .step-number {
                width: 34px;
                height: 34px;
                min-width: 34px;
                border-radius: 8px;
                background-color: var(--hoh-blue);
                color: #ffffff !important;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 800;
            }
            .step-title { font-size: 14px; font-weight: 800; color: var(--hoh-blue); margin-bottom: 4px; }
            .step-phase { font-size: 12px; color: var(--hoh-muted); margin-bottom: 4px; }
            .step-text { font-size: 13px; color: #2f3645; line-height: 1.45; }

            .graph-toolbar {
                display: flex;
                gap: 0.5rem;
                flex-wrap: wrap;
                align-items: center;
                padding: 0.75rem;
                border: 1px solid var(--hoh-border);
                border-radius: 12px;
                background: #ffffff;
                margin-bottom: 1rem;
            }
            .prop-panel { padding: 1rem; position: sticky; top: 1rem; }
            .prop-title { font-size: 18px; font-weight: 800; color: var(--hoh-navy); margin-bottom: 0.25rem; }
            .prop-muted { font-size: 13px; color: var(--hoh-muted); margin-bottom: 1rem; line-height: 1.45; }
            .selection-pill {
                display: inline-block;
                padding: 0.25rem 0.55rem;
                border-radius: 999px;
                background: var(--hoh-light-blue);
                color: var(--hoh-navy);
                font-size: 12px;
                font-weight: 700;
                margin-bottom: 0.6rem;
            }
            .canvas-help { color: var(--hoh-muted); font-size: 13px; line-height: 1.45; margin: 0.25rem 0 0.75rem 0; }
            .tiny-note { color: var(--hoh-muted); font-size: 12px; }

            .view-info {
                border: 1px solid #BBD7EA;
                border-left: 6px solid var(--hoh-blue-2);
                background: #F2FAFD;
                border-radius: 12px;
                padding: 0.95rem 1rem;
                margin: 0.75rem 0 1.25rem 0;
                color: var(--hoh-text);
                line-height: 1.55;
                box-shadow: 0 2px 8px rgba(0, 59, 112, 0.04);
            }
            .view-info-title { font-size: 14px; font-weight: 800; color: var(--hoh-blue); margin-bottom: 0.25rem; }
            .view-info-text { font-size: 14px; color: var(--hoh-text); }

            div.stButton > button,
            div[data-testid="stFormSubmitButton"] button {
                background: var(--hoh-blue) !important;
                color: #ffffff !important;
                border: 1px solid var(--hoh-blue) !important;
                border-radius: 4px !important;
                font-weight: 700 !important;
                box-shadow: none !important;
            }
            div.stButton > button:hover,
            div[data-testid="stFormSubmitButton"] button:hover {
                background: var(--hoh-navy) !important;
                border-color: var(--hoh-navy) !important;
                color: #ffffff !important;
            }
            div.stButton > button[kind="secondary"] {
                background: #ffffff !important;
                color: var(--hoh-blue) !important;
                border-color: #BBD7EA !important;
            }
            div.stButton > button[kind="secondary"]:hover {
                background: #EAF5FA !important;
                color: var(--hoh-navy) !important;
                border-color: var(--hoh-blue) !important;
            }

            [data-testid="stRadio"] label,
            label, .stTextInput label, .stTextArea label, .stSelectbox label, .stNumberInput label {
                color: var(--hoh-text) !important;
                font-weight: 600;
            }
            input, textarea, select, input:focus, textarea:focus {
                color: var(--hoh-text) !important;
                background-color: #ffffff !important;
                caret-color: var(--hoh-text) !important;
            }

            div[data-baseweb="select"] > div {
                background-color: #ffffff !important;
                border-color: var(--hoh-border) !important;
            }

            code {
                color: var(--hoh-text) !important;
                background-color: #E9F1F7 !important;
                border-radius: 4px;
                padding: 2px 5px;
                border: 1px solid #D5E3EE;
            }

            .stAlert {
                border-radius: 10px !important;
            }

            hr {
                border-color: var(--hoh-border) !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )



def _asset_as_data_uri(relative_path: str) -> str:
    """Lädt ein lokales Asset als Data-URI, damit es im HTML-Header angezeigt werden kann."""
    try:
        root = Path(__file__).resolve().parents[1]
        path = root / relative_path
        data = path.read_bytes()
        suffix = path.suffix.lower().lstrip(".") or "png"
        mime = "image/png" if suffix == "png" else f"image/{suffix}"
        return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")
    except Exception:
        return ""


def _set_active_view(view: str) -> None:
    st.session_state["active_view"] = view
    st.session_state["sidebar_view"] = view


def render_hohenheim_header(active_view: str = "", nav_map: dict[str, str] | None = None) -> None:
    """Zeigt eine Hohenheim-inspirierte Kopfzeile mit Uni-Branding und klickbarer Navigation."""
    logo_uri = _asset_as_data_uri("assets/hohenheim_seal.png")
    logo_html = (
        f'<img class="hoh-logo-img" src="{logo_uri}" alt="Universität Hohenheim Logo" />'
        if logo_uri
        else '<div class="hoh-logo-img" style="border:2px solid #004A87;border-radius:999px;display:flex;align-items:center;justify-content:center;font-weight:800;color:#004A87;">UH</div>'
    )

    st.markdown(
        f"""
        <div class="hoh-shell">
            <div class="hoh-brand">
                <div class="hoh-brand-left">
                    {logo_html}
                    <div class="hoh-logo-text">
                        <span class="hoh-uni-line">Universität</span>
                        <span class="hoh-uni-line">Hohenheim</span>
                        <div class="hoh-subbrand">KIM · Regelbasiertes Assistenzsystem</div>
                    </div>
                </div>
                <div class="hoh-project-badge">IT-Anleitungsassistent</div>
            </div>
        """,
        unsafe_allow_html=True,
    )

    if nav_map:
        st.markdown('<div class="hoh-nav-bar"><div class="hoh-nav-hint">Ansicht wechseln</div><div class="hoh-nav-button-row">', unsafe_allow_html=True)
        labels = list(nav_map.keys())
        cols = st.columns(len(labels), gap="small")
        for i, label in enumerate(labels):
            target = nav_map[label]
            active = target == active_view
            with cols[i]:
                st.button(
                    label,
                    key=f"hoh_nav_{target}",
                    type="primary" if active else "secondary",
                    use_container_width=True,
                    on_click=_set_active_view,
                    args=(target,),
                )
        st.markdown('</div></div>', unsafe_allow_html=True)

    st.markdown(
        f"""
            <div class="hoh-page-title">
                <h1>{esc(active_view or 'KIM Assistenzsystem')}</h1>
                <p>Modulares Expertensystem für IT-Anleitungen mit JSON-Rule-Engine, Entscheidungsnetzen und optionaler lokaler LLM-Unterstützung.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def esc(value: Any) -> str:
    return html.escape(str(value)).replace("\n", "<br>")


def split_lines(text: str) -> list[str]:
    return [line.strip() for line in str(text).splitlines() if line.strip()]


def json_area(label: str, value: Any, key: str, height: int = 220) -> Any:
    raw = st.text_area(label, value=json.dumps(value, ensure_ascii=False, indent=2), height=height, key=key)
    return json.loads(raw)


def select_service(key: str, active_only: bool = False) -> dict[str, Any] | None:
    services = kb_json.get_services(active_only=active_only)
    if not services:
        st.warning("Keine Dienste vorhanden.")
        return None
    return st.selectbox("Dienst auswählen", services, format_func=lambda s: f"{s.get('name')} ({s.get('key')})", key=key)


def select_system(service_key: str, key: str, active_only: bool = False) -> dict[str, Any] | None:
    systems = kb_json.get_systems(service_key, active_only=active_only)
    if not systems:
        st.warning("Keine Systeme für diesen Dienst vorhanden.")
        return None
    return st.selectbox("System auswählen", systems, format_func=lambda s: f"{s.get('name')} ({s.get('key')})", key=key)


def select_step(service_key: str, system_key: str, key: str, active_only: bool = False) -> dict[str, Any] | None:
    steps = kb_json.get_steps(service_key, system_key, active_only=active_only)
    if not steps:
        st.warning("Keine Schritte für dieses System vorhanden.")
        return None
    return st.selectbox("Schritt auswählen", steps, format_func=lambda s: f"{s.get('number')} · {s.get('title')}", key=key)


def render_step_card(step: dict[str, Any]) -> None:
    st.markdown(
        f"""
        <div class="step-card">
            <div class="step-number">{esc(step.get('number'))}</div>
            <div>
                <div class="step-title">{esc(step.get('title'))}</div>
                <div class="step-phase">Phase: {esc(step.get('phase'))}</div>
                <div class="step-text">{esc(step.get('instruction'))}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_answer(title: str, text: str) -> None:
    st.markdown(
        f"""
        <div class="answer-card">
            <div class="answer-title">{esc(title)}</div>
            <div class="answer-text">{esc(text)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )



def render_view_info(title: str, text: str) -> None:
    """Zeigt oben in jeder Ansicht eine kurze Erklärung zur Nutzung."""
    st.markdown(
        f"""
        <div class="view-info">
            <div class="view-info-title">{esc(title)}</div>
            <div class="view-info-text">{esc(text)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )



# ============================================================
# Interaktiver eduroam-Installationsdurchlauf
# ============================================================
