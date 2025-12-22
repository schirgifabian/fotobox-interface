# ui_components.py

import streamlit as st
import textwrap
from sheets_helpers import get_data_event, get_spreadsheet, get_fleet_data_parallel
from status_logic import HEARTBEAT_WARN_MINUTES

# -----------------------------------------------------------------------------
# GLOBAL STYLING (WOW EFFECT EDITION)
# -----------------------------------------------------------------------------
MODERN_CSS = """
<style>
/* --- 0. ANIMATION DEFINITIONS --- */
@keyframes fadeInUp {
    from { opacity: 0; transform: translate3d(0, 20px, 0); }
    to { opacity: 1; transform: translate3d(0, 0, 0); }
}

@keyframes pulse-ring {
    0% { transform: scale(0.33); }
    80%, 100% { opacity: 0; }
}

@keyframes pulse-dot {
    0% { transform: scale(0.8); }
    50% { transform: scale(1); }
    100% { transform: scale(0.8); }
}

@keyframes gradient-x {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

/* --- 1. GLOBAL LAYOUT & BG --- */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

.stApp {
    /* Edler Hintergrund-Verlauf */
    background: linear-gradient(-45deg, #f1f5f9, #e2e8f0, #f8fafc, #ffffff);
    background-size: 400% 400%;
    animation: gradient-x 15s ease infinite;
}

.block-container {
    padding-top: 2rem !important;
    padding-bottom: 6rem !important;
    max-width: 1000px;
}

/* --- 2. TYPOGRAPHY --- */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    color: #1e293b;
}

h1, h2, h3 {
    color: #0f172a;
    font-weight: 700;
    letter-spacing: -0.02em;
}

/* --- 3. GLASSMORPHISM CARDS --- */
.glass-card {
    background: rgba(255, 255, 255, 0.75);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.6);
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 
                0 2px 4px -1px rgba(0, 0, 0, 0.03),
                inset 0 0 0 1px rgba(255,255,255,0.5);
    border-radius: 20px;
    padding: 24px;
    margin-bottom: 20px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    animation: fadeInUp 0.6s ease-out both;
}

.glass-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.05), 
                0 10px 10px -5px rgba(0, 0, 0, 0.02);
    border-color: rgba(255,255,255, 0.9);
}

/* --- 4. BUTTONS --- */
div.stButton > button {
    border-radius: 12px;
    border: none;
    background: white;
    box-shadow: 0 4px 6px rgba(0,0,0,0.04);
    font-weight: 600;
    padding: 0.6rem 1rem;
    transition: all 0.2s;
    color: #475569;
}
div.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 12px rgba(0,0,0,0.08);
    background: #f8fafc;
    color: #0f172a;
}
div.stButton > button:active {
    transform: translateY(0);
}

/* --- 5. METRICS OVERRIDE --- */
div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.6) !important;
    backdrop-filter: blur(8px) !important;
    border-radius: 16px !important;
    padding: 16px !important;
    border: 1px solid rgba(255,255,255,0.5) !important;
    box-shadow: 0 4px 6px rgba(0,0,0,0.02) !important;
    transition: transform 0.2s;
}
div[data-testid="stMetric"]:hover {
    transform: scale(1.02);
    background: rgba(255,255,255,0.8) !important;
}

div[data-testid="stMetricLabel"] {
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    color: #64748b !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
div[data-testid="stMetricValue"] {
    font-size: 1.8rem !important;
    font-weight: 700 !important;
    background: -webkit-linear-gradient(45deg, #1e293b, #475569);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

/* --- 6. PULSING LIVE DOT --- */
.live-indicator {
    position: relative;
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(255,255,255,0.5);
    padding: 6px 12px;
    border-radius: 99px;
    font-size: 0.8rem;
    color: #475569;
    width: fit-content;
    border: 1px solid rgba(255,255,255,0.4);
}
.pulsating-circle {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background-color: #10b981; /* Green default */
    position: relative;
}
.pulsating-circle::before {
    content: '';
    position: relative;
    display: block;
    width: 300%;
    height: 300%;
    box-sizing: border-box;
    margin-left: -100%;
    margin-top: -100%;
    border-radius: 50%;
    background-color: #10b981;
    animation: pulse-ring 1.25s cubic-bezier(0.215, 0.61, 0.355, 1) infinite;
    opacity: 0.4;
}

/* --- 7. CUSTOM PROGRESS BAR --- */
.custom-progress-container {
    width: 100%;
    background-color: #e2e8f0;
    border-radius: 99px;
    height: 14px;
    overflow: hidden;
    margin-top: 10px;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.05);
}

.custom-progress-bar {
    height: 100%;
    border-radius: 99px;
    background-size: 2rem 2rem;
    background-image: linear-gradient(
        45deg, 
        rgba(255, 255, 255, 0.15) 25%, 
        transparent 25%, 
        transparent 50%, 
        rgba(255, 255, 255, 0.15) 50%, 
        rgba(255, 255, 255, 0.15) 75%, 
        transparent 75%, 
        transparent
    );
    animation: progress-stripe 1s linear infinite;
    transition: width 0.6s ease;
}

@keyframes progress-stripe {
    0% { background-position: 1rem 0; }
    100% { background-position: 0 0; }
}

</style>
"""

def inject_custom_css():
    st.markdown(MODERN_CSS, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# ANIMATED HELPERS
# -----------------------------------------------------------------------------

def render_custom_progress_bar(value: float, color_start: str, color_end: str):
    """
    Rendert einen wunderschönen, animierten Progress-Bar.
    """
    percent = max(0, min(100, int(value * 100)))
    
    html = f"""
    <div class="custom-progress-container">
        <div class="custom-progress-bar" style="
            width: {percent}%; 
            background-color: {color_start};
            background-image: linear-gradient(90deg, {color_start}, {color_end});
        "></div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# COMPONENTS
# -----------------------------------------------------------------------------

def render_hero_status(status_mode: str, display_text: str, timestamp: str, heartbeat_info: str):
    """
    Die Hauptanzeige ganz oben - jetzt als Glassmorphism Card.
    """
    
    # Farben & Pulse definieren
    if status_mode == "error":
        color_grad = "linear-gradient(135deg, #EF4444 0%, #B91C1C 100%)"
        pulse_color = "#EF4444"
        icon = "🚨"
    elif status_mode == "printing":
        color_grad = "linear-gradient(135deg, #3B82F6 0%, #2563EB 100%)"
        pulse_color = "#3B82F6"
        icon = "🖨️"
    elif status_mode == "stale":
        color_grad = "linear-gradient(135deg, #F59E0B 0%, #D97706 100%)"
        pulse_color = "#F59E0B"
        icon = "⚠️"
    elif status_mode == "ready":
        color_grad = "linear-gradient(135deg, #10B981 0%, #059669 100%)"
        pulse_color = "#10B981"
        icon = "✅"
    else:
        color_grad = "linear-gradient(135deg, #F59E0B 0%, #D97706 100%)"
        pulse_color = "#F59E0B"
        icon = "ℹ️"
        
    display_text_clean = display_text.replace('✅ ', '').replace('🔴 ', '').replace('⚠️ ', '')
    
    # Inline Styles für den Pulse
    pulse_css = f"""
    <style>
    .pulsating-circle {{ background-color: {pulse_color}; }}
    .pulsating-circle::before {{ background-color: {pulse_color}; }}
    </style>
    """
    st.markdown(pulse_css, unsafe_allow_html=True)

    html = f"""
    <div class="glass-card" style="text-align: center; padding-bottom: 30px;">
        <div style="display: flex; justify-content: center; margin-bottom: 15px;">
            <div class="live-indicator">
                <div class="pulsating-circle"></div>
                <span>Update: {timestamp} {heartbeat_info}</span>
            </div>
        </div>
        
        <div style="
            font-size: 3rem; 
            font-weight: 800; 
            background: {color_grad};
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
            line-height: 1.1;
        ">
            {display_text_clean}
        </div>
        <div style="font-size: 1rem; color: #64748B; font-weight: 500;">
            Aktueller Drucker-Status
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


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
    # Farbthemen für die Cards
    if state == "on":
        bg_icon = "rgba(16, 185, 129, 0.15)"
        color_icon = "#059669"
        status_text = title_on
        icon = icon_on
    elif state == "off":
        bg_icon = "rgba(100, 116, 139, 0.1)"
        color_icon = "#64748B"
        status_text = title_off
        icon = icon_off
    else:
        bg_icon = "rgba(245, 158, 11, 0.15)"
        color_icon = "#D97706"
        status_text = title_unknown
        icon = icon_unknown

    html_content = textwrap.dedent(f"""
        <div class="glass-card" style="padding: 20px; position: relative;">
            <div style="
                position: absolute; top: 20px; right: 20px;
                background: {bg_icon}; color: {color_icon};
                font-size: 0.7rem; font-weight: 700;
                padding: 4px 10px; border-radius: 99px;
                text-transform: uppercase; letter-spacing: 0.05em;
            ">
                {badge_prefix}: {state.upper()}
            </div>
            <div style="display: flex; gap: 16px; margin-bottom: 16px;">
                <div style="
                    width: 50px; height: 50px; 
                    background: {bg_icon}; color: {color_icon};
                    border-radius: 14px;
                    display: flex; align-items: center; justify-content: center;
                    font-size: 24px; flex-shrink: 0;
                ">
                    {icon}
                </div>
                <div>
                    <div style="font-size: 0.75rem; color: #94A3B8; text-transform: uppercase; font-weight: 700; letter-spacing: 0.05em;">{section_title}</div>
                    <div style="font-size: 1.1rem; font-weight: 700; color: #1E293B;">{status_text}</div>
                </div>
            </div>
            <div style="font-size: 0.9rem; color: #64748B; margin-bottom: 0px;">
                {description}
            </div>
        </div>
    """)
    st.markdown(html_content, unsafe_allow_html=True)

    # Buttons unterhalb der Glass Card
    col1, col2 = st.columns(2)
    with col1:
        click_left = st.button(btn_left_label, key=btn_left_key, use_container_width=True)
    with col2:
        click_right = st.button(btn_right_label, key=btn_right_key, use_container_width=True)
    
    st.write("") 

    return click_left, click_right


def render_fleet_overview(PRINTERS: dict):
    st.markdown("### 📸 Fotobox Flotte")

    printers_secrets = st.secrets.get("printers", {})
    fleet_data = get_fleet_data_parallel(PRINTERS, printers_secrets)

    cols = st.columns(len(PRINTERS))
    
    idx = 0
    for name, cfg in PRINTERS.items():
        data = fleet_data.get(name)
        
        # Defaults
        status_color = "#94a3b8" 
        status_msg = "Offline"
        media_str = "–"
        last_ts = "N/A"
        
        if data:
            media_str = data.get("media_str", "?")
            last_ts = data.get("timestamp", "N/A")
            state = data.get("state", "unknown")
            
            if state == "error":
                status_color = "#EF4444"
                status_msg = "Störung"
            elif state == "printing":
                status_color = "#3B82F6"
                status_msg = "Druckt"
            elif state == "ready":
                status_color = "#10B981"
                status_msg = "Bereit"

        with cols[idx]:
            card_html = textwrap.dedent(f"""
                <div class="glass-card" style="
                    text-align: center; 
                    height: 200px; 
                    display: flex; 
                    flex-direction: column; 
                    justify-content: center; 
                    align-items: center;
                    margin-bottom: 0;
                ">
                    <div style="
                        font-weight: 700; 
                        color: #1e293b; 
                        margin-bottom: 15px; 
                        font-size: 1.1rem;
                    ">{name}</div>
                    
                    <div style="
                        background: {status_color}20; 
                        color: {status_color};
                        padding: 6px 16px;
                        border-radius: 99px;
                        font-size: 0.8rem;
                        font-weight: 700;
                        margin-bottom: 15px;
                        border: 1px solid {status_color}40;
                        text-transform: uppercase;
                        letter-spacing: 0.05em;
                    ">
                        {status_msg}
                    </div>
                    
                    <div style="font-size: 1.2rem; font-weight: 800; color: #334155; margin-bottom: 6px;">
                        {media_str}
                    </div>
                    <div style="font-size: 0.75rem; color: #94A3B8;">
                        {last_ts}
                    </div>
                </div>
            """)
            st.markdown(card_html, unsafe_allow_html=True)
        idx += 1
