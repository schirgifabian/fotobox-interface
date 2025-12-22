# ui_components.py

import streamlit as st
import textwrap
from sheets_helpers import get_data_event, get_spreadsheet, get_fleet_data_parallel

# -----------------------------------------------------------------------------
# GLOBAL STYLING (PERFEKTIONIERT + DASHBOARD UI)
# -----------------------------------------------------------------------------
MODERN_CSS = """
<style>
/* 1. App-Container & Reset */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

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

/* --------------------------------------------------------------------------
   NEU: DASHBOARD STYLES (Hero Card & Animationen)
   -------------------------------------------------------------------------- */

/* Pulsierende Animation für Status-Punkte */
@keyframes pulse-green {
    0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }
    70% { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
    100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}
@keyframes pulse-blue {
    0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.4); }
    70% { box-shadow: 0 0 0 10px rgba(59, 130, 246, 0); }
    100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
}

.status-dot {
    height: 12px;
    width: 12px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 8px;
    flex-shrink: 0;
}
.status-pulse-green {
    background-color: #10B981;
    animation: pulse-green 2s infinite;
}
.status-pulse-blue {
    background-color: #3B82F6;
    animation: pulse-blue 2s infinite;
}
.status-static-red {
    background-color: #EF4444;
}

/* Die große Dashboard-Karte */
.dashboard-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 20px;
    padding: 24px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    margin-bottom: 24px;
}

/* Grid Layout für Metriken innerhalb der Karte */
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-top: 24px;
    padding-top: 24px;
    border-top: 1px solid #F1F5F9;
}

.metric-item {
    text-align: center;
}

.metric-label {
    font-size: 0.75rem;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 600;
    margin-bottom: 4px;
}

.metric-value {
    font-size: 1.25rem;
    font-weight: 700;
    color: #1E293B;
}

.metric-sub {
    font-size: 0.7rem;
    color: #64748B;
    margin-top: 2px;
}

/* Custom Progress Bar */
.progress-bg {
    background-color: #F1F5F9;
    border-radius: 99px;
    height: 12px;
    width: 100%;
    margin-top: 8px;
    overflow: hidden;
}
.progress-fill {
    height: 100%;
    border-radius: 99px;
    transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Device Cards Styles (Legacy) */
.device-card {
    background: white;
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 12px;
    border: 1px solid #E2E8F0;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
    position: relative;
    min-height: 190px; 
    height: auto;
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.device-header { display: flex; align-items: flex-start; margin-bottom: 12px; padding-right: 0px; }
.device-icon-box { width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 24px; margin-right: 16px; flex-shrink: 0; }
.device-content { display: flex; flex-direction: column; justify-content: center; padding-top: 2px; }
.device-title-label { font-size: 0.7rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; margin-bottom: 4px; }
.device-status-text { font-size: 1.1rem; font-weight: 700; color: #1E293B; line-height: 1.2; }
.device-description { font-size: 0.85rem; color: #64748B; line-height: 1.5; font-weight: 400; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.status-badge-absolute { position: absolute; top: 24px; right: 24px; padding: 4px 10px; border-radius: 6px; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; background: #F1F5F9; }

</style>
"""

def inject_custom_css():
    st.markdown(MODERN_CSS, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# CORE COMPONENTS
# -----------------------------------------------------------------------------

def render_hero_card(
    status_mode: str,
    display_text: str,
    display_color: str,
    timestamp: str,
    heartbeat_info: str,
    media_remaining: int,
    max_prints: int,
    forecast_str: str,
    end_time_str: str,
    cost_txt: str
):
    """
    Rendert EINE große Karte (Hero Widget).
    FIX: textwrap.dedent verhindert, dass HTML als Code-Block angezeigt wird.
    """
    
    # 1. Icon & Animation Logic
    pulse_class = ""
    
    if status_mode == "printing":
        pulse_class = "status-pulse-blue"
        dot_color = "#3B82F6"
    elif status_mode == "ready":
        pulse_class = "status-pulse-green"
        dot_color = "#10B981"
    elif status_mode == "error":
        pulse_class = "status-static-red"
        dot_color = "#EF4444"
    else:
        # Fallback
        pulse_class = "status-dot" 
        dot_color = "#F59E0B" if "orange" in display_color or "yellow" in display_color else "#64748B"

    clean_text = display_text.replace('✅ ', '').replace('🔴 ', '').replace('⚠️ ', '').replace('🖨️ ', '').replace('⏳ ', '')

    # 2. Progress Bar Logic
    if not max_prints or max_prints <= 0:
        pct = 0
    else:
        pct = max(0, min(100, int((media_remaining / max_prints) * 100)))
    
    if pct < 10: bar_color = "#EF4444" 
    elif pct < 25: bar_color = "#F59E0B" 
    else: bar_color = "#3B82F6" 

    icon_char = '📸'
    if status_mode == 'printing': icon_char = '🖨️'
    elif status_mode == 'error': icon_char = '🔧'
    elif status_mode == 'low_paper': icon_char = '⚠️'
    elif status_mode == 'cooldown': icon_char = '❄️'

    icon_bg = f"{dot_color}15" 

    # 3. HTML Zusammenbauen (Mit textwrap.dedent!)
    # WICHTIG: Das f"""...""" muss direkt am Rand stehen oder mit dedent bereinigt werden.
html_content = f"""
    <div class="dashboard-card">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
                <div style="display: flex; align-items: center; margin-bottom: 8px;">
                    <span class="{pulse_class} status-dot" style="{ 'background-color:' + dot_color if 'pulse' not in pulse_class else '' }"></span>
                    <span style="font-size: 0.8rem; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em;">System Status</span>
                </div>
                <div style="font-size: 2rem; font-weight: 800; color: #1E293B; line-height: 1.1; margin-bottom: 6px;">
                    {clean_text}
                </div>
                <div style="font-size: 0.8rem; color: #94A3B8; display: flex; align-items: center; gap: 4px;">
                    <span>🕒</span> {timestamp} {heartbeat_info}
                </div>
            </div>
            <div style="background: {icon_bg}; color: {dot_color}; width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 24px;">
                 {icon_char}
            </div>
        </div>
        <div style="margin-top: 24px;">
            <div style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 6px; font-weight: 500; color: #475569;">
                <span>Verbrauch ({pct}%)</span>
                <span>{media_remaining} / {max_prints} Bilder</span>
            </div>
            <div class="progress-bg">
                <div class="progress-fill" style="width: {pct}%; background-color: {bar_color};"></div>
            </div>
        </div>
        <div class="metrics-grid">
            <div class="metric-item">
                <div class="metric-label">Papier</div>
                <div class="metric-value" style="color: {bar_color}">{media_remaining}</div>
                <div class="metric-sub">Verbleibend</div>
            </div>
            <div class="metric-item" style="border-left: 1px solid #F1F5F9; border-right: 1px solid #F1F5F9;">
                <div class="metric-label">Prognose</div>
                <div class="metric-value">{forecast_str.split(' ')[0]}</div>
                <div class="metric-sub">{ " ".join(forecast_str.split(' ')[1:]) if 'Min' in forecast_str else forecast_str }</div>
                <div class="metric-sub" style="font-size: 0.65rem; color: #CBD5E1; margin-top:0;">{end_time_str}</div>
            </div>
            <div class="metric-item">
                <div class="metric-label">Kosten</div>
                <div class="metric-value">{cost_txt}</div>
                <div class="metric-sub">Laufend</div>
            </div>
        </div>
    </div>
    """
    
    # HIER IST DER FIX:
    st.markdown(textwrap.dedent(html_content), unsafe_allow_html=True)


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

    col1, col2 = st.columns(2)
    with col1:
        click_left = st.button(btn_left_label, key=btn_left_key, use_container_width=True)
    with col2:
        click_right = st.button(btn_right_label, key=btn_right_key, use_container_width=True)
    
    st.write("") 
    return click_left, click_right


def render_fleet_overview(PRINTERS: dict):
    st.markdown("### 📸 Alle Fotoboxen")
    printers_secrets = st.secrets.get("printers", {})
    fleet_data = get_fleet_data_parallel(PRINTERS, printers_secrets)

    cols = st.columns(len(PRINTERS))
    idx = 0
    for name, cfg in PRINTERS.items():
        data = fleet_data.get(name)
        
        last_ts = "N/A"
        status_color = "#64748B" # Grau
        status_bg = "#F1F5F9"
        status_msg = "Offline / ??"
        media_str = "–"

        if data:
            media_str = data.get("media_str", "?")
            last_ts = data.get("timestamp", "N/A")
            state = data.get("state", "unknown")
            
            if state == "error":
                status_color = "#EF4444" 
                status_bg = "#FEF2F2"
                status_msg = "Störung"
            elif state == "printing":
                status_color = "#3B82F6"
                status_bg = "#EFF6FF"
                status_msg = "Druckt"
            elif state == "ready":
                status_color = "#10B981"
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
