# ui_components.py

import streamlit as st
import textwrap
from sheets_helpers import get_data_event, get_spreadsheet, get_fleet_data_parallel

# -----------------------------------------------------------------------------
# GLOBAL STYLING (Sidebar + Dashboard + Animationen)
# -----------------------------------------------------------------------------
MODERN_CSS = """
<style>
/* 1. GRUNDGERÜST & SCHRIFTEN */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #1E293B; 
    background-color: #F8FAFC; 
}

/* 2. SIDEBAR - PROFISSIONELLER LOOK */
section[data-testid="stSidebar"] {
    background-color: #F1F5F9; 
    border-right: 1px solid #E2E8F0;
    padding-top: 1rem;
}

section[data-testid="stSidebar"] .block-container {
    padding-top: 1rem;
    padding-bottom: 2rem;
}

section[data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 12px !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.02) !important;
    padding: 16px !important;
    margin-bottom: 12px;
}

section[data-testid="stSidebar"] h1, 
section[data-testid="stSidebar"] h2, 
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] h4 {
    color: #64748B !important;
    font-size: 0.75rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    margin-bottom: 12px !important;
    margin-top: 0px !important;
    border: none !important;
}

section[data-testid="stSidebar"] .stCaption {
    color: #94A3B8;
    font-size: 0.7rem;
}

/* 3. BUTTONS & INPUTS */
div.stButton > button {
    border-radius: 8px;
    border: 1px solid #E2E8F0;
    background-color: #FFFFFF;
    color: #475569;
    font-weight: 600;
    font-size: 0.85rem;
    padding: 0.4rem 0.8rem;
    transition: all 0.2s ease;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
div.stButton > button:hover {
    border-color: #CBD5E1;
    background-color: #F8FAFC;
    color: #0F172A;
}

div.stButton > button[kind="primary"] {
    background: #3B82F6;
    color: white;
    border: none;
}
div.stButton > button[kind="primary"]:hover {
    background: #2563EB;
    box-shadow: 0 4px 6px rgba(37, 99, 235, 0.2);
}

/* 4. USER PROFILE STYLING */
.user-profile-card {
    display: flex;
    align-items: center;
    gap: 12px;
}
.user-avatar {
    width: 36px;
    height: 36px;
    background: #DBEAFE; 
    color: #2563EB;
    border-radius: 8px; 
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 1rem;
}
.user-info {
    display: flex;
    flex-direction: column;
    line-height: 1.2;
}
.user-name {
    font-weight: 600;
    font-size: 0.9rem;
    color: #1E293B;
}
.user-role {
    font-size: 0.75rem;
    color: #64748B;
}

/* 5. SETTINGS ROW STYLING */
.settings-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.85rem;
    color: #334155;
    font-weight: 500;
    padding-top: 4px;
    padding-bottom: 4px;
}
.stRadio > div {
    gap: 8px;
}

/* 6. ANTI-JUMP & NO-SPINNER FIX (V2 Features) */
.stSpinner, div[data-testid="stSpinner"] {
    display: none !important;
    opacity: 0 !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}
div[data-testid="stStatusWidget"] {
    visibility: hidden;
}
div[data-testid="stFragment"] {
    animation: none !important;
    transition: none !important;
}
div[data-testid="stVerticalBlock"] {
    min-height: 1px;
}

/* 7. DASHBOARD CARDS & HERO (WICHTIG: Aus V1 wiederhergestellt!) */
.status-dot { height: 12px; width: 12px; border-radius: 50%; display: inline-block; margin-right: 8px; flex-shrink: 0; }
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

.metrics-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 24px; padding-top: 24px; border-top: 1px solid #F1F5F9; }
.metric-item { text-align: center; }
.metric-label { font-size: 0.75rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; margin-bottom: 4px; }
.metric-value { font-size: 1.25rem; font-weight: 700; color: #1E293B; }
.metric-sub { font-size: 0.7rem; color: #64748B; margin-top: 2px; }

.progress-bg { background-color: #F1F5F9; border-radius: 99px; height: 12px; width: 100%; margin-top: 8px; overflow: hidden; }
.progress-fill { height: 100%; border-radius: 99px; transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1); }

/* Link Styling */
a.dashboard-link { text-decoration: none !important; color: inherit !important; display: block; transition: transform 0.2s ease, box-shadow 0.2s ease; }
a.dashboard-link:hover .dashboard-card { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05); border-color: #CBD5E1; }

/* Animation Keyframes */
@keyframes pulse-green { 0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); } 70% { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); } 100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); } }
@keyframes pulse-blue { 0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.4); } 70% { box-shadow: 0 0 0 10px rgba(59, 130, 246, 0); } 100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); } }
@keyframes pulse-orange { 0% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.4); } 70% { box-shadow: 0 0 0 10px rgba(245, 158, 11, 0); } 100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); } }
@keyframes pulse-red { 0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); } 70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); } 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); } }
@keyframes pulse-gray { 0% { box-shadow: 0 0 0 0 rgba(100, 116, 139, 0.4); } 70% { box-shadow: 0 0 0 10px rgba(100, 116, 139, 0); } 100% { box-shadow: 0 0 0 0 rgba(100, 116, 139, 0); } }

</style>
"""

def inject_custom_css():
    st.markdown(MODERN_CSS, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# NEUE KOMPONENTE: Card Header für Admin-Bereiche
# -----------------------------------------------------------------------------
def render_card_header(icon: str, title: str, subtitle: str, color_class: str = "blue"):
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
    icon_char = '📸' 

    if status_mode == "maintenance":
        pulse_class = "status-pulse-gray"
        dot_color = "#94A3B8"
        icon_char = '🚚'
    elif status_mode == "printing":
        pulse_class = "status-pulse-blue"
        dot_color = "#3B82F6"
        icon_char = '🖨️'
    elif status_mode == "ready":
        pulse_class = "status-pulse-green"
        dot_color = "#10B981"
    elif status_mode == "error":
        pulse_class = "status-pulse-red"
        dot_color = "#EF4444"
        icon_char = '🔧'
    else:
        if "orange" in display_color or "yellow" in display_color:
            pulse_class = "status-pulse-orange"
            dot_color = "#F59E0B"
            if status_mode == 'low_paper': icon_char = '⚠️'
            elif status_mode == 'cooldown': icon_char = '❄️'
        else:
            pulse_class = "status-pulse-gray" 
            dot_color = "#64748B"

    clean_text = display_text.replace('✅ ', '').replace('🔴 ', '').replace('⚠️ ', '').replace('🖨️ ', '').replace('⏳ ', '').replace('🚚 ', '')

    if not max_prints or max_prints <= 0:
        pct = 0
    else:
        pct = max(0, min(100, int((media_remaining / max_prints) * 100)))
    
    if pct < 10: bar_color = "#EF4444" 
    elif pct < 25: bar_color = "#F59E0B" 
    else: bar_color = "#3B82F6" 

    icon_bg = f"{dot_color}15" 

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
# SCREENSAVER / ZEN MODE (FIX)
# -----------------------------------------------------------------------------

def inject_screensaver_css():
    """
    Setzt das CSS für den Screensaver.
    Muss AUSSERHALB des Fragments/Loops aufgerufen werden, damit es nicht flackert.
    """
    css = """
    <style>
        .stApp {
            background-color: #000000 !important;
            color: #E2E8F0 !important;
        }
        section[data-testid="stSidebar"] { display: none !important; }
        header { visibility: hidden !important; }
        footer { visibility: hidden !important; }
        
        .screensaver-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 85vh;
            text-align: center;
            font-family: 'Inter', sans-serif;
        }
        .big-number {
            font-size: 15vw; /* Responsive Größe */
            font-weight: 800;
            line-height: 1;
            margin-bottom: 2vh;
            font-variant-numeric: tabular-nums;
        }
        .label-text {
            font-size: 2vh;
            text-transform: uppercase;
            letter-spacing: 0.3em;
            color: #64748B;
            margin-bottom: 0px;
        }
        .status-pill {
            background-color: #111827;
            border: 1px solid #1F2937;
            padding: 1.5vh 4vw;
            border-radius: 99px;
            font-size: 3vh;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 12px;
            margin-top: 4vh;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5);
        }
        .status-dot {
            height: 2vh;
            width: 2vh;
            border-radius: 50%;
        }
        .meta-info {
            margin-top: 5vh;
            color: #374151;
            font-family: monospace;
            font-size: 1.5vh;
        }
        /* Button-Container: Fixiert am unteren Bildschirmrand, exakt mittig */
        .stButton {
            position: fixed !important;
            bottom: 40px !important;
            left: 50% !important;
            transform: translateX(-50%) !important;
            width: auto !important;
            z-index: 99999;
        }

        /* Das eigentliche Button-Styling (Pillen-Form, dezent) */
        .stButton > button {
            background-color: transparent !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            color: rgba(255, 255, 255, 0.4) !important;
            border-radius: 50px !important; /* Macht ihn rund (Pille) */
            padding: 8px 30px !important;
            font-size: 0.75rem !important;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            transition: all 0.3s ease !important;
        }

        /* Hover-Effekt: Wird weiß und sichtbar */
        .stButton > button:hover {
            border-color: #ffffff !important;
            color: #ffffff !important;
            background-color: rgba(255, 255, 255, 0.1) !important;
            box-shadow: 0 0 15px rgba(255, 255, 255, 0.2);
            transform: translateY(-2px);
        }
        
        /* Den Button beim Klicken nicht rot werden lassen */
        .stButton > button:active, .stButton > button:focus {
            border-color: #ffffff !important;
            color: #ffffff !important;
            background-color: rgba(255, 255, 255, 0.2) !important;
        }
        
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def render_screensaver_content(status_mode, media_remaining, display_text, display_color, timestamp):
    # (Unverändert lassen)
    color_map = {"green": "#10B981", "blue": "#3B82F6", "orange": "#F59E0B", "red": "#EF4444", "gray": "#64748B"}
    accent_color = color_map.get(display_color, "#64748B")
    clean_text = display_text.replace('✅', '').replace('⚠️', '').replace('🔴', '').strip()
    html = f"""
    <div class="screensaver-container">
        <div class="label-text">Verbleibende Bilder</div>
        <div class="big-number" style="color: {accent_color}; text-shadow: 0 0 40px {accent_color}40;">{media_remaining}</div>
        <div class="status-pill" style="color: {accent_color};"><span class="status-dot" style="background-color: {accent_color}; box-shadow: 0 0 10px {accent_color};"></span>{clean_text}</div>
        <div class="meta-info">Zuletzt aktualisiert: {timestamp}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def inject_screensaver_css():
    # (Unverändert lassen)
    css = """<style>.stApp {background-color: #000000 !important; color: #E2E8F0 !important;} section[data-testid="stSidebar"] {display: none !important;} header, footer {visibility: hidden !important;} .screensaver-container {display: flex; flex-direction: column; align-items: center; justify-content: center; height: 85vh; text-align: center; font-family: 'Inter', sans-serif;} .big-number {font-size: 15vw; font-weight: 800; line-height: 1; margin-bottom: 2vh; font-variant-numeric: tabular-nums;} .label-text {font-size: 2vh; text-transform: uppercase; letter-spacing: 0.3em; color: #64748B;} .status-pill {background-color: #111827; border: 1px solid #1F2937; padding: 1.5vh 4vw; border-radius: 99px; font-size: 3vh; font-weight: 600; display: flex; align-items: center; gap: 12px; margin-top: 4vh; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5);} .status-dot {height: 2vh; width: 2vh; border-radius: 50%;} .meta-info {margin-top: 5vh; color: #374151; font-family: monospace; font-size: 1.5vh;} .stButton {position: fixed !important; bottom: 40px !important; left: 50% !important; transform: translateX(-50%) !important; width: auto !important; z-index: 99999;} .stButton > button {background-color: transparent !important; border: 1px solid rgba(255, 255, 255, 0.2) !important; color: rgba(255, 255, 255, 0.4) !important; border-radius: 50px !important; padding: 8px 30px !important; font-size: 0.75rem !important; text-transform: uppercase; letter-spacing: 0.15em; transition: all 0.3s ease !important;} .stButton > button:hover {border-color: #ffffff !important; color: #ffffff !important; background-color: rgba(255, 255, 255, 0.1) !important; box-shadow: 0 0 15px rgba(255, 255, 255, 0.2); transform: translateY(-2px);} .stButton > button:active, .stButton > button:focus {border-color: #ffffff !important; color: #ffffff !important; background-color: rgba(255, 255, 255, 0.2) !important;}</style>"""
    st.markdown(css, unsafe_allow_html=True)


# ui_components.py

import streamlit as st

def render_power_card(name: str, is_on: bool, power: float, switch_id: int, key_prefix: str, icon_type: str = "bolt"):
    """
    Rendert eine Kachel mit dynamischen Icons basierend auf icon_type.
    """
    
    # --- 1. SVG BIBLIOTHEK ---
    
    # Blitz (Standard / Hoher Verbrauch / Studioblitz)
    svg_bolt = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" style="width: 24px; height: 24px;"><path fill-rule="evenodd" d="M14.615 1.595a.75.75 0 01.359.852L12.982 9.75h7.268a.75.75 0 01.548 1.262l-10.5 11.25a.75.75 0 01-1.272-.71l1.992-7.302H3.75a.75.75 0 01-.548-1.262l10.5-11.25a.75.75 0 01.913-.143z" clip-rule="evenodd" /></svg>"""
    
    # Surface / Laptop / PC
    svg_surface = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" style="width: 24px; height: 24px;"><path d="M10.5 18.75a.75.75 0 000 1.5h3a.75.75 0 000-1.5h-3z" /><path fill-rule="evenodd" d="M8.625.75A3.375 3.375 0 005.25 4.125v15.75a3.375 3.375 0 003.375 3.375h6.75a3.375 3.375 0 003.375-3.375V4.125A3.375 3.375 0 0015.375.75h-6.75zM7.5 4.125c0-.621.504-1.125 1.125-1.125h6.75c.621 0 1.125.504 1.125 1.125v15.75c0 .621-.504 1.125-1.125 1.125h-6.75A1.125 1.125 0 017.5 19.875V4.125z" clip-rule="evenodd" /></svg>"""
    
    # Drucker / Printer
    svg_printer = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" style="width: 24px; height: 24px;"><path fill-rule="evenodd" d="M7.875 1.5C6.839 1.5 6 2.34 6 3.375v2.99c-.426.053-.851.11-1.274.174-1.454.218-2.476 1.483-2.476 2.917v6.294a3 3 0 003 3h.27l-.155 1.705A1.875 1.875 0 007.232 22.5h9.536a1.875 1.875 0 001.867-2.045l-.155-1.705h.27a3 3 0 003-3V9.456c0-1.434-1.022-2.7-2.476-2.917A48.816 48.816 0 0018 6.366V3.375c0-1.036-.84-1.875-1.875-1.875h-8.25zM16.5 6.205v-2.83A.375.375 0 0016.125 3h-8.25a.375.375 0 00-.375.375v2.83a49.353 49.353 0 019 0zm-.217 8.295a.75.75 0 10-1.5 0c0 .414.336.75.75.75h4.5a.75.75 0 100-1.5h-3.75z" clip-rule="evenodd" /><path d="M12 2.25a.75.75 0 01.75.75v2.25a.75.75 0 01-1.5 0V3a.75.75 0 01.75-.75z" /></svg>"""

    # Lüfter / Fan / Wind
    svg_fan = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" style="width: 24px; height: 24px;"><path d="M11.996 6.342a1.875 1.875 0 013.212-1.327l1.365 1.365a1.875 1.875 0 01-2.651 2.651l-1.926-1.926v-.763zM10.121 7.669a1.875 1.875 0 01-2.651-2.651l1.365-1.365a1.875 1.875 0 013.212 1.327v.763l-1.926 1.926zM11.996 17.658a1.875 1.875 0 01-3.212 1.327l-1.365-1.365a1.875 1.875 0 012.651-2.651l1.926 1.926v.763zM13.871 16.331a1.875 1.875 0 012.651 2.651l-1.365 1.365a1.875 1.875 0 01-3.212-1.327v-.763l1.926-1.926z" /><path fill-rule="evenodd" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25zm0 8.25a1.5 1.5 0 100 3 1.5 1.5 0 000-3z" clip-rule="evenodd" /></svg>"""

    # WLAN Router (Optional, falls benötigt)
    svg_router = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" style="width: 24px; height: 24px;"><path fill-rule="evenodd" d="M1.371 8.143c5.858-5.857 15.356-5.857 21.213 0a.75.75 0 010 1.061l-.53.53a.75.75 0 01-1.06 0c-4.98-4.979-13.053-4.979-18.032 0a.75.75 0 01-1.06 0l-.53-.53a.75.75 0 010-1.06zm3.182 3.182c4.1-4.1 10.749-4.1 14.85 0a.75.75 0 010 1.061l-.53.53a.75.75 0 01-1.062 0 8.25 8.25 0 00-11.667 0 .75.75 0 01-1.06 0l-.53-.53a.75.75 0 010-1.06zm3.204 3.182a6 6 0 018.486 0 .75.75 0 010 1.061l-.53.53a.75.75 0 01-1.061 0 3.75 3.75 0 00-5.304 0 .75.75 0 01-1.06 0l-.53-.53a.75.75 0 010-1.06zm3.182 3.182a1.5 1.5 0 012.122 0 .75.75 0 010 1.061l-.53.53a.75.75 0 01-1.061 0l-.53-.53a.75.75 0 010-1.06z" clip-rule="evenodd" /></svg>"""

    # Individuell / Default
    svg_default = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" style="width: 24px; height: 24px;"><path fill-rule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm11.378-3.917c-.89-.777-2.366-.777-3.255 0a.75.75 0 01-.988-1.129c1.454-1.272 3.776-1.272 5.23 0 1.513 1.324 1.513 3.518 0 4.842a3.75 3.75 0 01-.837.552c-.676.328-1.028.774-1.028 1.152v.2a.75.75 0 01-1.5 0v-.2c0-1.201 1.134-2.215 2.185-2.741.478-.239.792-.705.792-1.226 0-.61-.433-1.123-1.099-1.45zM12 15.75a.75.75 0 01.75.75v.008a.75.75 0 01-1.5 0v-.008a.75.75 0 01.75-.75z" clip-rule="evenodd" /></svg>"""

    # Ausgeschaltet (Power Button)
    svg_off = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width: 24px; height: 24px;"><path d="M18.36 6.64a9 9 0 1 1-12.73 0"></path><line x1="12" y1="2" x2="12" y2="12"></line></svg>"""

    # --- 2. LOGIK: WELCHES ICON? ---
    
    # Mapping JSON-Name -> SVG Variable
    icons_map = {
        "bolt": svg_bolt,
        "surface": svg_surface,
        "router": svg_router,
        "printer": svg_printer,
        "fan": svg_fan,
        "default": svg_default
    }
    
    # Welches Icon soll gezeigt werden wenn AN?
    active_icon_svg = icons_map.get(icon_type, svg_bolt) # Fallback ist Blitz

    if is_on:
        # Farbe bestimmen
        if power > 10: 
            status_color = "#3B82F6" # Blau (Aktiv)
            bg_color = "#EFF6FF"
            status_text = "AKTIV"
            pulse_class = "status-pulse-blue"
        else:
            status_color = "#10B981" # Grün (Standby/An)
            bg_color = "#ECFDF5"
            status_text = "AN"
            pulse_class = "status-pulse-green"
            
        icon_svg = active_icon_svg
        btn_label = "Ausschalten"
        btn_type = "secondary"
    else:
        status_color = "#94A3B8"
        bg_color = "#F1F5F9"
        icon_svg = svg_off 
        status_text = "AUS"
        pulse_class = ""
        power = 0.0
        btn_label = "Einschalten"
        btn_type = "primary"

    # --- 3. HTML ---
    html = f"""
    <div class="dashboard-card" style="padding: 20px; margin-bottom: 12px; height: 100%;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
                <div style="display: flex; align-items: center; margin-bottom: 8px;">
                    <span class="{pulse_class} status-dot"></span>
                    <span style="font-size: 0.75rem; font-weight: 700; color: #94A3B8; letter-spacing: 0.05em; text-transform: uppercase;">{name}</span>
                </div>
                <div style="display: flex; align-items: baseline; gap: 4px;">
                    <span style="font-size: 2.2rem; font-weight: 800; color: #1E293B; font-variant-numeric: tabular-nums;">{power:.1f}</span>
                    <span style="font-size: 1rem; font-weight: 600; color: #64748B;">W</span>
                </div>
            </div>
            <div style="background: {bg_color}; color: {status_color}; width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; box-shadow: inset 0 2px 4px 0 rgba(0,0,0,0.05);">
                {icon_svg}
            </div>
        </div>
        <div style="margin-top: 12px; font-size: 0.8rem; color: #64748B; font-weight: 500; display: flex; justify-content: space-between; align-items: center;">
            <span>Status: <span style="color: {status_color}; font-weight: 700;">{status_text}</span></span>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
    
    if st.button(btn_label, key=f"pwr_btn_{key_prefix}_{switch_id}", type=btn_type, use_container_width=True):
        return True
    return False


def render_lock_card_dual(lock_state: str, key_prefix: str):
    """
    Rendert die Screen-Lock Karte mit ZWEI separaten Buttons über die volle Breite.
    """
    
    # Icons
    svg_unlock = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" style="width: 24px; height: 24px;"><path d="M18 1.5c2.9 0 5.25 2.35 5.25 5.25v3.75a.75.75 0 01-1.5 0V6.75a3.75 3.75 0 10-7.5 0v3a3 3 0 013 3v6.75a3 3 0 01-3 3H3.75a3 3 0 01-3-3v-6.75a3 3 0 013-3h9v-3c0-2.9 2.35-5.25 5.25-5.25z" /></svg>"""
    svg_lock = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" style="width: 24px; height: 24px;"><path fill-rule="evenodd" d="M12 1.5a5.25 5.25 0 00-5.25 5.25v3a3 3 0 00-3 3v6.75a3 3 0 003 3h10.5a3 3 0 003-3v-6.75a3 3 0 00-3-3v-3c0-2.9-2.35-5.25-5.25-5.25zm3.75 8.25v-3a3.75 3.75 0 10-7.5 0v3h7.5z" clip-rule="evenodd" /></svg>"""

    # Farben & Text
    is_locked = (lock_state == "on")
    if is_locked:
        main_text = "GESPERRT"
        status_color = "#F59E0B" # Orange
        bg_color = "#FFFBEB"
        pulse_class = "status-pulse-orange"
        icon_svg = svg_lock
    else:
        main_text = "FREI"
        status_color = "#10B981" # Grün
        bg_color = "#ECFDF5"
        pulse_class = "status-pulse-green"
        icon_svg = svg_unlock

    # HTML: margin-bottom reduziert auf 0px, damit Buttons direkt anschließen
    # border-bottom-left-radius/right auf 0, damit es mit Buttons wie eins aussieht (optional, hier dezent gelassen)
    html = f"""
    <div class="dashboard-card" style="padding: 20px; margin-bottom: 8px; height: auto;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <div style="display: flex; align-items: center; margin-bottom: 6px;">
                    <span class="{pulse_class} status-dot"></span>
                    <span style="font-size: 0.75rem; font-weight: 700; color: #94A3B8; letter-spacing: 0.05em; text-transform: uppercase;">Screen Modus</span>
                </div>
                <div style="font-size: 1.8rem; font-weight: 800; color: #1E293B; font-variant-numeric: tabular-nums; line-height: 1;">
                    {main_text}
                </div>
            </div>
            <div style="background: {bg_color}; color: {status_color}; width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; box-shadow: inset 0 2px 4px 0 rgba(0,0,0,0.05);">
                {icon_svg}
            </div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
    
    # Action Buttons
    c1, c2 = st.columns(2)
    action = None
    
    with c1:
        # Button: Sperren (Links)
        if st.button("Sperren 🔒", key=f"btn_lock_{key_prefix}", use_container_width=True):
            action = "lock"
            
    with c2:
        # Button: Freigeben (Rechts)
        if st.button("Freigeben 🔓", key=f"btn_unlock_{key_prefix}", use_container_width=True):
            action = "unlock"
            
    return action
