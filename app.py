import streamlit as st
import gspread
from gspread.exceptions import WorksheetNotFound
from google.oauth2.service_account import Credentials
import requests
import pandas as pd
from datetime import datetime

# --- KONFIGURATION GLOBAL ---
PAGE_TITLE = "Fotobox Drucker Status"
PAGE_ICON = "🖨️"

PRINTERS = {
    "dieFotobox.": {
        "sheet_id": "10uLjotNMT3AewBHdkuYyOudbbOCEuquDqGbwr2Wu7ig",
        "ntfy_topic": "fotobox_status_secret_4566",
        "warning_threshold": 20,
        "default_max_prints": 400,
        "cost_per_roll_eur": 46.58,
    },
    "Fotobox Weinkellerei": {
        "sheet_id": "1zZ0Xd4OhRnIsCH7JPbaEEE8GzLvdn9usMj1YUOc_-rs",
        "ntfy_topic": "fotobox_status_secret_4566-weinkellerei",
        "warning_threshold": 50,
        "default_max_prints": 400,
        "cost_per_roll_eur": None,
    },
}

HEARTBEAT_WARN_MINUTES = 60
NTFY_ACTIVE_DEFAULT = True
ALERT_SOUND_URL = "https://actions.google.com/sounds/v1/alarms/beep_short.ogg"

# --- SEITEN CONFIG ---
st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="centered")

# --- GOOGLE SHEETS HELPER ---
def get_gspread_client():
    secrets = st.secrets["gcp_service_account"]
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(secrets, scopes=scopes)
    return gspread.authorize(creds)

def get_current_worksheet():
    """Öffnet das Sheet der aktuell ausgewählten Fotobox."""
    gc = get_gspread_client()
    # Wir holen die ID aus dem Session State (wird in der Sidebar gesetzt)
    sheet_id = st.session_state.get("current_sheet_id")
    if not sheet_id:
        return None
    return gc.open_by_key(sheet_id).get_worksheet(0)

# --- PUSH CONFIG (SPALTE K) LOGIK ---
def load_push_setting_from_sheet():
    """Lädt die Push-Einstellung aus Zelle K2."""
    try:
        ws = get_current_worksheet()
        if not ws: 
            return NTFY_ACTIVE_DEFAULT
        
        # Wir lesen K1 und K2
        # K1 sollte Header "Push" sein, K2 der Wert (TRUE/FALSE)
        val_k2 = ws.acell('K2').value
        
        if val_k2 == "TRUE":
            return True
        elif val_k2 == "FALSE":
            return False
        else:
            # Wenn leer oder unbekannt, Header setzen und Default zurückgeben
            ws.update_acell('K1', 'Push')
            ws.update_acell('K2', str(NTFY_ACTIVE_DEFAULT).upper())
            return NTFY_ACTIVE_DEFAULT
    except Exception as e:
        st.error(f"Fehler beim Laden der Push-Einstellung: {e}")
        return NTFY_ACTIVE_DEFAULT

def save_push_setting_to_sheet():
    """Callback: Speichert den Status der Checkbox sofort in Zelle K2."""
    try:
        ws = get_current_worksheet()
        if ws:
            new_value = st.session_state.ntfy_active_checkbox
            # Header sicherstellen
            k1_val = ws.acell('K1').value
            if k1_val != "Push":
                ws.update_acell('K1', 'Push')
            
            # Wert speichern
            ws.update_acell('K2', str(new_value).upper())
            
            # Session State auch aktualisieren (für die interne Logik)
            st.session_state.ntfy_active = new_value
            st.toast(f"Einstellung gespeichert: Push {'An' if new_value else 'Aus'}")
    except Exception as e:
        st.error(f"Fehler beim Speichern der Push-Einstellung: {e}")

# --- DATEN LADEN (SPALTEN A-J) ---
def get_data():
    """Lädt nur Spalten A bis J (Log-Daten), ignoriert K (Config)."""
    ws = get_current_worksheet()
    if not ws:
        return pd.DataFrame()

    # Explizit nur A bis J abrufen, damit Spalte K nicht stört
    # Wir gehen davon aus, dass Header in Zeile 1 stehen
    data = ws.get("A:J") 
    
    if not data:
        return pd.DataFrame()

    # Erste Zeile als Header, Rest als Daten
    headers = data.pop(0)
    df = pd.DataFrame(data, columns=headers)
    return df

def clear_google_sheet():
    """Löscht Log-Daten (A2:J...), behält Spalte K."""
    ws = get_current_worksheet()
    if ws:
        # Lösche nur den Bereich A2 bis J10000 (Spalte K bleibt sicher)
        ws.batch_clear(["A2:J10000"])

def log_reset_event(roll_size, note=""):
    """Schreibt den Reset-Event in das Log (erste Zeile nach Header)."""
    ws = get_current_worksheet()
    if ws:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Spaltenstruktur anpassen je nach deinem Sheet (Beispiel: Timestamp, Event, Details...)
        # Hier fügen wir einfach eine Zeile an. 
        row = [now_str, "RESET", f"Neue Rolle: {roll_size}", note]
        ws.append_row(row)

def send_ntfy_push(title, message, priority="default", tags="printer"):
    """Sendet Push Notification via ntfy.sh"""
    # Prüfen ob im State aktiv
    if not st.session_state.get("ntfy_active", True):
        return
    
    topic = st.session_state.get("ntfy_topic")
    if not topic:
        return

    try:
        requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode("utf-8"),
            headers={
                "Title": title.encode("utf-8"),
                "Priority": priority,
                "Tags": tags,
            },
            timeout=5
        )
    except Exception as e:
        print(f"Push Error: {e}")

# --- INIT SESSION STATE ---
if "confirm_reset" not in st.session_state:
    st.session_state.confirm_reset = False
if "ntfy_active" not in st.session_state:
    st.session_state.ntfy_active = NTFY_ACTIVE_DEFAULT
if "last_warn_status" not in st.session_state:
    st.session_state.last_warn_status = None
if "max_prints" not in st.session_state:
    st.session_state.max_prints = 400
if "selected_printer_name" not in st.session_state:
    st.session_state.selected_printer_name = None

# --- SIDEBAR ---
st.sidebar.header("Einstellungen")

# Auswahl der Box
printer_name = st.sidebar.selectbox(
    "Fotobox auswählen", 
    list(PRINTERS.keys()),
    index=0 
)

# Wenn sich die Box ändert, Config aktualisieren
if printer_name != st.session_state.selected_printer_name:
    st.session_state.selected_printer_name = printer_name
    conf = PRINTERS[printer_name]
    st.session_state.current_sheet_id = conf["sheet_id"]
    st.session_state.ntfy_topic = conf["ntfy_topic"]
    st.session_state.default_max = conf["default_max_prints"]
    
    # Hier: Push-Setting aus Sheet laden!
    is_push_active = load_push_setting_from_sheet()
    st.session_state.ntfy_active = is_push_active
    # Reset Logik zurücksetzen
    st.session_state.confirm_reset = False
    st.session_state.max_prints = conf["default_max_prints"]

event_mode = st.sidebar.toggle("Event-Ansicht (nur Status)", value=False)
sound_enabled = st.sidebar.checkbox("Warnton aktiv", value=True)

# --- LOGIK: DATEN AUFBEREITEN ---
df = get_data()

# --- UI: HAUPTBEREICH ---
st.title(f"{PAGE_TITLE} – {printer_name}")

if df.empty:
    st.info("System wartet auf Start... (Datenblatt ist leer oder konnte nicht gelesen werden)")
    st.write("Warte auf erste Druckdaten...")
else:
    # Hier deine Logik zur Analyse des Dataframes
    # Da ich nicht genau weiß, wie deine Spalten heißen, 
    # nehme ich an, dass die Anzahl der Zeilen = Anzahl Drucke ist, 
    # oder es gibt eine Spalte "Prints". 
    # BEISPIEL-LOGIK (Anpassen falls nötig):
    total_prints = len(df) # oder df['Prints'].sum()
    
    # Papierberechnung
    remaining = st.session_state.max_prints - total_prints
    progress = max(0, min(1.0, total_prints / st.session_state.max_prints))
    
    # Darstellung Live Status
    col_metric1, col_metric2 = st.columns(2)
    col_metric1.metric("Gedruckte Fotos", total_prints)
    col_metric2.metric("Verbleibend", remaining)
    
    st.progress(progress)
    
    if remaining <= PRINTERS[printer_name]["warning_threshold"]:
        st.error(f"⚠️ ACHTUNG: Nur noch {remaining} Bilder übrig!")
        if sound_enabled:
            st.audio(ALERT_SOUND_URL, autoplay=True)
    else:
        st.success("Drucker bereit ✅")

    # Tabellen-Ansicht (optional)
    with st.expander("Detaillierte Daten anzeigen"):
        st.dataframe(df)

st.markdown("---")

# --- ADMIN BEREICH ---
if not event_mode:
    with st.expander("🛠️ Admin & Einstellungen", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            st.write("### Externe Links")
            st.link_button("🔗 Fotoshare Cloud", "https://fotoshare.co/admin/index", use_container_width=True)

            st.write("### Benachrichtigungen")
            st.code(st.session_state.ntfy_topic or "(kein Topic)")
            
            # CHECKBOX MIT SAVE-CALLBACK
            # Wir nutzen key='ntfy_active_checkbox' und synchronisieren via on_change
            st.checkbox(
                "Push aktiv (gespeichert in Spalte K)", 
                value=st.session_state.ntfy_active,
                key="ntfy_active_checkbox",
                on_change=save_push_setting_to_sheet
            )

            if st.button("Test Push 🔔"):
                send_ntfy_push("Test", "Dies ist ein Test von der Fotobox.", tags="tada")
                st.toast("Test-Nachricht gesendet!")

        with col2:
            st.write("### Neuer Auftrag / Papierwechsel")
            size = st.radio(
                "Paketgröße",
                [200, 400],
                horizontal=True,
                index=1 if st.session_state.max_prints == 400 else 0,
            )

            reset_note = st.text_input("Notiz (optional)", key="reset_note")

            if not st.session_state.confirm_reset:
                if st.button("Papierwechsel (Reset) 🔄", use_container_width=True):
                    st.session_state.confirm_reset = True
                    st.session_state.temp_package_size = size
                    st.rerun()
            else:
                st.warning(f"Log löschen & auf {st.session_state.temp_package_size}er Rolle setzen?")
                c_y, c_n = st.columns(2)
                if c_y.button("Ja, Reset", use_container_width=True):
                    st.session_state.max_prints = st.session_state.temp_package_size
                    # Nur Log löschen, Spalte K behalten
                    clear_google_sheet()
                    log_reset_event(st.session_state.temp_package_size, reset_note)
                    st.session_state.confirm_reset = False
                    st.rerun()
                if c_n.button("Abbrechen", use_container_width=True):
                    st.session_state.confirm_reset = False
                    st.rerun()
