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

/* 4. Cards (Expander & Container) */
.stExpander {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}
div[data-testid="stExpanderDetails"] {
    background: #FFFFFF;
}

/* WICHTIG: Überschreibt den Standard st.container(border=True) Style, 
   damit er exakt wie die Dashboard-Hero-Card aussieht */
div[data-testid="stVerticalBlockBorderWrapper"] > div {
    border-radius: 20px !important;
    border: 1px solid #E2E8F0 !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
    background-color: #FFFFFF !important;
    padding: 24px !important;
}

/* 5. Buttons */
div.stButton > button {
    width: 100%;
    border-radius: 12px; /* Runder */
    border: 1px solid #E2E8F0;
    background-color: #F8FAFC; /* Leicht grau */
    color: #475569;
    font-weight: 600;
    padding: 0.6rem 1rem;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    transition: all 0.2s ease-in-out;
}
div.stButton > button:hover {
    border-color: #CBD5E1;
    background-color: #FFFFFF;
    color: #0F172A;
    transform: translateY(-1px);
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}

/* Primary Button Style (wenn type="primary") */
div.stButton > button[kind="primary"] {
    background-color: #3B82F6;
    color: white;
    border: 1px solid #2563EB;
}
div.stButton > button[kind="primary"]:hover {
    background-color: #2563EB;
    color: white;
}

/* --------------------------------------------------------------------------
   DASHBOARD STYLES (Hero Card & Animationen)
   -------------------------------------------------------------------------- */
/* ... (Animationen bleiben gleich wie vorher) ... */
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
    height: 12px;
    width: 12px;
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
.metric-item { text-align: center; }
.metric-label { font-size: 0.75rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; margin-bottom: 4px; }
.metric-value { font-size: 1.25rem; font-weight: 700; color: #1E293B; }
.metric-sub { font-size: 0.7rem; color: #64748B; margin-top: 2px; }

/* Custom Progress Bar */
.progress-bg { background-color: #F1F5F9; border-radius: 99px; height: 12px; width: 100%; margin-top: 8px; overflow: hidden; }
.progress-fill { height: 100%; border-radius: 99px; transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1); }

a.dashboard-link { text-decoration: none !important; color: inherit !important; display: block; transition: transform 0.2s ease, box-shadow 0.2s ease; }
a.dashboard-link:hover .dashboard-card { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05); border-color: #CBD5E1; }
</style>
"""

def inject_custom_css():
    st.markdown(MODERN_CSS, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# NEUE KOMPONENTE: Card Header für Admin-Bereiche
# -----------------------------------------------------------------------------
def render_card_header(icon: str, title: str, subtitle: str, color_class: str = "blue"):
    """
    Rendert den oberen Teil einer Card (Icon + Text) innerhalb eines st.containers.
    """
    
    # Farb-Mapping für Icon-Hintergrund
    colors = {
        "blue":  {"bg": "#EFF6FF", "fg": "#3B82F6"},
        "green": {"bg": "#ECFDF5", "fg": "#10B981"},
        "orange":{"bg": "#FFFBEB", "fg": "#F59E0B"},
        "red":   {"bg": "#FEF2F2", "fg": "#EF4444"},
        "slate": {"bg": "#F1F5F9", "fg": "#64748B"},
    }
    c = colors.get(color_class, colors["slate"])
    
    html = f"""
    <div style="display: flex; align-items: center; margin-bottom: 20px;">
        <div style="
            background: {c['bg']}; 
            color: {c['fg']}; 
            width: 48px; height: 48px; 
            border-radius: 12px; 
            display: flex; align-items: center; justify-content: center; 
            font-size: 24px;
            margin-right: 16px;
            flex-shrink: 0;
        ">
            {icon}
        </div>
        <div>
            <div style="font-size: 1.1rem; font-weight: 700; color: #1E293B; line-height: 1.2;">
                {title}
            </div>
            <div style="font-size: 0.85rem; color: #64748B; margin-top: 2px;">
                {subtitle}
            </div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# CORE COMPONENTS (Hero & co)
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

    icon_bg = f"{dot_color}15" 

    # 3. HTML Zusammenbauen
    html_content = f"""
<div class="dashboard-card">
    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
        <div>
            <div style="display: flex; align-items: center; margin-bottom: 8px;">
                <span class="{pulse_class} status-dot"></span>
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
    st.markdown(html_content, unsafe_allow_html=True)


def render_fleet_overview(PRINTERS: dict):
    st.markdown("### 📸 Alle Fotoboxen")
    printers_secrets = st.secrets.get("printers", {})
    fleet_data = get_fleet_data_parallel(PRINTERS, printers_secrets)

    cols = st.columns(len(PRINTERS))
    idx = 0
    for name, cfg in PRINTERS.items():
        data = fleet_data.get(name)
        
        last_ts = "N/A"
        status_color = "#64748B" 
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
                    border-radius: 20px;
                    padding: 24px;
                    text-align: center;
                    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
                    height: 200px;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                ">
                    <div style="font-weight: 700; color: #0F172A; margin-bottom: 12px; font-size: 1.1rem;">{name}</div>
                    <div style="
                        display: inline-block;
                        background: {status_bg};
                        color: {status_color};
                        padding: 6px 16px;
                        border-radius: 99px;
                        font-size: 0.8rem;
                        font-weight: 600;
                        margin-bottom: 16px;
                        letter-spacing: 0.05em;
                        text-transform: uppercase;
                    ">
                        {status_msg}
                    </div>
                    <div style="font-size: 1.1rem; color: #334155; margin-bottom: 6px; font-weight: 600;">
                        {media_str}
                    </div>
                    <div style="font-size: 0.75rem; color: #94A3B8;">
                        Update: {last_ts}
                    </div>
                </div>
            """)
            st.markdown(card_html, unsafe_allow_html=True)
        idx += 1


def render_link_card(url: str, title: str, subtitle: str, icon: str = "☁️"):
    if not url: return
    html_content = f"""
<a href="{url}" target="_blank" class="dashboard-link">
<div class="dashboard-card" style="display: flex; justify-content: space-between; align-items: center; padding: 24px;">
<div>
<div style="display: flex; align-items: center; margin-bottom: 6px;">
<span style="font-size: 0.75rem; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em;">External Link</span>
</div>
<div style="font-size: 1.5rem; font-weight: 800; color: #1E293B; line-height: 1.1;">
{title}
</div>
<div style="font-size: 0.9rem; color: #64748B; margin-top: 4px; font-weight: 500;">
{subtitle} ➜
</div>
</div>
<div style="background: #F1F5F9; color: #3B82F6; width: 64px; height: 64px; border-radius: 16px; display: flex; align-items: center; justify-content: center; font-size: 32px;">
{icon}
</div>
</div>
</a>
"""
    st.markdown(html_content, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# SCREENSAVER / ZEN MODE
# -----------------------------------------------------------------------------
def render_screensaver_ui(
    status_mode: str,
    media_remaining: int,
    display_text: str,
    display_color: str,
    timestamp: str,
    max_prints: int
):
    """
    Rendert eine Vollbild-Ansicht im Darkmode.
    """
    
    # Farbe basierend auf Status festlegen
    color_map = {
        "green": "#10B981", # Smaragdgrün
        "blue": "#3B82F6",  # Blau
        "orange": "#F59E0B",# Bernstein
        "red": "#EF4444",   # Rot
        "gray": "#64748B"   # Grau
    }
    accent_color = color_map.get(display_color, "#64748B")
    
    # Prozentbalken Berechnung
    if not max_prints or max_prints <= 0:
        pct = 0
    else:
        pct = max(0, min(100, int((media_remaining / max_prints) * 100)))

    # CSS HACKS: Sidebar ausblenden, Hintergrund schwarz, Header weg
    screensaver_css = f"""
    <style>
        /* Alles Schwarz erzwingen */
        .stApp {{
            background-color: #000000 !important;
            color: #E2E8F0 !important;
        }}
        
        /* Sidebar komplett ausblenden */
        section[data-testid="stSidebar"] {{
            display: none !important;
        }}
        
        /* Header Decoration Line oben ausblenden */
        header {{
            visibility: hidden !important;
        }}
        
        /* Footer ausblenden */
        footer {{
            visibility: hidden !important;
        }}

        /* Container Styling */
        .screensaver-container {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 90vh; /* Fast volle Höhe */
            text-align: center;
        }}

        .big-number {{
            font-size: 12rem; /* Riesig */
            font-weight: 800;
            line-height: 1;
            color: {accent_color};
            text-shadow: 0 0 30px {accent_color}40; /* Leichter Glow */
            font-variant-numeric: tabular-nums;
        }}

        .label-text {{
            font-size: 1.5rem;
            text-transform: uppercase;
            letter-spacing: 0.2em;
            color: #64748B;
            margin-bottom: 20px;
        }}

        .status-pill {{
            background-color: #1E293B;
            border: 1px solid #334155;
            color: {accent_color};
            padding: 10px 30px;
            border-radius: 50px;
            font-size: 1.2rem;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 10px;
            margin-top: 40px;
        }}

        .status-dot {{
            height: 12px;
            width: 12px;
            background-color: {accent_color};
            border-radius: 50%;
            box-shadow: 0 0 10px {accent_color};
        }}

        .meta-info {{
            margin-top: 20px;
            color: #475569;
            font-family: monospace;
        }}
        
        /* Exit Button Styling leicht transparent machen */
        div.stButton > button {{
            background-color: #1E293B !important;
            color: #94A3B8 !important;
            border: 1px solid #334155 !important;
        }}
        div.stButton > button:hover {{
            border-color: #EF4444 !important;
            color: #EF4444 !important;
        }}
    </style>
    """
    st.markdown(screensaver_css, unsafe_allow_html=True)

    # HTML Aufbau
    html = f"""
    <div class="screensaver-container">
        <div class="label-text">Verbleibende Bilder</div>
        <div class="big-number">{media_remaining}</div>
        
        <div class="status-pill">
            <span class="status-dot"></span>
            {display_text.replace('✅', '').replace('⚠️', '').replace('🔴', '').strip()}
        </div>

        <div class="meta-info">
            Zuletzt aktualisiert: {timestamp}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
