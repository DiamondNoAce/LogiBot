from __future__ import annotations

import html
import json
from typing import Any

import streamlit as st

from storage import kb_loader as kb_json


def apply_global_styles() -> None:
    st.markdown(
        """
        <style>
            html, body, [data-testid="stAppViewContainer"] { background-color: #ffffff; color: #111827; }
            [data-testid="stSidebar"] { background-color: #f4f5f9; }
            [data-testid="stSidebar"] * { color: #111827 !important; }
            .block-container { max-width: 1200px; padding-top: 2.6rem; padding-bottom: 4rem; }
            label, .stTextInput label, .stTextArea label, .stSelectbox label, .stNumberInput label { color: #111827 !important; }
            input, textarea, select, input:focus, textarea:focus { color: #111827 !important; background-color: #ffffff !important; caret-color: #111827 !important; }
            .hero-title { font-size: 40px; font-weight: 800; color: #272838; margin-bottom: 0.4rem; }
            .hero-subtitle { color: #5c6270; font-size: 15px; line-height: 1.55; margin-bottom: 1.2rem; }
            .card { border: 1px solid #e3e8f0; border-radius: 12px; background: #ffffff; padding: 1rem 1.1rem; margin-bottom: 1rem; box-shadow: 0 1px 2px rgba(0,0,0,0.03); }
            .answer-card { border: 1px solid #d8e5f3; border-left: 5px solid #0d8bd6; border-radius: 10px; background: #ffffff; padding: 1rem 1.1rem; margin-top: 1rem; }
            .answer-title { font-size: 13px; text-transform: uppercase; color: #0b6faa; font-weight: 800; letter-spacing: 0.3px; margin-bottom: 0.55rem; }
            .answer-text { color: #1f2937; font-size: 15px; line-height: 1.58; }
            .step-card { display: flex; gap: 12px; border: 1px solid #e3e8f0; border-left: 4px solid #2f55a4; border-radius: 8px; background-color: #ffffff; padding: 12px 14px; margin-bottom: 10px; }
            .step-number { width: 34px; height: 34px; min-width: 34px; border-radius: 8px; background-color: #2f55a4; color: #ffffff !important; display: flex; align-items: center; justify-content: center; font-weight: 800; }
            .step-title { font-size: 14px; font-weight: 800; color: #244b9b; margin-bottom: 4px; }
            .step-phase { font-size: 12px; color: #6b7280; margin-bottom: 4px; }
            .step-text { font-size: 13px; color: #2f3645; line-height: 1.45; }
            code { color: #111827 !important; background-color: #e8eef8 !important; border-radius: 4px; padding: 2px 4px; }

            .graph-toolbar { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; padding: 0.75rem; border: 1px solid #e5e7eb; border-radius: 12px; background: #f8fafc; margin-bottom: 1rem; }
            .prop-panel { border: 1px solid #e5e7eb; border-radius: 14px; background: #ffffff; padding: 1rem; position: sticky; top: 1rem; }
            .prop-title { font-size: 18px; font-weight: 800; color: #111827; margin-bottom: 0.25rem; }
            .prop-muted { font-size: 13px; color: #6b7280; margin-bottom: 1rem; line-height: 1.45; }
            .selection-pill { display: inline-block; padding: 0.25rem 0.55rem; border-radius: 999px; background: #e8eef8; color: #1f3b78; font-size: 12px; font-weight: 700; margin-bottom: 0.6rem; }
            .canvas-help { color: #6b7280; font-size: 13px; line-height: 1.45; margin: 0.25rem 0 0.75rem 0; }
            .tiny-note { color: #6b7280; font-size: 12px; }
            .view-info {
                border: 1px solid #dbeafe;
                border-left: 5px solid #2563eb;
                background: #eff6ff;
                border-radius: 12px;
                padding: 0.9rem 1rem;
                margin: 0.75rem 0 1.25rem 0;
                color: #1f2937;
                line-height: 1.55;
            }
            .view-info-title {
                font-size: 14px;
                font-weight: 800;
                color: #1e3a8a;
                margin-bottom: 0.25rem;
            }
            .view-info-text {
                font-size: 14px;
                color: #1f2937;
            }
        </style>
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
