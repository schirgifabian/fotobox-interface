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

/* 4. Buttons (Global) */
div.stButton > button {
    width: 100%;
    border-radius: 12px;
    border: 1px solid #E2E8F0;
    background-color: #FFFFFF;
    color: #475569;
    font-weight: 600;
    padding: 0.6rem 1rem;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    transition: all 0.2s ease;
}
div.stButton > button:hover {
    border-color: #CBD5E1;
    background-color: #F8FAFC;
    color: #0F172A;
    transform: translateY(-1px);
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}

/* --------------------------------------------------------------------------
   DASHBOARD STYLES (Hero Card & Mini Cards)
   -------------------------------------------------------------------------- */

/* Pulsierende Animationen */
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
@keyframes pulse-orange {
    0% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.4); }
    70% { box-shadow: 0 0 0 10px rgba(245, 158, 11, 0); }
    100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); }
}
@keyframes pulse-red {
    0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
    70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
    100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
}
@keyframes pulse-gray {
    0% { box-shadow: 0 0 0 0 rgba(100, 116, 139, 0.4); }
    70% { box-shadow: 0 0 0 10px rgba(100, 116, 139, 0); }
    100% { box-shadow: 0 0 0 0 rgba(100, 116, 139, 0); }
}

.status-dot {
    height: 10px;
    width: 10px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 8px;
    flex-shrink: 0;
}

.status-pulse-green { background-color: #10B981; animation: pulse-green 2s infinite; }
.status-pulse-blue { background-color: #3B82F6; animation: pulse-blue 2s infinite; }
.status-pulse-orange { background-color: #F59E0B; animation: pulse-orange 2s infinite; }
.status-pulse-red { background-color: #EF4444; animation: pulse-red 2s infinite; }
.status-pulse-gray { background-color: #64748B; animation: pulse-gray 2s infinite; }

/* SHARED CARD DESIGN */
.dashboard-card, .mini-card, .control-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 20px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    margin-bottom: 24px;
}

/* HERO CARD SPECIFICS */
.dashboard-card { padding: 24px; }

/* MINI CARD (Fleet) SPECIFICS */
.mini-card {
    padding: 20px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    height: 100%;
    min-height: 160px;
    transition: transform 0.2s ease;
}
.mini-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05);
}

/* CONTROL CARD (Toggle) SPECIFICS */
.control-card {
    padding: 20px;
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 12px; /* Buttons sind separat darunter */
}

/* Metrics Grid in Hero */
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-top: 24px;
    padding-top: 24px;
    border-top: 1px solid #F1F5F9;
}
.metric-item { text-align: center; }
.metric-label { font-size: 0.75rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; margin-bottom: 4px; }
.metric-value { font-size: 1.25rem; font-weight: 700; color: #1E293B; }
.metric-sub { font-size: 0.7rem; color: #64748B; margin-top: 2px; }

/* Progress Bar */
.progress-bg {
    background-color: #F1F5F9;
    border-radius: 99px;
    height: 8px;
    width: 100%;
    margin-top: 12px;
    overflow: hidden;
}
.progress-fill {
    height: 100%;
    border-radius: 99px;
    transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

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
    Rendert die große Hauptkarte.
    """
    
    # 1. Icon & Animation Logic
    pulse_class = ""
    dot_color = ""
    
    if status_mode == "printing":
        pulse_class = "status-pulse-blue"
        dot_color = "#3B82F6"
    elif status_mode == "ready":
        pulse_class = "status-pulse-green"
        dot_color = "#10B981"
    elif status_mode == "error":
        pulse_class = "status-pulse-red"
        dot_color = "#EF4444"
    else:
        if "orange" in display_color or "yellow" in display_color:
            pulse_class = "status-pulse-orange"
            dot_color = "#F59E0B"
        else:
            pulse_class = "status-pulse-gray" 
            dot_color = "#64748B"

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

    icon_bg = f"{dot_color}15" # Hex Transparency 

    # 3. HTML Zusammenbauen
    html_content = f"""
<div class="dashboard-card">
    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
        <div>
            <div style="display: flex; align-items: center; margin-bottom: 12px;">
                <span class="{pulse_class} status-dot"></span>
                <span style="font-size: 0.75rem; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.1em;">System Status</span>
            </div>
            <div style="font-size: 1.75rem; font-weight: 800; color: #1E293B; line-height: 1.1; margin-bottom: 8px;">
                {clean_text}
            </div>
            <div style="font-size: 0.85rem; color: #94A3B8; display: flex; align-items: center; gap: 6px;">
                <span>🕒</span> {timestamp} {heartbeat_info}
            </div>
        </div>
        <div style="background: {icon_bg}; color: {dot_color}; width: 56px; height: 56px; border-radius: 16px; display: flex; align-items: center; justify-content: center; font-size: 28px;">
                {icon_char}
        </div>
    </div>
    
    <div style="margin-top: 32px;">
        <div style="display: flex; justify-content: space-between; font-size: 0.85rem; font-weight: 600; color: #475569; margin-bottom: 4px;">
            <span>Verbrauch ({pct}%)</span>
            <span>{media_remaining} / {max_prints}</span>
        </div>
        <div class="progress-bg">
            <div class="progress-fill" style="width: {pct}%; background-color: {bar_color};"></div>
        </div>
    </div>
    
    <div class="metrics-grid">
        <div class="metric-item">
            <div class="metric-label">Papier</div>
            <div class="metric-value" style="color: {bar_color}">{media_remaining}</div>
            <div class="metric-sub">Bilder</div>
        </div>
        <div class="metric-item" style="border-left: 1px solid #F1F5F9; border-right: 1px solid #F1F5F9;">
            <div class="metric-label">Prognose</div>
            <div class="metric-value">{forecast_str.split(' ')[0]}</div>
            <div class="metric-sub">{ " ".join(forecast_str.split(' ')[1:]) if 'Min' in forecast_str else forecast_str }</div>
            <div style="font-size: 0.65rem; color: #CBD5E1; margin-top:2px;">{end_time_str}</div>
        </div>
        <div class="metric-item">
            <div class="metric-label">Kosten</div>
            <div class="metric-value">{cost_txt}</div>
            <div class="metric-sub">Laufend</div>
        </div>
    </div>
</div>
"""
    
    st.markdown(html_content, unsafe_allow_html=True)


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
    Rendert eine Steuerungs-Karte im gleichen Look wie das Dashboard.
    """
    # Farblogik
    if state == "on":
        color_theme = "#059669" # Emerald
        bg_theme = "#ECFDF5"
        icon = icon_on
        status_text = title_on
        pulse_class = "status-pulse-green"
    elif state == "off":
        color_theme = "#64748B" # Slate
        bg_theme = "#F1F5F9"
        icon = icon_off
        status_text = title_off
        pulse_class = "status-pulse-gray"
    else:
        color_theme = "#D97706" # Amber
        bg_theme = "#FFFBEB"
        icon = icon_unknown
        status_text = title_unknown
        pulse_class = "status-pulse-orange"

    html_content = textwrap.dedent(f"""
        <div class="control-card">
            <div style="background-color: {bg_theme}; color: {color_theme}; min-width: 50px; height: 50px; border-radius: 14px; display: flex; align-items: center; justify-content: center; font-size: 24px;">
                {icon}
            </div>
            <div style="flex-grow: 1;">
                <div style="display:flex; align-items:center; margin-bottom: 2px;">
                    <div class="status-dot {pulse_class}" style="width:8px; height:8px; margin-right:6px;"></div>
                    <div style="font-size: 0.7rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600;">{section_title}</div>
                </div>
                <div style="font-size: 1.1rem; font-weight: 700; color: #1E293B;">{status_text}</div>
                <div style="font-size: 0.8rem; color: #64748B; margin-top: 2px;">{description}</div>
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
    """
    Zeigt alle Fotoboxen als 'Mini Hero Cards' an.
    """
    st.markdown("### 📸 Alle Fotoboxen")
    printers_secrets = st.secrets.get("printers", {})
    fleet_data = get_fleet_data_parallel(PRINTERS, printers_secrets)

    cols = st.columns(len(PRINTERS))
    idx = 0
    for name, cfg in PRINTERS.items():
        data = fleet_data.get(name)
        
        last_ts = "N/A"
        media_val = "0"
        
        # Defaults
        pulse_class = "status-pulse-gray"
        dot_color = "#64748B"
        status_text = "Offline"
        
        if data:
            last_ts = data.get("timestamp", "N/A")
            state = data.get("state", "unknown")
            media_val = data.get("media_str", "0").replace(" Bilder", "")
            
            if state == "error":
                pulse_class = "status-pulse-red"
                dot_color = "#EF4444"
                status_text = "Störung"
            elif state == "printing":
                pulse_class = "status-pulse-blue"
                dot_color = "#3B82F6"
                status_text = "Druckt"
            elif state == "ready":
                pulse_class = "status-pulse-green"
                dot_color = "#10B981"
                status_text = "Bereit"

        with cols[idx]:
            card_html = textwrap.dedent(f"""
                <div class="mini-card">
                    <div>
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
                            <div style="font-weight: 700; color: #0F172A; font-size: 0.95rem;">{name}</div>
                            <div class="status-dot {pulse_class}"></div>
                        </div>
                        
                        <div style="font-size: 2rem; font-weight: 800; color: #1E293B; letter-spacing: -0.02em;">
                            {media_val}
                        </div>
                        <div style="font-size: 0.75rem; color: #64748B; font-weight: 500;">Bilder verbleibend</div>
                    </div>
                    
                    <div style="margin-top: 20px; padding-top: 12px; border-top: 1px solid #F1F5F9; display:flex; justify-content: space-between; align-items:center;">
                        <span style="font-size: 0.7rem; color: {dot_color}; font-weight: 700; text-transform: uppercase;">{status_text}</span>
                        <span style="font-size: 0.7rem; color: #94A3B8;">{last_ts}</span>
                    </div>
                </div>
            """)
            st.markdown(card_html, unsafe_allow_html=True)
            
            # Button um zur Detailansicht zu springen (müsste man via Session State lösen, hier nur visuell)
            # st.button(f"Details", key=f"btn_{idx}", use_container_width=True) 
            
        idx += 1


def render_health_overview(aqara_enabled: bool, dsr_enabled: bool):
    """
    Kleine Pill-Indikatoren, jetzt etwas subtiler.
    """
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
        html_items += f"""
        <div style="display:flex; align-items:center; gap:6px; margin-right:16px;">
            <span style="background-color:{color}; width:8px; height:8px; border-radius:50%;"></span>
            <span style="font-size:0.75rem; font-weight:600; color:#475569;">{name}</span>
        </div>"""
        
    st.markdown(f"""
        <div style="display: flex; flex-wrap: wrap; background: #FFFFFF; padding: 10px 20px; border-radius: 99px; border: 1px solid #E2E8F0; width: fit-content; margin-bottom: 24px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
            {html_items}
        </div>
    """, unsafe_allow_html=True)
