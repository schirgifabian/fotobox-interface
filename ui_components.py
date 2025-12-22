# ui_components.py

import streamlit as st
import textwrap
from sheets_helpers import get_data_event, get_spreadsheet, get_fleet_data_parallel
from status_logic import HEARTBEAT_WARN_MINUTES

# -----------------------------------------------------------------------------
# GLOBAL STYLING (PERFEKTIONIERT)
# -----------------------------------------------------------------------------
MODERN_CSS = """
<style>
/* 1. App-Container & Reset */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.block-container {
    padding-top: 1rem !important;
    padding-bottom: 5rem !important;
    max-width: 1000px;
}

/* 2. Typografie */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #334155;
    font-weight: 400;
}

h1, h2, h3 {
    color: #0F172A;
    font-weight: 600;
    letter-spacing: -0.01em;
}

/* 3. Sidebar Cleaner */
section[data-testid="stSidebar"] {
    background-color: #FFFFFF;
    border-right: 1px solid #F1F5F9;
}

/* 4. Cards (Expander) */
.stExpander {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}
div[data-testid="stExpanderDetails"] {
    background: #FFFFFF;
}

/* 5. Buttons */
div.stButton > button {
    width: 100%;
    border-radius: 8px;
    border: 1px solid #E2E8F0;
    background-color: #FFFFFF;
    color: #475569;
    font-weight: 500;
    padding: 0.5rem 1rem;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    transition: all 0.15s ease-in-out;
}
div.stButton > button:hover {
    border-color: #CBD5E1;
    background-color: #F8FAFC;
    color: #1E293B;
    transform: translateY(-1px);
}

/* 6. Metrics (Papierstatus) - HÖHE REPARIERT */
div[data-testid="stMetric"] {
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 16px !important;
    padding: 24px 16px !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.02) !important;
    text-align: center !important;
    
    /* FIX: Flexible Höhe für Mobile */
    min-height: 160px !important; 
    height: auto !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
    align-items: center !important;
}

div[data-testid="stMetricLabel"] {
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    color: #94A3B8 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    margin-bottom: 4px !important;
}
div[data-testid="stMetricValue"] {
    font-size: 1.8rem !important;
    font-weight: 700 !important;
    color: #0F172A !important;
}
/* Delta Indikator (die kleine Pille) */
div[data-testid="stMetricDelta"] {
    font-size: 0.8rem !important;
    margin-top: 8px !important;
    font-weight: 500 !important;
}

/* 7. DEVICE CARD STYLES */
.device-card {
    background: white;
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 12px;
    border: 1px solid #E2E8F0;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
    position: relative;
    
    /* Layout Fixes */
    display: flex;
    flex-direction: column;
    justify-content: center;
    
    /* FIX: Flexible Höhe statt fixer Höhe für Mobile-Optimierung (4.A) */
    min-height: 190px; 
    height: auto;
}

.device-header {
    display: flex;
    align-items: flex-start; 
    margin-bottom: 12px;
    padding-right: 0px; 
}

.device-icon-box {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    margin-right: 16px;
    flex-shrink: 0;
}

.device-content {
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding-top: 2px;
}

.device-title-label {
    font-size: 0.7rem; 
    color: #94A3B8; 
    text-transform: uppercase; 
    letter-spacing: 0.08em; 
    font-weight: 600;
    margin-bottom: 4px;
}

.device-status-text {
    font-size: 1.1rem; 
    font-weight: 700; 
    color: #1E293B;
    line-height: 1.2;
}

.device-description {
    font-size: 0.85rem; 
    color: #64748B; 
    line-height: 1.5;
    font-weight: 400;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

/* Badge absolut oben rechts */
.status-badge-absolute {
    position: absolute;
    top: 24px;
    right: 24px;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    background: #F1F5F9;
}

</style>
"""

def inject_custom_css():
    st.markdown(MODERN_CSS, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# HELPER COMPONENTS
# -----------------------------------------------------------------------------

def render_toggle_card(
    section_title: str,
    description: str,
    state: str,
    title_on: str,
    title_off: str,
    title_unknown: str,
    badge_prefix: str,
    icon_on: str,
    icon_off: str,
    icon_unknown: str,
    btn_left_label: str,
    btn_right_label: str,
    btn_left_key: str,
    btn_right_key: str,
):
    # Farblogik
    if state == "on":
        color_theme = "#059669" # Emerald
        bg_theme = "#ECFDF5"
        icon = icon_on
        status_text = title_on
        badge_border = "rgba(5, 150, 105, 0.1)"
    elif state == "off":
        color_theme = "#64748B" # Slate
        bg_theme = "#F8FAFC"
        icon = icon_off
        status_text = title_off
        badge_border = "#E2E8F0"
    else:
        color_theme = "#D97706" # Amber
        bg_theme = "#FFFBEB"
        icon = icon_unknown
        status_text = title_unknown
        badge_border = "rgba(217, 119, 6, 0.1)"

    # HTML sicher rendern mit dedent (Verhindert Code-Block-Fehler)
    html_content = textwrap.dedent(f"""
        <div class="device-card">
            <div class="status-badge-absolute" style="background-color:{bg_theme}; color:{color_theme}; border: 1px solid {badge_border};">
                {badge_prefix}: {state.upper()}
            </div>
            <div class="device-header">
                <div class="device-icon-box" style="background-color: {bg_theme}; color: {color_theme};">
                    {icon}
                </div>
                <div class="device-content">
                    <div class="device-title-label">{section_title}</div>
                    <div class="device-status-text">{status_text}</div>
                </div>
            </div>
            <div class="device-description">
                {description}
            </div>
        </div>
    """)
    st.markdown(html_content, unsafe_allow_html=True)

    # Buttons
    col1, col2 = st.columns(2)
    with col1:
        click_left = st.button(btn_left_label, key=btn_left_key, use_container_width=True)
    with col2:
        click_right = st.button(btn_right_label, key=btn_right_key, use_container_width=True)
    
    st.write("") 

    return click_left, click_right


def render_fleet_overview(PRINTERS: dict):
    """
    Rendert die Übersicht aller Drucker. 
    Nutzt 'get_fleet_data_parallel' für schnelle Ladezeiten.
    """
    st.markdown("### 📸 Alle Fotoboxen")

    printers_secrets = st.secrets.get("printers", {})
    
    # 1. Parallel Load: Alle Daten gleichzeitig holen
    # Dies verhindert, dass wir N mal warten müssen (N = Anzahl Drucker)
    fleet_data = get_fleet_data_parallel(PRINTERS, printers_secrets)

    cols = st.columns(len(PRINTERS))
    
    idx = 0
    for name, cfg in PRINTERS.items():
        
        # Daten aus dem parallelen Fetch holen
        data = fleet_data.get(name)
        
        # Defaults (falls Fehler oder Offline)
        last_ts = "N/A"
        status_color = "#64748B" # Grau
        status_bg = "#F1F5F9"
        status_msg = "Offline / ??"
        media_str = "–"

        if data:
            media_str = data.get("media_str", "?")
            last_ts = data.get("timestamp", "N/A")
            state = data.get("state", "unknown")
            
            # Farb-Logik basierend auf dem ermittelten State
            if state == "error":
                status_color = "#EF4444" # Rot
                status_bg = "#FEF2F2"
                status_msg = "Störung"
            elif state == "printing":
                status_color = "#3B82F6" # Blau
                status_bg = "#EFF6FF"
                status_msg = "Druckt"
            elif state == "ready":
                status_color = "#10B981" # Grün
                status_bg = "#ECFDF5"
                status_msg = "Bereit"

        with cols[idx]:
            card_html = textwrap.dedent(f"""
                <div style="
                    background: white;
                    border: 1px solid #E2E8F0;
                    border-radius: 16px;
                    padding: 20px;
                    text-align: center;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.02);
                    height: 180px;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                ">
                    <div style="font-weight: 700; color: #0F172A; margin-bottom: 12px; font-size: 1rem;">{name}</div>
                    <div style="
                        display: inline-block;
                        background: {status_bg};
                        color: {status_color};
                        padding: 4px 12px;
                        border-radius: 99px;
                        font-size: 0.75rem;
                        font-weight: 600;
                        margin-bottom: 12px;
                        letter-spacing: 0.05em;
                        text-transform: uppercase;
                    ">
                        {status_msg}
                    </div>
                    <div style="font-size: 0.9rem; color: #334155; margin-bottom: 4px; font-weight: 500;">
                        {media_str}
                    </div>
                    <div style="font-size: 0.7rem; color: #94A3B8;">
                        Update: {last_ts}
                    </div>
                </div>
            """)
            st.markdown(card_html, unsafe_allow_html=True)
        idx += 1


def render_health_overview(aqara_enabled: bool, dsr_enabled: bool):
    sheets_ok = False
    try:
        if st.session_state.get("sheet_id"):
            # Nur checken, ob das Objekt existiert/geladen werden kann
            _ = get_spreadsheet(st.session_state.get("sheet_id"))
            sheets_ok = True
    except: pass
    
    ntfy_ok = bool(st.session_state.get("ntfy_topic")) and st.session_state.get("ntfy_active", False)
    
    items = [("Sheets", sheets_ok), ("Push", ntfy_ok), ("Strom", aqara_enabled), ("Sperre", dsr_enabled)]
    
    html_items = ""
    for name, ok in items:
        color = "#10B981" if ok else "#CBD5E1" 
        html_items += f"""<div style="display:flex; align-items:center; gap:6px; margin-right:16px;"><span style="color:{color}; font-size:12px;">●</span><span style="font-size:12px; font-weight:500; color:#475569;">{name}</span></div>"""
        
    st.markdown(f"""<div style="display: flex; flex-wrap: wrap; background: white; padding: 8px 16px; border-radius: 99px; border: 1px solid #E2E8F0; width: fit-content; margin-bottom: 24px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">{html_items}</div>""", unsafe_allow_html=True)


def render_status_help(warning_threshold: int):
    with st.expander("ℹ️  Hilfe & Legende"):
        st.markdown(f"""
            <div style="font-size: 0.9rem; color: #475569;">
            **Status:** <span style="color:#10B981">●</span> Bereit &nbsp; <span style="color:#F59E0B">●</span> Papier < {warning_threshold} &nbsp; <span style="color:#EF4444">●</span> Störung &nbsp; <span style="color:#64748B">●</span> Veraltet
            </div>
        """, unsafe_allow_html=True)
