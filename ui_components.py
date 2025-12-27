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
    background-color: #F1F5F9; /* Kühles Grau als Basis */
    border-right: 1px solid #E2E8F0;
    padding-top: 1rem;
}

/* Sidebar Titel ausblenden oder stylen */
section[data-testid="stSidebar"] .block-container {
    padding-top: 1rem;
    padding-bottom: 2rem;
}

/* 3. DIE "FLOATING CARDS" IN DER SIDEBAR */
/* Wir stylen spezifisch die Container in der Sidebar */
section[data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 12px !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.02) !important;
    padding: 16px !important;
    margin-bottom: 12px;
}

/* Überschriften innerhalb der Sidebar-Cards kleiner und grauer */
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

/* Captions in der Sidebar unsichtbar machen oder stylen, 
   da wir eigene Header nutzen */
section[data-testid="stSidebar"] .stCaption {
    color: #94A3B8;
    font-size: 0.7rem;
}

/* 4. BUTTONS & INPUTS */
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

/* Primary Button */
div.stButton > button[kind="primary"] {
    background: #3B82F6;
    color: white;
    border: none;
}
div.stButton > button[kind="primary"]:hover {
    background: #2563EB;
    box-shadow: 0 4px 6px rgba(37, 99, 235, 0.2);
}

/* 5. USER PROFILE STYLING */
.user-profile-card {
    display: flex;
    align-items: center;
    gap: 12px;
    /* margin-bottom wird vom Container handled */
}
.user-avatar {
    width: 36px;
    height: 36px;
    background: #DBEAFE; /* Helles Blau */
    color: #2563EB;
    border-radius: 8px; /* Eckig statt rund wirkt moderner */
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

/* 6. SETTINGS ROW STYLING */
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

/* Radio Buttons kompakter */
.stRadio > div {
    gap: 8px;
}

/* =========================================
   ANTI-JUMP & NO-SPINNER FIX
   ========================================= */

/* 1. Den Standard-Spinner von Streamlit (oben rechts und in Elementen) ausblenden */
.stSpinner, div[data-testid="stSpinner"] {
    display: none !important;
    opacity: 0 !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* 2. Den "Running"-Man oben rechts ausblenden (falls gewünscht) */
div[data-testid="stStatusWidget"] {
    visibility: hidden;
}

/* 3. Animationen bei Fragment-Updates unterdrücken 
   (Verhindert das "Grau-Werden" beim Neuladen) */
div[data-testid="stFragment"] {
    animation: none !important;
    transition: none !important;
}

/* 4. Verhindert das Zusammenfallen von Containern während des Ladens */
div[data-testid="stVerticalBlock"] {
    min-height: 1px; /* Erzwingt, dass der Block existiert */
}


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
