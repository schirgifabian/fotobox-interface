# ui_components.py

import streamlit as st
from sheets_helpers import get_data_event, get_spreadsheet
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
    padding-top: 2rem !important;
    padding-bottom: 5rem !important;
    max-width: 950px; /* Etwas breiter für mehr Platz */
}

/* 2. Typografie - Weniger "Fett", mehr Eleganz */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-weight: 400; /* Standard ist jetzt normal, nicht fett */
    color: #334155;   /* Slate-700, weicher als Schwarz */
}

h1, h2, h3 {
    color: #0F172A;
    font-weight: 600; /* Überschriften kräftig, aber nicht extrabold */
    letter-spacing: -0.01em;
}

/* 3. Sidebar Styling (Cleaner Look) */
section[data-testid="stSidebar"] {
    background-color: #FFFFFF; /* Weiß statt Grau */
    border-right: 1px solid #F1F5F9;
}

/* Sidebar Widgets anpassen */
section[data-testid="stSidebar"] .stRadio label {
    font-weight: 500 !important;
}
div[data-testid="stRadio"] > div {
    gap: 0.5rem;
}

/* 4. Cards Design (Apple Style) */
.stExpander {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.02);
}

div[data-testid="stExpanderDetails"] {
    background: #FFFFFF;
}

/* 5. Buttons (Dezent & Clean) */
div.stButton > button {
    width: 100%;
    border-radius: 10px;
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
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}

div.stButton > button:active {
    transform: translateY(0);
}

/* 6. Metrics (KPIs) - Filigraner */
div[data-testid="stMetric"] {
    background-color: #FFFFFF;
    padding: 16px 20px; /* Mehr Padding innen */
    border-radius: 16px;
    border: 1px solid #E2E8F0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
    text-align: center;
}
div[data-testid="stMetricLabel"] {
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    color: #64748B !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
div[data-testid="stMetricValue"] {
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    margin-top: 4px;
}

/* 7. Custom HTML Device Card Classes */
.device-card {
    background: white;
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 12px;
    border: 1px solid #E2E8F0;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.03);
    position: relative; /* Wichtig für absolute Positionierung des Badges */
    
    /* Layout Fixes */
    display: flex;
    flex-direction: column;
    justify-content: center;
    
    /* ERZWINGT GLEICHE HÖHE: */
    min-height: 150px; 
}

.device-header {
    display: flex;
    align-items: center;
    margin-bottom: 8px;
    padding-right: 80px; /* Platz für das Badge reservieren, damit Text nicht überlappt */
}

.device-icon-box {
    width: 44px;
    height: 44px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    margin-right: 14px;
    flex-shrink: 0;
}

.device-title-label {
    font-size: 0.7rem; 
    color: #94A3B8; 
    text-transform: uppercase; 
    letter-spacing: 0.08em; 
    font-weight: 600;
    margin-bottom: 2px;
}

.device-status-text {
    font-size: 1.05rem; 
    font-weight: 700; 
    color: #1E293B;
}

.device-description {
    font-size: 0.8rem; 
    color: #64748B; 
    line-height: 1.4;
    font-weight: 400;
    margin-top: 4px;
}

/* Badge absolut oben rechts positionieren */
.status-badge-absolute {
    position: absolute;
    top: 20px;
    right: 20px;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    white-space: nowrap; /* Verhindert Umbruch */
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
    Rendert eine moderne Karte mit fixed height und absoluter Badge-Positionierung.
    Dadurch "springen" die Layouts nicht und Texte werden nicht abgeschnitten.
    """
    
    # Farblogik
    if state == "on":
        color_theme = "#059669" # Emerald 600
        bg_theme = "#ECFDF5"    # Emerald 50
        border_theme = "rgba(5, 150, 105, 0.1)"
        icon = icon_on
        status_text = title_on
    elif state == "off":
        color_theme = "#64748B" # Slate 500
        bg_theme = "#F8FAFC"    # Slate 50
        border_theme = "#E2E8F0"
        icon = icon_off
        status_text = title_off
    else:
        color_theme = "#D97706" # Amber 600
        bg_theme = "#FFFBEB"    # Amber 50
        border_theme = "rgba(217, 119, 6, 0.1)"
        icon = icon_unknown
        status_text = title_unknown

    # HTML Container Start
    st.markdown(
        f"""
        <div class="device-card">
            
            <div class="status-badge-absolute" 
                 style="background-color:{bg_theme}; color:{color_theme}; border: 1px solid {border_theme};">
                {badge_prefix}: {state.upper()}
            </div>

            <div class="device-header">
                <div class="device-icon-box" style="background-color: {bg_theme}; color: {color_theme};">
                    {icon}
                </div>
                <div>
                    <div class="device-title-label">
                        {section_title}
                    </div>
                    <div class="device-status-text">
                        {status_text}
                    </div>
                </div>
            </div>
            
            <div class="device-description">
                {description}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Buttons
    col1, col2 = st.columns(2)
    with col1:
        click_left = st.button(btn_left_label, key=btn_left_key, use_container_width=True)
    with col2:
        click_right = st.button(btn_right_label, key=btn_right_key, use_container_width=True)
    
    st.write("") # Kleiner Spacer

    return click_left, click_right


def render_fleet_overview(PRINTERS: dict):
    """
    Grid-Ansicht für alle Boxen.
    """
    st.markdown("### 📸 Alle Fotoboxen")

    printers_secrets = st.secrets.get("printers", {})
    cols = st.columns(len(PRINTERS))
    
    idx = 0
    for name, cfg in PRINTERS.items():
        sheet_id = printers_secrets.get(cfg["key"], {}).get("sheet_id")
        
        last_ts = "N/A"
        status_color = "#64748B"
        status_bg = "#F1F5F9"
        status_msg = "Offline"
        media_str = "–"
        
        if sheet_id:
            try:
                df = get_data_event(sheet_id)
                if not df.empty:
                    last = df.iloc[-1]
                    last_ts = str(last.get("Timestamp", ""))[-8:]
                    raw_status = str(last.get("Status", "")).lower()
                    
                    try:
                        media_val = int(last.get("MediaRemaining", 0)) * cfg.get("media_factor", 1)
                        media_str = f"{media_val} Bilder"
                    except:
                        media_str = "?"

                    if "error" in raw_status or "jam" in raw_status or "end" in raw_status:
                        status_color = "#EF4444"
                        status_bg = "#FEF2F2"
                        status_msg = "Störung"
                    elif "printing" in raw_status:
                        status_color = "#3B82F6"
                        status_bg = "#EFF6FF"
                        status_msg = "Druckt"
                    else:
                        status_color = "#10B981"
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
                    box-shadow: 0 2px 4px rgba(0,0,0,0.02);
                    height: 100%;
                    min-height: 180px; /* Auch hier gleiche Höhe erzwingen */
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
                """,
                unsafe_allow_html=True
            )
        
        idx += 1


def render_health_overview(aqara_enabled: bool, dsr_enabled: bool):
    """
    Kompakte Statusleiste oben.
    """
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
    
    html_items = ""
    for name, ok in items:
        color = "#10B981" if ok else "#CBD5E1" 
        icon = "●" 
        html_items += f"""
        <div style="display:flex; align-items:center; gap:6px; margin-right:16px;">
            <span style="color:{color}; font-size:12px;">{icon}</span>
            <span style="font-size:12px; font-weight:500; color:#475569;">{name}</span>
        </div>
        """
        
    st.markdown(
        f"""
        <div style="
            display: flex; 
            flex-wrap: wrap; 
            background: white; 
            padding: 8px 16px; 
            border-radius: 99px; 
            border: 1px solid #E2E8F0;
            width: fit-content;
            margin-bottom: 24px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.02);
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
            <div style="font-size: 0.9rem; color: #475569;">
            
            **Status-Bedeutungen:**
            
            - <span style="color:#10B981">●</span> **Bereit:** Alles OK.
            - <span style="color:#F59E0B">●</span> **Papier fast leer:** Unter {warning_threshold} Bilder.
            - <span style="color:#EF4444">●</span> **Störung:** Druckerfehler (Papierstau, Band fehlt).
            - <span style="color:#64748B">●</span> **Veraltet:** Seit >{HEARTBEAT_WARN_MINUTES} Min. keine Daten.
            
            ---
            **Funktionen:**
            - **Aqara:** Schaltet den Strom der gesamten Box hart an/aus.
            - **Lockscreen:** Verhindert neue Sessions am Bildschirm.
            
            </div>
            """
        , unsafe_allow_html=True)
