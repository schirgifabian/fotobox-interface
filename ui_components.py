# ui_components.py

import streamlit as st
import textwrap
from sheets_helpers import get_data_event, get_spreadsheet, get_fleet_data_parallel

# -----------------------------------------------------------------------------
# GLOBAL STYLING (Sidebar + Dashboard + Animationen)
# -----------------------------------------------------------------------------
MODERN_CSS = """
<style>
/* 1. App-Container & Reset */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

.block-container {
    padding-top: 2rem !important;
    padding-bottom: 5rem !important;
    max-width: 1000px;
}

/* 2. Typografie & Body */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #334155;
    background-color: #F8FAFC; /* Ganz leichter Hintergrund für Main Area */
}

h1, h2, h3 {
    color: #0F172A;
    font-weight: 600;
    letter-spacing: -0.01em;
}

/* 3. SIDEBAR STYLING */
section[data-testid="stSidebar"] {
    background-color: #FFFFFF;
    border-right: 1px solid #E2E8F0;
    box-shadow: 4px 0 24px rgba(0,0,0,0.02);
}

/* Sidebar Überschriften */
section[data-testid="stSidebar"] h1, 
section[data-testid="stSidebar"] h2, 
section[data-testid="stSidebar"] h3 {
    color: #0F172A;
    font-weight: 700;
    letter-spacing: -0.02em;
}

/* Sidebar Widgets (Selectbox, Radio) */
section[data-testid="stSidebar"] label {
    font-size: 0.8rem;
    font-weight: 600;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Trennlinien in Sidebar feiner machen */
section[data-testid="stSidebar"] hr {
    border-color: #F1F5F9;
    margin: 1.5rem 0;
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

/* Container Border Override */
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
    border-radius: 12px;
    border: 1px solid #E2E8F0;
    background-color: #F8FAFC;
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

/* Primary Button Style */
div.stButton > button[kind="primary"] {
    background-color: #3B82F6;
    color: white;
    border: 1px solid #2563EB;
}
div.stButton > button[kind="primary"]:hover {
    background-color: #2563EB;
    color: white;
}

/* 6. MOBILE MINI STICKY BAR */
.mobile-status-bar {
    display: none; /* Auf Desktop standardmäßig ausblenden */
}

@media (max-width: 768px) {
    .mobile-status-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        
        /* HIER IST DIE ÄNDERUNG: sticky statt fixed */
        position: -webkit-sticky; /* Für Safari */
        position: sticky;
        
        /* 3rem (ca 48px) ist meist die Höhe des Streamlit Headers. 
           So dockt es genau darunter an. */
        top: 3rem; 
        
        z-index: 999; /* Etwas niedriger als der Streamlit Header */
        
        /* Margin sorgt für Abstand zur Hero-Card vorher */
        margin-top: 1rem; 
        margin-bottom: 1rem;
        
        background-color: rgba(255, 255, 255, 0.90);
        backdrop-filter: blur(8px);
        border: 1px solid #E2E8F0; /* Rundherum Rand sieht bei Sticky oft besser aus */
        border-radius: 12px;       /* Leicht abgerundet sieht 'schwebend' aus */
        padding: 8px 16px;         /* Etwas Padding */
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }

.mini-stat-item {
    display: flex;
    align-items: center;
    font-size: 0.85rem;
    font-weight: 600;
    color: #334155;
}

/* --------------------------------------------------------------------------
   DASHBOARD ANIMATIONEN (Keyframes)
   -------------------------------------------------------------------------- */
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
    
    # Standard Style für die Karte (Weiß mit grauem Rand)
    card_style = "background: #FFFFFF; border: 1px solid #E2E8F0;"

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
        # HIER IST DIE ÄNDERUNG: Alarm-Optik bei Fehler
        card_style = "background: #FEF2F2; border: 2px solid #EF4444;"
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

    # Icon Hintergrund leicht transparent basierend auf Statusfarbe
    icon_bg = f"{dot_color}15" 

    html_content = f"""
<div class="dashboard-card" style="{card_style}">
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

def render_mini_status_bar(status_mode: str, display_text: str, media_remaining: int):
    """
    Rendert eine fixierte Mini-Leiste für Mobile Devices.
    """
    # Farben definieren
    color_map = {
        "ready": "#10B981",    # Grün
        "printing": "#3B82F6", # Blau
        "error": "#EF4444",    # Rot
        "warning": "#F59E0B",  # Orange
        "offline": "#64748B"   # Grau
    }
    
    # Farbe bestimmen
    if status_mode in color_map:
        c = color_map[status_mode]
    elif "stale" in status_mode or "low" in status_mode:
        c = color_map["warning"]
    else:
        c = color_map["offline"]

    # Text kürzen für Mobile (z.B. "✅ Bereit" -> "Bereit")
    short_text = display_text.replace('✅ ', '').replace('🔴 ', '').replace('⚠️ ', '').replace('🖨️ ', '').strip()
    # Falls Text zu lang, abschneiden
    if len(short_text) > 15: 
        short_text = short_text[:12] + "..."

    html = f"""
    <div class="mobile-status-bar">
        <div class="mini-stat-item">
            <div style="width: 10px; height: 10px; border-radius: 50%; background: {c}; margin-right: 8px; box-shadow: 0 0 5px {c};"></div>
            {short_text}
        </div>
        <div class="mini-stat-item">
            <span style="background: #F1F5F9; padding: 4px 10px; border-radius: 99px; font-size: 0.75rem; color: #475569;">
                📷 {media_remaining}
            </span>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


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
        /* Buttons im Screensaver verstecken/abdunkeln */
        .stButton > button {
            background: transparent !important;
            border: 1px solid #333 !important;
            color: #555 !important;
        }
        .stButton > button:hover {
            color: red !important;
            border-color: red !important;
        }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def render_screensaver_content(
    status_mode: str,
    media_remaining: int,
    display_text: str,
    display_color: str,
    timestamp: str
):
    """
    Rendert NUR den Inhalt (HTML), kein CSS.
    """
    color_map = {
        "green": "#10B981",
        "blue": "#3B82F6",
        "orange": "#F59E0B",
        "red": "#EF4444",
        "gray": "#64748B"
    }
    accent_color = color_map.get(display_color, "#64748B")
    
    clean_text = display_text.replace('✅', '').replace('⚠️', '').replace('🔴', '').strip()
    
    # Inline Styles für dynamische Farben nutzen
    html = f"""
    <div class="screensaver-container">
        <div class="label-text">Verbleibende Bilder</div>
        <div class="big-number" style="color: {accent_color}; text-shadow: 0 0 40px {accent_color}40;">
            {media_remaining}
        </div>
        <div class="status-pill" style="color: {accent_color};">
            <span class="status-dot" style="background-color: {accent_color}; box-shadow: 0 0 10px {accent_color};"></span>
            {clean_text}
        </div>
        <div class="meta-info">
            Zuletzt aktualisiert: {timestamp}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
