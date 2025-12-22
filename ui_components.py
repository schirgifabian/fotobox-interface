# ui_components.py

import streamlit as st
from sheets_helpers import get_data_event, get_spreadsheet
from status_logic import HEARTBEAT_WARN_MINUTES

# -----------------------------------------------------------------------------
# GLOBAL STYLING
# -----------------------------------------------------------------------------
MODERN_CSS = """
<style>
/* 1. App-Container aufräumen */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.block-container {
    padding-top: 2rem !important;
    padding-bottom: 5rem !important;
    max-width: 900px;
}

/* 2. Hintergrund & Typografie */
.stApp {
    background-color: #F8FAFC; /* Slate-50 */
}

h1, h2, h3 {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #0F172A; /* Slate-900 */
    font-weight: 700;
}

/* 3. Cards Design (Apple Style) */
.stExpander {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 16px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    margin-bottom: 1rem;
    overflow: hidden;
}

div[data-testid="stExpanderDetails"] {
    background: #FFFFFF;
}

/* 4. Buttons Modernisieren */
div.stButton > button {
    width: 100%;
    border-radius: 12px;
    border: 1px solid #E2E8F0;
    background-color: #FFFFFF;
    color: #1E293B;
    font-weight: 600;
    padding: 0.5rem 1rem;
    transition: all 0.2s ease;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
}

div.stButton > button:hover {
    border-color: #3B82F6;
    color: #3B82F6;
    transform: translateY(-1px);
    box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.1);
}

div.stButton > button:active {
    background-color: #EFF6FF;
    transform: translateY(0);
}

/* 5. Metrics (KPIs) */
div[data-testid="stMetric"] {
    background-color: #FFFFFF;
    padding: 16px;
    border-radius: 16px;
    border: 1px solid #E2E8F0;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
    text-align: center;
}
div[data-testid="stMetricLabel"] {
    justify-content: center;
    font-size: 0.85rem;
    color: #64748B;
}
div[data-testid="stMetricValue"] {
    font-size: 1.5rem;
    font-weight: 700;
    color: #0F172A;
}

/* 6. Custom Classes für HTML-Komponenten */
.device-card {
    background: white;
    border-radius: 20px;
    padding: 24px;
    margin-bottom: 16px;
    border: 1px solid #E2E8F0;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    display: flex;
    justify-content: space-between;
    align-items: center;
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
}

.status-badge {
    padding: 4px 12px;
    border-radius: 99px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.toast-container {
    z-index: 99999;
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
    """
    Rendert eine moderne 'Smart Home'-style Karte.
    Nutzt HTML für das Layout und native st.buttons für die Interaktion.
    """
    
    # Farblogik
    if state == "on":
        color_theme = "#10B981" # Emerald 500
        bg_theme = "#ECFDF5"    # Emerald 50
        icon = icon_on
        status_text = title_on
    elif state == "off":
        color_theme = "#64748B" # Slate 500
        bg_theme = "#F1F5F9"    # Slate 100
        icon = icon_off
        status_text = title_off
    else:
        color_theme = "#F59E0B" # Amber 500
        bg_theme = "#FFFBEB"    # Amber 50
        icon = icon_unknown
        status_text = title_unknown

    # HTML Container Start
    st.markdown(
        f"""
        <div class="device-card">
            <div style="display:flex; align-items:center;">
                <div class="device-icon-box" style="background-color: {bg_theme}; color: {color_theme};">
                    {icon}
                </div>
                <div>
                    <div style="font-size: 0.75rem; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600;">
                        {section_title}
                    </div>
                    <div style="font-size: 1.1rem; font-weight: 700; color: #0F172A; margin-top: 2px;">
                        {status_text}
                    </div>
                    <div style="font-size: 0.85rem; color: #94A3B8; margin-top: 4px; line-height: 1.3;">
                        {description}
                    </div>
                </div>
            </div>
            <div style="text-align:right;">
                <span class="status-badge" style="background-color:{bg_theme}; color:{color_theme}; border: 1px solid {color_theme}30;">
                    {badge_prefix}: {state.upper()}
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Die Buttons rendern wir darunter in einem Container, 
    # damit sie visuell zur Karte gehören aber technisch funktionieren.
    col1, col2 = st.columns(2)
    with col1:
        click_left = st.button(btn_left_label, key=btn_left_key, use_container_width=True)
    with col2:
        click_right = st.button(btn_right_label, key=btn_right_key, use_container_width=True)
    
    # Abstandshalter
    st.write("") 

    return click_left, click_right


def render_fleet_overview(PRINTERS: dict):
    """
    Schöne Grid-Ansicht für alle Boxen.
    """
    st.markdown("### 📸 Alle Fotoboxen")

    printers_secrets = st.secrets.get("printers", {})
    
    # Grid Layout erstellen
    cols = st.columns(len(PRINTERS))
    
    idx = 0
    for name, cfg in PRINTERS.items():
        sheet_id = printers_secrets.get(cfg["key"], {}).get("sheet_id")
        
        # Default Werte
        last_ts = "N/A"
        status_color = "#64748B" # Grau
        status_bg = "#F1F5F9"
        status_msg = "Offline"
        media_str = "–"
        
        if sheet_id:
            try:
                df = get_data_event(sheet_id)
                if not df.empty:
                    last = df.iloc[-1]
                    last_ts = str(last.get("Timestamp", ""))[-8:] # Nur Uhrzeit
                    raw_status = str(last.get("Status", "")).lower()
                    
                    try:
                        media_val = int(last.get("MediaRemaining", 0)) * cfg.get("media_factor", 1)
                        media_str = f"{media_val} Bilder"
                    except:
                        media_str = "?"

                    # Einfache Ampel-Logik für die Übersicht
                    if "error" in raw_status or "jam" in raw_status or "end" in raw_status:
                        status_color = "#EF4444" # Rot
                        status_bg = "#FEF2F2"
                        status_msg = "Störung"
                    elif "printing" in raw_status:
                        status_color = "#3B82F6" # Blau
                        status_bg = "#EFF6FF"
                        status_msg = "Druckt"
                    else:
                        status_color = "#10B981" # Grün
                        status_bg = "#ECFDF5"
                        status_msg = "Bereit"
                        
            except Exception:
                pass

        with cols[idx]:
            st.markdown(
                f"""
                <div style="
                    background: white;
                    border: 1px solid #E2E8F0;
                    border-radius: 16px;
                    padding: 20px;
                    text-align: center;
                    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
                    height: 100%;
                ">
                    <div style="font-weight: 700; color: #0F172A; margin-bottom: 8px;">{name}</div>
                    
                    <div style="
                        display: inline-block;
                        background: {status_bg};
                        color: {status_color};
                        padding: 4px 12px;
                        border-radius: 99px;
                        font-size: 0.8rem;
                        font-weight: 600;
                        margin-bottom: 12px;
                    ">
                        {status_msg}
                    </div>
                    
                    <div style="font-size: 0.8rem; color: #64748B; margin-bottom: 4px;">
                        Verbleibend: <strong>{media_str}</strong>
                    </div>
                    <div style="font-size: 0.7rem; color: #94A3B8;">
                        Update: {last_ts}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
        
        idx += 1


def render_health_overview(aqara_enabled: bool, dsr_enabled: bool):
    items = []
    
    # Logik prüfen
    sheets_ok = False
    try:
        if st.session_state.get("sheet_id"):
            _ = get_spreadsheet(st.session_state.get("sheet_id"))
            sheets_ok = True
    except: pass
    
    ntfy_ok = bool(st.session_state.get("ntfy_topic")) and st.session_state.get("ntfy_active", False)
    
    items = [
        ("Sheets", sheets_ok),
        ("Push", ntfy_ok),
        ("Strom", aqara_enabled),
        ("Sperre", dsr_enabled)
    ]
    
    # HTML Bauen für eine kompakte Statusleiste
    html_items = ""
    for name, ok in items:
        color = "#10B981" if ok else "#CBD5E1" # Grün oder ausgegraut
        icon = "●" 
        html_items += f"""
        <div style="display:flex; align-items:center; gap:6px; margin-right:16px;">
            <span style="color:{color}; font-size:12px;">{icon}</span>
            <span style="font-size:12px; font-weight:600; color:#475569;">{name}</span>
        </div>
        """
        
    st.markdown(
        f"""
        <div style="
            display: flex; 
            flex-wrap: wrap; 
            background: white; 
            padding: 10px 16px; 
            border-radius: 99px; 
            border: 1px solid #E2E8F0;
            width: fit-content;
            margin-bottom: 20px;
        ">
            {html_items}
        </div>
        """,
        unsafe_allow_html=True
    )


def render_status_help(warning_threshold: int):
    with st.expander("ℹ️  Hilfe & Legende"):
        st.markdown(
            f"""
            **Status-Bedeutungen:**
            
            - <span style="color:#10B981">●</span> **Bereit:** Alles OK.
            - <span style="color:#F59E0B">●</span> **Papier fast leer:** Unter {warning_threshold} Bilder.
            - <span style="color:#EF4444">●</span> **Störung:** Druckerfehler (Papierstau, Band fehlt).
            - <span style="color:#64748B">●</span> **Veraltet:** Seit >{HEARTBEAT_WARN_MINUTES} Min. keine Daten.
            
            ---
            **Funktionen:**
            - **Aqara:** Schaltet den Strom der gesamten Box hart an/aus.
            - **Lockscreen:** Verhindert neue Sessions am Bildschirm.
            """
        , unsafe_allow_html=True)
