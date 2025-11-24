import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import requests
from streamlit_lottie import st_lottie
import pandas as pd
import time
from datetime import datetime, timedelta

# --- KONFIGURATION ---
SHEET_ID = "10uLjotNMT3AewBHdkuYyOudbbOCEuquDqGbwr2Wu7ig"
PAGE_TITLE = "Fotobox Drucker Status"
PAGE_ICON = "🖨️"

# --- NTFY EINSTELLUNGEN (Push Nachrichten) ---
# Dies ist dein geheimer Schlüssel für die App
NTFY_TOPIC = "fotobox_status_secret_4566" 
NTFY_ACTIVE_DEFAULT = True

# --- SEITEN KONFIGURATION ---
st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="centered")

# --- SESSION STATE INITIALISIERUNG ---
if "confirm_reset" not in st.session_state:
    st.session_state.confirm_reset = False
if "ntfy_active" not in st.session_state:
    st.session_state.ntfy_active = NTFY_ACTIVE_DEFAULT
if "low_paper_warned" not in st.session_state:
    st.session_state.low_paper_warned = False
# Standardmäßig 400, wird aber durch Admin-Auswahl überschrieben
if "max_prints" not in st.session_state:
    st.session_state.max_prints = 400

# --- HELPER: LOTTIE (Stabilere URLs) ---
@st.cache_data(ttl=3600)
def load_lottieurl(url):
    try:
        r = requests.get(url, timeout=3)
        if r.status_code != 200: return None
        return r.json()
    except:
        return None

# Wir nutzen hier sehr stabile URLs
lottie_printing = load_lottieurl("https://lottie.host/5a8439d0-a686-40df-996c-7234f2903e25/6F0s8Y5s2R.json")
lottie_ready = load_lottieurl("https://assets10.lottiefiles.com/packages/lf20_jbrw3hcz.json")
lottie_warning = load_lottieurl("https://lottie.host/9415257e-28c4-4a76-af37-0418586e45e6/uX5Kz8q7sJ.json")

# --- HELPER: GOOGLE SHEETS ---
def get_worksheet():
    try:
        secrets = st.secrets["gcp_service_account"]
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(secrets, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        return sh.sheet1
    except Exception as e:
        st.error(f"Verbindungsfehler Google Sheets: {e}")
        return None

@st.cache_data(ttl=2) 
def get_data():
    try:
        worksheet = get_worksheet()
        if worksheet:
            data = worksheet.get_all_records()
            df = pd.DataFrame(data)
            # Zeitstempel normalisieren
            if 'Timestamp' in df.columns:
                df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
            elif 'Time' in df.columns:
                 df['Timestamp'] = pd.to_datetime(df['Time'], errors='coerce')
            return df
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

# --- HELPER: PUSH NACHRICHTEN ---
def send_ntfy_push(title, message, tags="warning", priority=3):
    if not st.session_state.ntfy_active: return False
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode('utf-8'),
            headers={"Title": title.encode('utf-8'), "Priority": str(priority), "Tags": tags},
            timeout=5
        )
        return True
    except: return False

# --- HELPER: PROGNOSE (Verbessert) ---
def calculate_forecast(df, current_prints_left):
    if df.empty or 'Timestamp' not in df.columns: return "Keine Daten"
    
    # Letzte Stunde analysieren
    now = datetime.now()
    one_hour_ago = now - timedelta(hours=1)
    recent = df[df['Timestamp'] > one_hour_ago]
    
    count_last_hour = len(recent)
    
    if count_last_hour < 2: return "Warte auf Daten..."
    
    hours_left = current_prints_left / count_last_hour
    
    if hours_left > 24: 
        return "> 24 Std."
    elif hours_left >= 1:
        return f"ca. {int(hours_left)} Std." # Nur Stunden wenn > 1
    else:
        minutes = int(hours_left * 60)
        return f"{minutes} Min." # Minuten wenn < 1 Std

# --- HELPER: RESET ---
def clear_google_sheet():
    try:
        ws = get_worksheet()
        if ws:
            ws.batch_clear(["A2:Z10000"])
            st.toast("Auftrag neu gestartet!", icon="✅")
            st.session_state.low_paper_warned = False
            st.cache_data.clear()
            return True
    except Exception as e:
        st.error(f"Fehler: {e}")
    return False

# --- APP START ---
st.title(f"{PAGE_ICON} {PAGE_TITLE}")
st.markdown("---")

# --- LIVE DASHBOARD ---
@st.fragment(run_every=10)
def show_live_status():
    if st.button("🔄 Status prüfen", key="refresh_btn"):
        st.cache_data.clear()

    df = get_data()
    
    # Aktuelles Max aus Session State holen
    current_max = st.session_state.max_prints

    if not df.empty:
        last_entry = df.iloc[-1]
        status = str(last_entry.get("Status", "Ready"))
        
        # Papierstand ermitteln
        if "Media_Remaining" in last_entry:
            try:
                media_remaining = int(last_entry.get("Media_Remaining", 0))
            except:
                media_remaining = 0
        else:
            media_remaining = current_max - len(df)

        timestamp = last_entry.get("Timestamp", datetime.now().strftime("%H:%M:%S"))
        forecast_text = calculate_forecast(df, media_remaining)

        # Logik für Warnschwelle (dynamisch basierend auf Paketgröße, z.B. 5%)
        warn_level = 20 

        # Design & Animation wählen
        if "Printing" in status:
            current_lottie = lottie_printing
            status_color = "#FFA500" # Orange
            status_text = "Druckt gerade..."
        elif media_remaining <= warn_level:
            current_lottie = lottie_warning
            status_color = "#FF4B4B" # Rot
            status_text = "Papier fast leer!"
            
            # Push senden
            if not st.session_state.low_paper_warned:
                send_ntfy_push("⚠️ Papier kritisch", f"Noch {media_remaining} Bilder (Paket: {current_max}). Bitte wechseln!", tags="rotating_light", priority=4)
                st.session_state.low_paper_warned = True
        else:
            current_lottie = lottie_ready
            status_color = "#00C851" # Grün
            status_text = "Drucker bereit"

        col1, col2 = st.columns([1, 2])

        with col1:
            # Fallback falls Lottie nicht lädt
            if current_lottie:
                st_lottie(current_lottie, height=220, key="anim_status")
            else:
                # Großes Emoji als Fallback
                st.markdown(f"<div style='font-size: 100px; text-align: center;'>{PAGE_ICON}</div>", unsafe_allow_html=True)

        with col2:
            st.markdown(f"<h2 style='color:{status_color}; margin-top:0;'>{status_text}</h2>", unsafe_allow_html=True)
            st.caption(f"Letztes Signal: {timestamp}")
            
            m_col1, m_col2 = st.columns(2)
            m_col1.metric("Verbleibend", f"{media_remaining}", f"Max: {current_max}")
            m_col2.metric("Laufzeit", forecast_text)

            # Progress Bar
            progress_val = max(0.0, min(1.0, media_remaining / current_max))
            st.progress(progress_val)

    else:
        st.info("System wartet auf Start...")
        st.caption("Noch keine Druckdaten empfangen.")

show_live_status()

st.markdown("---")

# --- ADMIN BEREICH ---
with st.expander("🛠️ Admin & Einstellungen", expanded=False):
    
    col_admin1, col_admin2 = st.columns(2)

    with col_admin1:
        st.write("### Externe Links")
        st.link_button("🔗 Zu Fotoshare Cloud", "https://fotoshare.co/admin/index", use_container_width=True)
        
        st.write("### Benachrichtigungen")
        st.code(NTFY_TOPIC, language="text")
        st.caption("Dies ist dein Topic für die 'ntfy' App.")
        
        st.session_state.ntfy_active = st.checkbox("Push-Nachrichten aktiv", value=st.session_state.ntfy_active)
        if st.button("Test Push 🔔"):
            send_ntfy_push("Test", f"Test erfolgreich! Paketgröße: {st.session_state.max_prints}", tags="tada")
            st.toast("Gesendet!")

    with col_admin2:
        st.write("### Neuer Auftrag / Wartung")
        
        # Paket Auswahl
        st.write("Welches Papier liegt ein?")
        new_package_size = st.radio("Paketgröße:", [200, 400], horizontal=True, index=1 if st.session_state.max_prints == 400 else 0)
        
        # Logik für Reset mit Bestätigung
        if not st.session_state.confirm_reset:
            if st.button("Papierwechsel durchgeführt (Reset) 🔄", use_container_width=True):
                st.session_state.confirm_reset = True
                st.session_state.temp_package_size = new_package_size # Zwischenspeichern
                st.rerun()
        else:
            st.warning(f"Log löschen & auf {st.session_state.temp_package_size}er Rolle setzen?")
            col_yes, col_no = st.columns(2)
            if col_yes.button("✅ Ja", use_container_width=True):
                # Anwenden der Änderungen
                st.session_state.max_prints = st.session_state.temp_package_size
                clear_google_sheet()
                st.session_state.confirm_reset = False
                st.rerun()

            if col_no.button("❌ Nein", use_container_width=True):
                st.session_state.confirm_reset = False
                st.rerun()
