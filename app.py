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
MAX_PRINTS_PER_ROLL = 400
WARNING_THRESHOLD = 20  # Ab hier wird gewarnt
PAGE_TITLE = "Fotobox Drucker Status"
PAGE_ICON = "🖨️"

# --- SEITEN KONFIGURATION ---
st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="centered")

# --- SESSION STATE INITIALISIERUNG ---
# Wir speichern Zustände, um Benachrichtigungs-Spam zu verhindern
if "confirm_reset" not in st.session_state:
    st.session_state.confirm_reset = False

# ntfy Einstellungen
if "ntfy_active" not in st.session_state:
    st.session_state.ntfy_active = False  # Standard aus
if "ntfy_topic" not in st.session_state:
    st.session_state.ntfy_topic = "fotobox_status_secret_123" # Standard Topic (sollte geändert werden)

# Status-Speicher (damit wir nur bei Änderungen benachrichtigen)
if "last_known_status" not in st.session_state:
    st.session_state.last_known_status = "Startup"
if "low_paper_warned" not in st.session_state:
    st.session_state.low_paper_warned = False

# --- CACHING & LOTTIE ---
@st.cache_data(ttl=3600)
def load_lottieurl(url):
    try:
        r = requests.get(url)
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None

lottie_printing = load_lottieurl("https://assets9.lottiefiles.com/packages/lf20_yyja09.json")
lottie_ready = load_lottieurl("https://assets1.lottiefiles.com/packages/lf20_jbrw3hcz.json")
lottie_error = load_lottieurl("https://assets10.lottiefiles.com/packages/lf20_Tkwjw8.json")

# --- GOOGLE SHEETS HELPER ---
def get_worksheet():
    secrets = st.secrets["gcp_service_account"]
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(secrets, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    return sh.sheet1

# --- DATEN LADEN (MIT CACHE) ---
@st.cache_data(ttl=0)
def get_data():
    try:
        worksheet = get_worksheet()
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        if not df.empty and "Timestamp" in df.columns:
             df["dt_obj"] = pd.to_datetime(df["Timestamp"], format="%Y-%m-%d %H:%M:%S", errors='coerce')
        return df
    except Exception as e:
        return pd.DataFrame()

# --- DATEN LÖSCHEN FUNKTION ---
def clear_google_sheet():
    try:
        ws = get_worksheet()
        ws.batch_clear(["A2:Z10000"]) 
        st.toast("Log erfolgreich geleert!", icon="✅")
        st.cache_data.clear()
        # Reset Flags
        st.session_state.low_paper_warned = False
        st.session_state.last_known_status = "Reset"
    except Exception as e:
        st.error(f"Fehler beim Löschen: {e}")

# --- NTFY PUSH FUNKTION ---
def send_ntfy_push(title, message, priority="3", tags=""):
    """Sendet eine Push-Nachricht via ntfy.sh"""
    if not st.session_state.ntfy_active:
        return

    topic = st.session_state.ntfy_topic.strip()
    if not topic:
        return

    url = f"https://ntfy.sh/{topic}"
    try:
        requests.post(
            url,
            data=message.encode(encoding='utf-8'),
            headers={
                "Title": title,
                "Priority": priority, # 1=min, 3=default, 5=high
                "Tags": tags,
            },
            timeout=3
        )
        # Kleiner Toast im Dashboard als Bestätigung, dass gesendet wurde (optional)
        # st.toast(f"Push gesendet: {title}") 
    except Exception as e:
        print(f"NTFY Fehler: {e}")

# --- HILFSFUNKTION: RESTZEIT ---
def calculate_time_remaining(df, current_media):
    try:
        if df.empty or "dt_obj" not in df.columns: return "Keine Daten"
        df_sorted = df.dropna(subset=["dt_obj"]).sort_values("dt_obj")
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        last_hour_df = df_sorted[df_sorted["dt_obj"] > one_hour_ago]
        
        if len(last_hour_df) < 2: return "Lerne..."
            
        start_media = last_hour_df.iloc[0]["Media_Remaining"]
        prints_made = start_media - current_media
        
        if prints_made <= 0: return "Standby"
        hours_left = current_media / prints_made
        
        if hours_left < 1: return f"ca. {int(hours_left * 60)} Min"
        else: return f"ca. {hours_left:.1f} Std"
    except Exception: return "n/a"

# --- LAYOUT START ---
st.title(f"{PAGE_ICON} {PAGE_TITLE}")
st.markdown("---")

# --- LIVE FRAGMENT (Logik + UI) ---
@st.fragment(run_every=10)
def show_live_status():
    if st.button("🔄 Status prüfen", key="refresh_fragment"):
        st.cache_data.clear()

    df = get_data()

    if not df.empty:
        try:
            latest_entry = df.iloc[-1]
            status = latest_entry.get("Status", "Unknown")
            media_remaining = int(latest_entry.get("Media_Remaining", 0))
            timestamp = latest_entry.get("Timestamp", "Unbekannt")

            # --- ALARM LOGIK (NTFY) ---
            # 1. Papier Warnung (Nur einmalig feuern bis Auffüllung)
            if media_remaining < WARNING_THRESHOLD and media_remaining > 0:
                if not st.session_state.low_paper_warned:
                    send_ntfy_push(
                        title="⚠️ Drucker Papier fast leer!",
                        message=f"Nur noch {media_remaining} Bilder übrig. Bitte bald wechseln.",
                        priority="4",
                        tags="roll_of_paper,warning"
                    )
                    st.session_state.low_paper_warned = True
            elif media_remaining > WARNING_THRESHOLD:
                # Reset Flag wenn aufgefüllt wurde
                st.session_state.low_paper_warned = False

            # 2. Fehler Status Warnung
            # Ignoriere 'normal' status changes zwischen Ready und Printing
            is_error = status not in ["Ready", "Printing"]
            
            # Wenn Status ein Fehler ist UND sich vom letzten bekannten Status unterscheidet
            if is_error and status != st.session_state.last_known_status:
                send_ntfy_push(
                    title=f"🚨 Drucker Fehler: {status}",
                    message=f"Der Drucker meldet ein Problem: {status}. Bitte prüfen!",
                    priority="5",
                    tags="rotating_light,printer"
                )
            
            # Status aktualisieren
            st.session_state.last_known_status = status

            # --- VISUALISIERUNG ---
            col1, col2 = st.columns([1, 2])

            if status == "Printing":
                current_lottie = lottie_printing
                status_color = "orange"
                status_text = "Druckt gerade..."
            elif status == "Ready":
                current_lottie = lottie_ready
                status_color = "green"
                status_text = "Drucker bereit"
            else:
                current_lottie = lottie_error
                status_color = "red"
                status_text = f"Status: {status}"

            with col1:
                st_lottie(current_lottie, height=200, key="status_animation")

            with col2:
                st.markdown(f"<h2 style='color:{status_color};'>{status_text}</h2>", unsafe_allow_html=True)
                st.write(f"🕒 Letztes Update: **{timestamp}**")
                
                time_left = calculate_time_remaining(df, media_remaining)
                
                c_metric1, c_metric2 = st.columns(2)
                c_metric1.metric(label="Verbleibende Bilder", value=f"{media_remaining} Stk")
                c_metric2.metric(label="Geschätzte Laufzeit", value=time_left)

                progress_val = max(0.0, min(1.0, media_remaining / MAX_PRINTS_PER_ROLL))
                st.write("Papierstatus:")
                if progress_val < 0.1:
                    st.progress(progress_val, text="⚠️ Wenig Papier")
                else:
                    st.progress(progress_val)
            
            # Browser Error Message (Visuell)
            if media_remaining < WARNING_THRESHOLD:
                 st.error(f"Nur noch {media_remaining} Bilder!")
            if status not in ["Ready", "Printing"]:
                 st.error(f"Drucker Fehler erkannt: {status}")

            with st.expander("📊 Statistik & Verlauf"):
                st.caption("Verlauf Papierstand")
                if "dt_obj" in df.columns:
                    chart_df = df.dropna(subset=["dt_obj"]).set_index("dt_obj")["Media_Remaining"]
                    st.line_chart(chart_df, height=200)
                st.dataframe(df.tail(5).sort_index(ascending=False), use_container_width=True)

        except Exception as e:
            st.error(f"Fehler in der Datenverarbeitung: {e}")
    else:
        st.info("Warte auf Daten...")

# Fragment starten
show_live_status()

st.markdown("---")

# --- ADMIN TOOLS ---
with st.expander("🛠️ Admin & Einstellungen", expanded=True):
    
    col_admin1, col_admin2 = st.columns(2)

    with col_admin1:
        st.write("**Push-Benachrichtigungen (ntfy.sh)**")
        
        # Checkbox für Aktivierung
        ntfy_check = st.checkbox("🔔 Benachrichtigungen aktivieren", 
                                 value=st.session_state.ntfy_active)
        st.session_state.ntfy_active = ntfy_check

        # Topic Eingabe
        topic_input = st.text_input("Dein ntfy Topic Name", 
                                    value=st.session_state.ntfy_topic,
                                    help="Geheim halten! Auf deinem Handy App installieren und dieses Topic abonnieren.")
        st.session_state.ntfy_topic = topic_input
        
        if st.button("Test Nachricht senden"):
            send_ntfy_push("Test vom Dashboard", "Wenn du das liest, funktioniert die Verbindung! 🚀", tags="tada")
            st.success("Test gesendet!")

    with col_admin2:
        st.write("**Datenbank Management**")
        st.link_button("🔗 Zu Fotoshare Admin", "https://fotoshare.co/admin/index", use_container_width=True)
        
        if not st.session_state.confirm_reset:
            if st.button("🗑️ Log Datei leeren", use_container_width=True):
                st.session_state.confirm_reset = True
                st.rerun()
        else:
            st.warning("⚠️ Wirklich löschen?")
            col_yes, col_no = st.columns(2)
            if col_yes.button("✅ Ja", use_container_width=True):
                clear_google_sheet()
                st.session_state.confirm_reset = False
                st.rerun()
            if col_no.button("❌ Nein", use_container_width=True):
                st.session_state.confirm_reset = False
                st.rerun()
