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

# Mehrere Boxen vorbereitet – aktuell eine befüllt.
PRINTERS = {
    "Standard Fotobox": {
        "sheet_id": "10uLjotNMT3AewBHdkuYyOudbbOCEuquDqGbwr2Wu7ig",
        "ntfy_topic": "fotobox_status_secret_4566",
        "warning_threshold": 20,
        "default_max_prints": 400,
        "cost_per_roll_eur": 46.58,
    },
    "Fotobox Laurentius": {
        "sheet_id": "HIER_DIE_NEUE_SHEET_ID_EINSETZEN",
        "ntfy_topic": "fotobox_status_secret_4566-weinkellerei",
        "warning_threshold": 50,      # kannst du bei Bedarf anpassen
        "default_max_prints": 400,    # oder 200, je nach Rolle
        "cost_per_roll_eur": None,    # oder None, wenn du die Kosten nicht brauchst
    },
}


HEARTBEAT_WARN_MINUTES = 60      # ab wann "keine aktuellen Daten" gewarnt wird
NTFY_ACTIVE_DEFAULT = True
ALERT_SOUND_URL = "https://actions.google.com/sounds/v1/alarms/beep_short.ogg"  # optionaler Warnton

# --- SEITEN LAYOUT ---
st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="centered")

# --- SESSION STATE INIT ---
if "confirm_reset" not in st.session_state:
    st.session_state.confirm_reset = False
if "ntfy_active" not in st.session_state:
    st.session_state.ntfy_active = NTFY_ACTIVE_DEFAULT
if "last_warn_status" not in st.session_state:
    st.session_state.last_warn_status = None
if "last_sound_status" not in st.session_state:
    st.session_state.last_sound_status = None
if "max_prints" not in st.session_state:
    st.session_state.max_prints = None      # wird nach Box-Auswahl gesetzt
if "selected_printer" not in st.session_state:
    st.session_state.selected_printer = None

# --- SIDEBAR: BOX & ANSICHT ---
st.sidebar.header("Einstellungen")
printer_name = st.sidebar.selectbox("Fotobox auswählen", list(PRINTERS.keys()))
event_mode = st.sidebar.toggle("Event-Ansicht (nur Status)", value=False)
sound_enabled = st.sidebar.toggle("Sound bei Warnungen", value=False)

# Konfiguration der gewählten Box in Session übernehmen
printer_cfg = PRINTERS[printer_name]

if st.session_state.selected_printer != printer_name:
    # Beim Box-Wechsel Status zurücksetzen
    st.session_state.selected_printer = printer_name
    st.session_state.last_warn_status = None
    st.session_state.last_sound_status = None
    st.session_state.max_prints = printer_cfg["default_max_prints"]

st.session_state.sheet_id = printer_cfg["sheet_id"]
st.session_state.ntfy_topic = printer_cfg["ntfy_topic"]
WARNING_THRESHOLD = printer_cfg["warning_threshold"]
COST_PER_ROLL_EUR = printer_cfg["cost_per_roll_eur"]

# --- FUNKTIONEN: PUSH ---
def send_ntfy_push(title, message, tags="warning", priority="default"):
    if not st.session_state.ntfy_active:
        return
    topic = st.session_state.get("ntfy_topic")
    if not topic:
        return
    try:
        headers = {"Title": title.encode("utf-8"), "Tags": tags, "Priority": priority}
        requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode("utf-8"),
            headers=headers,
            timeout=5,
        )
    except Exception:
        # bewusst leise – Dashboard soll nicht crashen, wenn ntfy nicht geht
        pass

# --- FUNKTIONEN: GOOGLE SHEETS ---
def get_gspread_client():
    secrets = st.secrets["gcp_service_account"]
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(secrets, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc

def get_spreadsheet():
    gc = get_gspread_client()
    sheet_id = st.session_state.sheet_id
    return gc.open_by_key(sheet_id)

def get_main_worksheet():
    # Annahme: erste Tabelle = Log vom Drucker
    return get_spreadsheet().sheet1

@st.cache_data(ttl=10)
def get_data(sheet_id: str):
    try:
        ws = get_gspread_client().open_by_key(sheet_id).sheet1
        return pd.DataFrame(ws.get_all_records())
    except Exception:
        return pd.DataFrame()

def clear_google_sheet():
    """Log (A2:Z) der Haupt-Tabelle leeren."""
    try:
        ws = get_main_worksheet()
        ws.batch_clear(["A2:Z10000"])
        get_data.clear()
        st.toast("Log erfolgreich zurückgesetzt!", icon="♻️")
    except Exception as e:
        st.error(f"Fehler beim Reset: {e}")

def log_reset_event(package_size: int, note: str = ""):
    """Papierwechsel in separater 'Meta'-Tabelle protokollieren."""
    try:
        sh = get_spreadsheet()
        try:
            meta_ws = sh.worksheet("Meta")
        except WorksheetNotFound:
            meta_ws = sh.add_worksheet(title="Meta", rows=1000, cols=10)
            meta_ws.append_row(["Timestamp", "PackageSize", "Note"])
        meta_ws.append_row(
            [datetime.now().isoformat(timespec="seconds"), package_size, note]
        )
    except Exception as e:
        st.warning(f"Reset konnte nicht im Meta-Log gespeichert werden: {e}")

# --- STATUS-LOGIK ---
def evaluate_status(raw_status: str, media_remaining: int, timestamp: str):
    """Ermittelt Status-Modus, Anzeige-Text/Farbe und ggf. Push-Meldung."""
    prev_status = st.session_state.last_warn_status

    raw_status_l = (raw_status or "").lower()

    # Grund-Status anhand Status-Text & Papier
    if any(w in raw_status_l for w in ["error", "fehler", "stau", "failure", "unknown"]):
        status_mode = "error"
        display_text = f"⚠️ STÖRUNG: {raw_status}"
        display_color = "red"
    elif media_remaining <= WARNING_THRESHOLD:
        status_mode = "low_paper"
        display_text = "⚠️ Papier fast leer!"
        display_color = "orange"
    elif "printing" in raw_status_l or "processing" in raw_status_l:
        status_mode = "printing"
        display_text = "🖨️ Druckt gerade…"
        display_color = "blue"
    else:
        status_mode = "ready"
        display_text = "✅ Bereit"
        display_color = "green"

    # Heartbeat / keine aktuellen Daten
    minutes_diff = None
    ts_parsed = pd.to_datetime(timestamp, errors="coerce")
    if pd.notna(ts_parsed):
        delta = datetime.now() - ts_parsed.to_pydatetime()
        minutes_diff = int(delta.total_seconds() // 60)
        if minutes_diff >= HEARTBEAT_WARN_MINUTES and status_mode != "error":
            status_mode = "stale"
            display_text = "⚠️ Keine aktuellen Daten"
            display_color = "orange"

    # Push-Entscheidung
    push = None
    if status_mode == "error" and prev_status != "error":
        push = ("🔴 Fehler", f"Druckerfehler: {raw_status}", "rotating_light")
    elif status_mode == "low_paper" and prev_status != "low_paper":
        push = ("⚠️ Papierwarnung", f"Noch {media_remaining} Bilder!", "warning")
    elif status_mode == "stale" and prev_status != "stale":
        if minutes_diff is not None:
            push = (
                "⚠️ Keine aktuellen Daten",
                f"Seit {minutes_diff} Minuten kein Signal von der Fotobox.",
                "warning",
            )
    elif prev_status == "error" and status_mode not in ["error", None]:
        push = ("✅ Störung behoben", "Drucker läuft wieder.", "white_check_mark")

    # Session-Status aktualisieren
    st.session_state.last_warn_status = status_mode

    return status_mode, display_text, display_color, push, minutes_diff

def maybe_play_sound(status_mode: str, sound_enabled: bool):
    if not sound_enabled or not ALERT_SOUND_URL:
        return
    prev = st.session_state.last_sound_status
    if status_mode in ["error", "low_paper"] and prev != status_mode:
        st.session_state.last_sound_status = status_mode
        st.markdown(
            f"""
            <audio autoplay>
                <source src="{ALERT_SOUND_URL}" type="audio/ogg">
            </audio>
            """,
            unsafe_allow_html=True,
        )
    elif status_mode not in ["error", "low_paper"] and prev is not None:
        st.session_state.last_sound_status = None

# --- START DES UI ---
st.title(f"{PAGE_ICON} {PAGE_TITLE}")

@st.fragment(run_every=10)
def show_live_status(sound_enabled: bool = False):
    df = get_data(st.session_state.sheet_id)
    if df.empty:
        st.info("System wartet auf Start…")
        st.caption("Noch keine Druckdaten empfangen.")
        return

    try:
        last = df.iloc[-1]
        timestamp = str(last.get("Timestamp", ""))
        raw_status = str(last.get("Status", ""))
        media_remaining = int(last.get("Media_Remaining", 0))

        status_mode, display_text, display_color, push, minutes_diff = evaluate_status(
            raw_status, media_remaining, timestamp
        )

        if push is not None:
            title, msg, tags = push
            send_ntfy_push(title, msg, tags=tags)

        maybe_play_sound(status_mode, sound_enabled)

        # --- HEADER ---
        heartbeat_info = ""
        if minutes_diff is not None:
            heartbeat_info = f" (vor {minutes_diff} Min)"

        header_html = f"""
        <div style='text-align: left; margin-top: 0;'>
            <h2 style='color:{display_color}; font-weight: 700; margin-bottom: 4px;'>
                {display_text}
            </h2>
            <div style='color: #666; font-size: 14px; margin-bottom: 12px;'>
                Letztes Signal: {timestamp}{heartbeat_info}
            </div>
        </div>
        """

        st.markdown(header_html, unsafe_allow_html=True)

        if status_mode == "error":
            st.error("Bitte Drucker prüfen (Störung aktiv).")
        elif status_mode == "stale":
            st.warning("Seit einigen Minuten keine Daten – Verbindung / Script prüfen.")

        # --- PAPIERSTATUS ---
        st.markdown("### Papierstatus")

        if status_mode == "error":
            remaining_text = "–"
            forecast = "Unbekannt (Störung)"
        else:
            remaining_text = f"{media_remaining} Stk"
            if media_remaining > 0:
                m = int(media_remaining * 1.5)
                forecast = f"{m} Min." if m < 60 else f"{m//60} Std. {m%60} Min."
            else:
                forecast = "0 Min."

        colA, colB, colC = st.columns(3)
        colA.metric("Verbleibend", remaining_text, f"von {st.session_state.max_prints}")
        colB.metric("Restlaufzeit (geschätzt)", forecast)

        # Kosten-Anzeige, falls konfiguriert
        if COST_PER_ROLL_EUR:
            try:
                used = max(0, st.session_state.max_prints - media_remaining)
                cost_per_print = COST_PER_ROLL_EUR / st.session_state.max_prints
                cost_used = used * cost_per_print
                colC.metric("Kosten seit Reset", f"{cost_used:0.2f} €")
            except Exception:
                colC.metric("Kosten seit Reset", "–")
        else:
            colC.metric("Kosten seit Reset", "–")

        # Farbbalken
        if status_mode == "error":
            bar_color = "red"
            progress_val = 0
        else:
            progress_val = max(0, min(1, media_remaining / st.session_state.max_prints))
            if progress_val < 0.1:
                bar_color = "red"
            elif progress_val < 0.25:
                bar_color = "orange"
            else:
                bar_color = "blue"

        st.markdown(
            f"""
            <style>
            .stProgress > div > div > div > div {{
                background-color: {bar_color};
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.progress(progress_val)

    except Exception as e:
        st.error(f"Fehler bei der Datenverarbeitung: {e}")

def show_history():
    df = get_data(st.session_state.sheet_id)
    if df.empty:
        st.info("Noch keine Daten für die Historie.")
        return

    st.subheader("Verlauf & Analyse")

    # Zeitreihe vorbereiten
    if "Timestamp" in df.columns and "Media_Remaining" in df.columns:
        df_plot = df.copy()
        df_plot["Timestamp"] = pd.to_datetime(df_plot["Timestamp"], errors="coerce")
        df_plot = df_plot.dropna(subset=["Timestamp"]).set_index("Timestamp")
        st.line_chart(df_plot["Media_Remaining"], use_container_width=True)

    # Kennzahlen
    last = df.iloc[-1]
    try:
        media_remaining = int(last.get("Media_Remaining", 0))
    except Exception:
        media_remaining = 0

    total_rows = len(df)
    prints_since_reset = max(0, st.session_state.max_prints - media_remaining)

    c1, c2, c3 = st.columns(3)
    c1.metric("Log-Einträge", total_rows)
    c2.metric("Drucke (geschätzt)", prints_since_reset)
    if COST_PER_ROLL_EUR:
        try:
            cost_per_print = COST_PER_ROLL_EUR / st.session_state.max_prints
            cost_used = prints_since_reset * cost_per_print
            c3.metric("Kosten (geschätzt)", f"{cost_used:0.2f} €")
        except Exception:
            c3.metric("Kosten (geschätzt)", "–")
    else:
        c3.metric("Kosten (geschätzt)", "–")

    st.markdown("#### Rohdaten (letzte 200 Zeilen)")
    st.dataframe(df.tail(200), use_container_width=True)

# --- INHALT RENDERN ---
if event_mode:
    # Nur Live-Status anzeigen – ideal für Monitor/Kiosk
    show_live_status(sound_enabled)
else:
    tab_live, tab_hist = st.tabs(["Live-Status", "Historie & Analyse"])
    with tab_live:
        show_live_status(sound_enabled)
    with tab_hist:
        show_history()

st.markdown("---")

# --- ADMIN ---
if not event_mode:
    with st.expander("🛠️ Admin & Einstellungen"):
        col1, col2 = st.columns(2)

        with col1:
            st.write("### Externe Links")
            st.link_button(
                "🔗 Fotoshare Cloud", "https://fotoshare.co/admin/index", use_container_width=True
            )

            st.write("### Benachrichtigungen")
            st.code(st.session_state.ntfy_topic or "(kein Topic konfiguriert)")
            st.session_state.ntfy_active = st.checkbox("Push aktiv", st.session_state.ntfy_active)

            if st.button("Test Push 🔔"):
                send_ntfy_push("Test", "Test erfolgreich", tags="tada")
                st.toast("Test gesendet!")

        with col2:
            st.write("### Neuer Auftrag / Papierwechsel")
            size = st.radio(
                "Paketgröße",
                [200, 400],
                horizontal=True,
                index=1 if st.session_state.max_prints == 400 else 0,
            )

            reset_note = st.text_input("Notiz zum Papierwechsel (optional)", key="reset_note")

            if not st.session_state.confirm_reset:
                if st.button("Papierwechsel durchgeführt (Reset) 🔄", use_container_width=True):
                    st.session_state.confirm_reset = True
                    st.session_state.temp_package_size = size
                    st.session_state.temp_reset_note = reset_note
                    st.rerun()
            else:
                st.warning(
                    f"Log löschen & auf {st.session_state.temp_package_size}er Rolle setzen?",
                )
                y, n = st.columns(2)
                if y.button("Ja", use_container_width=True):
                    st.session_state.max_prints = st.session_state.temp_package_size
                    clear_google_sheet()
                    log_reset_event(
                        st.session_state.temp_package_size,
                        st.session_state.temp_reset_note,
                    )
                    st.session_state.confirm_reset = False
                    st.session_state.last_warn_status = None
                    st.rerun()
                if n.button("Nein", use_container_width=True):
                    st.session_state.confirm_reset = False
                    st.rerun()
