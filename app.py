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
NTFY_TOPIC = "fotobox_status_secret_4566" 
NTFY_ACTIVE_DEFAULT = True
WARNING_THRESHOLD = 20 # Ab wie vielen Bildern Warnung?

# --- SEITEN KONFIGURATION ---
st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="centered")

# --- SESSION STATE ---
if "confirm_reset" not in st.session_state:
    st.session_state.confirm_reset = False
if "ntfy_active" not in st.session_state:
    st.session_state.ntfy_active = NTFY_ACTIVE_DEFAULT
if "last_warn_status" not in st.session_state:
    st.session_state.last_warn_status = None # Speichert, wovor zuletzt gewarnt wurde
if "max_prints" not in st.session_state:
    st.session_state.max_prints = 400 # Standardwert

# --- FUNKTION: Push Nachricht Senden ---
def send_ntfy_push(title, message, tags="warning", priority="default"):
    """Sendet Push via ntfy.sh"""
    if not st.session_state.ntfy_active:
        return
    
    try:
        headers = {
            "Title": title.encode('utf-8'),
            "Tags": tags,
            "Priority": priority
        }
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode(encoding='utf-8'),
            headers=headers,
            timeout=5 # Timeout wichtig, damit App nicht hängt
        )
    except Exception as e:
        print(f"Push Fehler: {e}")

# --- FUNKTION: Lottie Laden (Stabil) ---
@st.cache_data(ttl=3600)
def load_lottieurl(url):
    try:
        r = requests.get(url, timeout=3)
        if r.status_code != 200: return None
        return r.json()
    except:
        return None

# Animationen laden
lottie_printing = load_lottieurl("https://lottie.host/5a8439d0-a686-40df-996c-7234f2903e25/6F0s8Y5s2R.json") # Drucker
lottie_ready = load_lottieurl("https://assets10.lottiefiles.com/packages/lf20_jbrw3hcz.json") # Checkmark
lottie_warning = load_lottieurl("https://lottie.host/97b99728-385a-4d12-811c-1e7062bc449e/1tqL2v7z2h.json") # Ausrufezeichen Gelb
lottie_error = load_lottieurl("https://lottie.host/8614466e-448c-41c3-be3b-183217257e8f/GkqQ3s9C7k.json") # Fehler Rot

# --- GOOGLE SHEETS HELPER ---
def get_worksheet():
    secrets = st.secrets["gcp_service_account"]
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(secrets, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    return sh.sheet1

@st.cache_data(ttl=0)
def get_data():
    try:
        worksheet = get_worksheet()
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        return df
    except Exception:
        return pd.DataFrame()

def clear_google_sheet():
    try:
        ws = get_worksheet()
        ws.batch_clear(["A2:Z10000"]) 
        st.cache_data.clear()
        st.toast("Log erfolgreich zurückgesetzt!", icon="♻️")
    except Exception as e:
        st.error(f"Fehler beim Reset: {e}")

# --- MAIN APP LOGIK ---
st.title(f"{PAGE_ICON} {PAGE_TITLE}")

@st.fragment(run_every=10)
def show_live_status():
    df = get_data()
    
    if not df.empty:
        try:
            # Letzten Eintrag holen
            last_entry = df.iloc[-1]
            
            # Zeitstempel parsing
            timestamp_str = str(last_entry.get("Timestamp", ""))
            try:
                last_update = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                time_diff = datetime.now() - last_update
                is_offline = time_diff.total_seconds() > 300 # 5 Min ohne Update = Offline?
            except:
                last_update = datetime.now()
                is_offline = False

            # Status Text analysieren
            raw_status = str(last_entry.get("Status", "")).lower()
            media_remaining = int(last_entry.get("MediaRemaining", 0))
            current_max = st.session_state.max_prints

            # --- LOGIK ENTSCHEIDUNGSBAUM (PRIORITÄT) ---
            
            # 1. OFFLINE CHECK
            if is_offline:
                status_mode = "offline"
                display_text = "Drucker antwortet nicht"
                display_color = "gray"
                current_lottie = lottie_warning # Oder ein schlafendes Icon

            # 2. FEHLER CHECK (Höchste Prio)
            elif "error" in raw_status or "unknown" in raw_status or "stau" in raw_status or "failure" in raw_status:
                status_mode = "error"
                display_text = f"⚠️ STÖRUNG: {last_entry.get('Status')}"
                display_color = "red"
                current_lottie = lottie_error
                
                # Push senden (nur einmal pro Fehler)
                if st.session_state.last_warn_status != "error":
                    send_ntfy_push("🔴 KRITISCHER FEHLER", f"Drucker meldet: {last_entry.get('Status')}", tags="rotating_light", priority="high")
                    st.session_state.last_warn_status = "error"

            # 3. PAPIER LEER CHECK
            elif media_remaining <= WARNING_THRESHOLD:
                status_mode = "low_paper"
                display_text = "Papier fast leer!"
                display_color = "orange" # Orange ist besser lesbar als gelb
                current_lottie = lottie_warning
                
                # Push senden
                if st.session_state.last_warn_status != "low_paper":
                    send_ntfy_push("⚠️ Papierwarnung", f"Nur noch {media_remaining} Bilder verbleibend!", tags="warning")
                    st.session_state.last_warn_status = "low_paper"

            # 4. ALLES OK (Druckt oder Bereit)
            elif "printing" in raw_status or "processing" in raw_status:
                status_mode = "printing"
                display_text = "Druckt gerade..."
                display_color = "blue"
                current_lottie = lottie_printing
                st.session_state.last_warn_status = "ok" # Reset Warning

            else:
                status_mode = "ready"
                display_text = "Bereit"
                display_color = "green"
                current_lottie = lottie_ready
                st.session_state.last_warn_status = "ok" # Reset Warning

            # --- ANZEIGE ---
            
            # Layout
            col1, col2 = st.columns([1, 2])
            
            with col1:
                # Bild anzeigen (Fallback Emoji wenn Lottie fehlt)
                if current_lottie:
                    st_lottie(current_lottie, height=180, key="status_anim_main")
                else:
                    st.markdown("## 🤖")

            with col2:
                st.markdown(f"<h2 style='color:{display_color}; margin-top:0;'>{display_text}</h2>", unsafe_allow_html=True)
                st.caption(f"Letztes Signal: {timestamp_str}")
                
                if status_mode == "offline":
                    st.error("Verbindung zum Drucker unterbrochen?")

            # Metriken & Balken (immer anzeigen, außer bei Offline evtl ausgrauen)
            st.markdown("#### Papierstatus")
            
            # Laufzeit Berechnung
            if media_remaining > 0:
                minutes_left = int(media_remaining * 1.5) # Annahme: 1.5 Min pro Bild inkl Leerlauf
                if minutes_left > 60:
                    hours = minutes_left // 60
                    mins = minutes_left % 60
                    forecast_text = f"ca. {hours} Std. {mins} Min."
                else:
                    forecast_text = f"ca. {minutes_left} Min."
            else:
                forecast_text = "0 Min."

            m_col1, m_col2 = st.columns(2)
            m_col1.metric("Verbleibend", f"{media_remaining} Stk", f"von {current_max}")
            m_col2.metric("Restlaufzeit (geschätzt)", forecast_text)

            # Progress Bar Farbe berechnen
            progress_val = max(0.0, min(1.0, media_remaining / current_max))
            
            if status_mode == "error":
                bar_color = "red" # Bei Fehler rot
            elif progress_val < 0.1:
                bar_color = "red"
            elif progress_val < 0.25:
                bar_color = "orange"
            else:
                bar_color = "blue"

            # Custom CSS für farbige Progress Bar (Trick)
            st.markdown(
                f"""
                <style>
                .stProgress > div > div > div > div {{
                    background-color: {bar_color};
                }}
                </style>""",
                unsafe_allow_html=True,
            )
            st.progress(progress_val)

    else:
        st.info("System wartet auf Start...")
        st.caption("Noch keine Druckdaten empfangen.")

# Fragment ausführen
show_live_status()

st.markdown("---")

# --- ADMIN BEREICH ---
with st.expander("🛠️ Admin & Einstellungen", expanded=False):
    
    col_admin1, col_admin2 = st.columns(2)

    with col_admin1:
        st.write("### Externe Links")
        st.link_button("🔗 Fotoshare Cloud", "https://fotoshare.co/admin/index", use_container_width=True)
        
        st.write("### Benachrichtigungen")
        st.code(NTFY_TOPIC, language="text")
        
        st.session_state.ntfy_active = st.checkbox("Push-Nachrichten aktiv", value=st.session_state.ntfy_active)
        if st.button("Test Push 🔔"):
            send_ntfy_push("Test", f"Test erfolgreich! Paketgröße: {st.session_state.max_prints}", tags="tada")
            st.toast("Test gesendet!")

    with col_admin2:
        st.write("### Neuer Auftrag")
        
        # Paket Auswahl
        st.write("Welches Papier liegt ein?")
        new_package_size = st.radio("Paketgröße:", [200, 400], horizontal=True, index=1 if st.session_state.max_prints == 400 else 0)
        
        # Logik für Reset
        if not st.session_state.confirm_reset:
            if st.button("Papierwechsel durchgeführt (Reset) 🔄", use_container_width=True):
                st.session_state.confirm_reset = True
                st.session_state.temp_package_size = new_package_size
                st.rerun()
        else:
            st.warning(f"Log löschen & auf {st.session_state.temp_package_size}er Rolle setzen?")
            col_yes, col_no = st.columns(2)
            if col_yes.button("✅ Ja", use_container_width=True):
                st.session_state.max_prints = st.session_state.temp_package_size
                clear_google_sheet()
                st.session_state.confirm_reset = False
                st.session_state.last_warn_status = None # Warnstatus auch resetten
                st.rerun()

            if col_no.button("❌ Nein", use_container_width=True):
                st.session_state.confirm_reset = False
                st.rerun()
