import streamlit as st
import gspread
from gspread.exceptions import WorksheetNotFound
from google.oauth2.service_account import Credentials
import requests
import pandas as pd
from datetime import datetime
import time
import uuid
import hashlib
import json

# --------------------------------------------------------------------
# AQARA CLIENT
# --------------------------------------------------------------------


class AqaraClient:
    def __init__(self, app_id, key_id, app_secret, region="ger"):
        self.app_id = app_id
        self.key_id = key_id
        self.app_secret = app_secret
        # laut Doku: https://${domain}/v3.0/open/api
        self.base_url = f"https://open-{region}.aqara.com/v3.0/open/api"

    def _generate_headers(self, access_token=None):
        """
        Erstellt die nötige Signatur für Aqara V3.

        Sign-Regel:
        - Nimm alle Header-Parameter aus {Accesstoken, Appid, Keyid, Nonce, Time},
          die im Request verwendet werden.
        - Sortiere sie nach ASCII des Keys.
        - Verketten: key1=val1&key2=val2&... + app_secret
        - alles zu lowercase() und dann md5 -> hex.
        """
        nonce = uuid.uuid4().hex
        timestamp = str(int(time.time() * 1000))

        # Parameter, die in die Signatur gehören
        sign_params = {
            "Appid": self.app_id,
            "Keyid": self.key_id,
            "Nonce": nonce,
            "Time": timestamp,
        }
        if access_token:
            sign_params["Accesstoken"] = access_token

        # ASCII-sortiert zusammensetzen
        sign_str = "&".join(
            f"{k}={sign_params[k]}" for k in sorted(sign_params.keys())
        )
        sign_str += self.app_secret

        # laut Beispielen: alles lowercase vor dem Hash
        sign = hashlib.md5(sign_str.lower().encode("utf-8")).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "Appid": self.app_id,
            "Keyid": self.key_id,
            "Nonce": nonce,
            "Time": timestamp,
            "Sign": sign,
            "Lang": "de",
        }
        if access_token:
            headers["Accesstoken"] = access_token
        return headers

    def get_device_value(self, access_token, device_id, resource_name: str):
        """
        Liest einen Sensorwert über Aqara V3.

        intent: query.resource.value
        data.resources[].resourceIds -> laut offizieller Doku
        """
        url = self.base_url
        headers = self._generate_headers(access_token)

        payload = {
            "intent": "query.resource.value",
            "data": {
                "resources": [
                    {
                        "subjectId": device_id,
                        "resourceIds": [resource_name],
                    }
                ]
            },
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            data = response.json()

            # Erfolg
            if data.get("code") == 0 and data.get("result"):
                first = data["result"][0]
                return first.get("value")

            # Fehlertext möglichst klar extrahieren
            msg = (
                data.get("message")
                or data.get("msgDetails")
                or f"Code {data.get('code', 'unbekannt')}"
            )
            return f"Fehler: {msg}"

        except Exception as e:
            return f"Verbindungsfehler: {str(e)}"

    def switch_socket(
        self,
        access_token,
        device_id,
        turn_on: bool,
        resource_id="4.1.85",
        mode: str = "state",
    ):
        """
        Schaltet eine Steckdose.

        intent: write.resource.device

        mode="state":
            0 = AUS, 1 = EIN (turn_on steuert den Zustand)
        mode="toggle":
            2 = TOGGLE (unabhängig von turn_on)
        """
        url = self.base_url
        headers = self._generate_headers(access_token)

        if mode == "toggle":
            value = "2"
        else:
            value = "1" if turn_on else "0"  # 0/1 als String

        payload = {
            "intent": "write.resource.device",
            "data": [
                {
                    "subjectId": device_id,
                    "resources": [
                        {
                            "resourceId": resource_id,
                            "value": value,
                        }
                    ],
                }
            ],
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            return response.json()
        except Exception as e:
            return {"code": -1, "message": str(e)}


# --------------------------------------------------------------------
# AQARA Farbsettings
# --------------------------------------------------------------------


def temp_color_and_label(temp: float | None):
    """
    Gibt (Farbe, Zusatzlabel) für eine Temperatur zurück.
    """
    if temp is None:
        return "#e5e7eb", ""  # grau

    if temp < 10:
        return "#bfdbfe", "kalt"
    if temp < 18:
        return "#93c5fd", "frisch"
    if temp <= 27:
        return "#bbf7d0", "ideal"
    if temp <= 32:
        return "#fed7aa", "warm"
    return "#fecaca", "heiß"


def hum_color_and_label(hum: float | None):
    """
    Gibt (Farbe, Zusatzlabel) für relative Luftfeuchte zurück.
    """
    if hum is None:
        return "#e5e7eb", ""

    if hum < 30:
        return "#fed7aa", "sehr trocken"
    if hum <= 60:
        return "#bbf7d0", "ok"
    if hum <= 75:
        return "#bfdbfe", "feucht"
    return "#fecaca", "sehr feucht"


# --------------------------------------------------------------------
# AQARA KONFIG AUS SECRETS
# --------------------------------------------------------------------
AQARA_ENABLED = False
aqara_client = None
AQARA_ACCESS_TOKEN = None
AQARA_SOCKET_DEVICE_ID = None
AQARA_SOCKET_RESOURCE_ID = "4.1.85"
AQARA_SENSOR_DEVICE_ID = None
AQARA_TEMP_RESOURCE = "0.1.85"
AQARA_HUM_RESOURCE = "0.2.85"

try:
    aqara_cfg = st.secrets["aqara"]
    AQARA_APP_ID = aqara_cfg["app_id"]
    AQARA_KEY_ID = aqara_cfg["key_id"]
    AQARA_APP_SECRET = aqara_cfg["app_secret"]
    AQARA_ACCESS_TOKEN = aqara_cfg["access_token"]

    AQARA_SOCKET_DEVICE_ID = aqara_cfg["socket_device_id"]
    AQARA_SOCKET_RESOURCE_ID = aqara_cfg.get("socket_resource_id", "4.1.85")

    AQARA_SENSOR_DEVICE_ID = aqara_cfg.get("sensor_device_id")
    AQARA_TEMP_RESOURCE = aqara_cfg.get("temperature_resource", "0.1.85")
    AQARA_HUM_RESOURCE = aqara_cfg.get("humidity_resource", "0.2.85")

    aqara_client = AqaraClient(
        app_id=AQARA_APP_ID,
        key_id=AQARA_KEY_ID,
        app_secret=AQARA_APP_SECRET,
        region="ger",
    )
    AQARA_ENABLED = True
except Exception:
    AQARA_ENABLED = False


def get_environment_values():
    """
    Holt Temperatur & Luftfeuchte vom Aqara-Sensor.
    Gibt (temp, hum, error_msg) zurück.

    Aqara liefert 0.01-Einheiten, z.B. 3203 = 32.03.
    """
    if not (AQARA_ENABLED and AQARA_SENSOR_DEVICE_ID and aqara_client):
        return None, None, "Aqara-Sensor nicht konfiguriert."

    temp_raw = aqara_client.get_device_value(
        AQARA_ACCESS_TOKEN,
        AQARA_SENSOR_DEVICE_ID,
        AQARA_TEMP_RESOURCE,
    )
    hum_raw = aqara_client.get_device_value(
        AQARA_ACCESS_TOKEN,
        AQARA_SENSOR_DEVICE_ID,
        AQARA_HUM_RESOURCE,
    )

    # Fehlermeldungen der API direkt weitergeben
    if isinstance(temp_raw, str) and temp_raw.startswith(("Fehler", "Verbindungsfehler")):
        return None, None, temp_raw
    if isinstance(hum_raw, str) and hum_raw.startswith(("Fehler", "Verbindungsfehler")):
        return None, None, hum_raw

    try:
        temp_val = float(temp_raw)
    except Exception:
        temp_val = None

    try:
        hum_val = float(hum_raw)
    except Exception:
        hum_val = None

    temp = temp_val / 100.0 if temp_val is not None else None
    hum = hum_val / 100.0 if hum_val is not None else None

    return temp, hum, None


# --------------------------------------------------------------------
# GLOBAL KONFIG
# --------------------------------------------------------------------
PAGE_TITLE = "Fotobox Drucker Status"
PAGE_ICON = "🖨️"

PRINTERS = {
    "Standard Fotobox": {
        "sheet_id": "10uLjotNMT3AewBHdkuYyOudbbOCEuquDqGbwr2Wu7ig",
        "ntfy_topic": "fotobox_status_secret_4566",
        "warning_threshold": 20,
        "default_max_prints": 400,
        "cost_per_roll_eur": 46.59,
    },
}

HEARTBEAT_WARN_MINUTES = 5
NTFY_ACTIVE_DEFAULT = True
ALERT_SOUND_URL = "https://actions.google.com/sounds/v1/alarms/beep_short.ogg"

# --------------------------------------------------------------------
# LAYOUT & SESSION STATE
# --------------------------------------------------------------------
st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="centered")

if "confirm_reset" not in st.session_state:
    st.session_state.confirm_reset = False
if "ntfy_active" not in st.session_state:
    st.session_state.ntfy_active = NTFY_ACTIVE_DEFAULT
if "last_warn_status" not in st.session_state:
    st.session_state.last_warn_status = None
if "last_sound_status" not in st.session_state:
    st.session_state.last_sound_status = None
if "max_prints" not in st.session_state:
    st.session_state.max_prints = None
if "selected_printer" not in st.session_state:
    st.session_state.selected_printer = None

st.sidebar.header("Einstellungen")
printer_name = st.sidebar.selectbox("Fotobox auswählen", list(PRINTERS.keys()))
event_mode = st.sidebar.toggle("Event-Ansicht (nur Status)", value=False)
sound_enabled = st.sidebar.toggle("Sound bei Warnungen", value=False)

printer_cfg = PRINTERS[printer_name]

if st.session_state.selected_printer != printer_name:
    st.session_state.selected_printer = printer_name
    st.session_state.last_warn_status = None
    st.session_state.last_sound_status = None
    st.session_state.max_prints = printer_cfg["default_max_prints"]

st.session_state.sheet_id = printer_cfg["sheet_id"]
st.session_state.ntfy_topic = printer_cfg["ntfy_topic"]
WARNING_THRESHOLD = printer_cfg["warning_threshold"]
COST_PER_ROLL_EUR = printer_cfg["cost_per_roll_eur"]


# --------------------------------------------------------------------
# PUSH FUNKTION
# --------------------------------------------------------------------
def send_ntfy_push(title, message, tags="warning", priority="default"):
    if not st.session_state.ntfy_active:
        return
    topic = st.session_state.get("ntfy_topic")
    if not topic:
        return
    try:
        headers = {
            "Title": title.encode("utf-8"),
            "Tags": tags,
            "Priority": priority,
        }
        requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode("utf-8"),
            headers=headers,
            timeout=5,
        )
    except Exception:
        pass  # Dashboard soll nicht crashen


# --------------------------------------------------------------------
# GOOGLE SHEETS
# --------------------------------------------------------------------
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
    return get_spreadsheet().sheet1


@st.cache_data(ttl=10)
def get_data(sheet_id: str):
    try:
        ws = get_gspread_client().open_by_key(sheet_id).sheet1
        return pd.DataFrame(ws.get_all_records())
    except Exception:
        return pd.DataFrame()


def clear_google_sheet():
    try:
        ws = get_main_worksheet()
        ws.batch_clear(["A2:Z10000"])
        get_data.clear()
        st.toast("Log erfolgreich zurückgesetzt!", icon="♻️")
    except Exception as e:
        st.error(f"Fehler beim Reset: {e}")


def log_reset_event(package_size: int, note: str = ""):
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


# --------------------------------------------------------------------
# STATUS-LOGIK
# --------------------------------------------------------------------
def evaluate_status(raw_status: str, media_remaining: int, timestamp: str):
    prev_status = st.session_state.last_warn_status
    raw_status_l = (raw_status or "").lower()

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

    minutes_diff = None
    ts_parsed = pd.to_datetime(timestamp, errors="coerce")
    if pd.notna(ts_parsed):
        delta = datetime.now() - ts_parsed.to_pydatetime()
        minutes_diff = int(delta.total_seconds() // 60)
        if minutes_diff >= HEARTBEAT_WARN_MINUTES and status_mode != "error":
            status_mode = "stale"
            display_text = "⚠️ Keine aktuellen Daten"
            display_color = "orange"

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


# --------------------------------------------------------------------
# UI START
# --------------------------------------------------------------------
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

        (
            status_mode,
            display_text,
            display_color,
            push,
            minutes_diff,
        ) = evaluate_status(raw_status, media_remaining, timestamp)

        if push is not None:
            title, msg, tags = push
            send_ntfy_push(title, msg, tags=tags)

        maybe_play_sound(status_mode, sound_enabled)

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

        # Papierstatus
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

        # Progress-Bar
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

    if "Timestamp" in df.columns and "Media_Remaining" in df.columns:
        df_plot = df.copy()
        df_plot["Timestamp"] = pd.to_datetime(df_plot["Timestamp"], errors="coerce")
        df_plot = df_plot.dropna(subset=["Timestamp"]).set_index("Timestamp")
        st.line_chart(df_plot["Media_Remaining"], use_container_width=True)

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


# --------------------------------------------------------------------
# RENDER
# --------------------------------------------------------------------
if event_mode:
    show_live_status(sound_enabled)
else:
    tab_live, tab_hist = st.tabs(["Live-Status", "Historie & Analyse"])
    with tab_live:
        show_live_status(sound_enabled)
    with tab_hist:
        show_history()

st.markdown("---")

# --------------------------------------------------------------------
# ADMIN
# --------------------------------------------------------------------
if not event_mode:
    with st.expander("🛠️ Admin & Einstellungen"):
        col1, col2 = st.columns(2)

        # LINKS & BENACHRICHTIGUNGEN
        with col1:
            st.write("### Externe Links")
            st.link_button(
                "🔗 Fotoshare Cloud",
                "https://fotoshare.co/admin/index",
                use_container_width=True,
            )

            st.write("### Benachrichtigungen")
            st.code(st.session_state.ntfy_topic or "(kein Topic konfiguriert)")
            st.session_state.ntfy_active = st.checkbox(
                "Push aktiv", st.session_state.ntfy_active
            )

            if st.button("Test Push 🔔"):
                send_ntfy_push("Test", "Test erfolgreich", tags="tada")
                st.toast("Test gesendet!")

        # PAPIER / RESET
        with col2:
            st.write("### Neuer Auftrag / Papierwechsel")
            size = st.radio(
                "Paketgröße",
                [200, 400],
                horizontal=True,
                index=1 if st.session_state.max_prints == 400 else 0,
            )

            reset_note = st.text_input(
                "Notiz zum Papierwechsel (optional)", key="reset_note"
            )

            if not st.session_state.confirm_reset:
                if st.button(
                    "Papierwechsel durchgeführt (Reset) 🔄",
                    use_container_width=True,
                ):
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

        st.markdown("---")

        # BOX-OBERTEIL (Temperatur / Luftfeuchte)
        st.write("### Box-Oberteil (Temperatur & Luftfeuchtigkeit)")
        if not (AQARA_ENABLED and AQARA_SENSOR_DEVICE_ID):
            st.caption("Aqara-Sensor ist nicht konfiguriert.")
        else:
            temp, hum, err = get_environment_values()

            if err:
                st.error(f"Fehler: {err}")
            else:
                colT, colH = st.columns(2)

                # --- Temperatur-Anzeige mit Farbe ---
                temp_color, temp_label = temp_color_and_label(temp)
                temp_html = f"""
                <div style="
                    background-color:{temp_color};
                    padding:10px 14px;
                    border-radius:8px;
                    border:1px solid #d1d5db;
                ">
                    <div style="font-size:13px; color:#374151; margin-bottom:2px;">
                        Temperatur
                    </div>
                    <div style="font-size:22px; font-weight:600; color:#111827;">
                        {temp if temp is not None else "–"} °C
                    </div>
                    <div style="font-size:12px; color:#4b5563; margin-top:2px;">
                        {temp_label}
                    </div>
                </div>
                """
                colT.markdown(temp_html, unsafe_allow_html=True)

                # --- Luftfeuchte-Anzeige mit Farbe ---
                hum_color, hum_label = hum_color_and_label(hum)
                hum_html = f"""
                <div style="
                    background-color:{hum_color};
                    padding:10px 14px;
                    border-radius:8px;
                    border:1px solid #d1d5db;
                ">
                    <div style="font-size:13px; color:#374151; margin-bottom:2px;">
                        Luftfeuchtigkeit
                    </div>
                    <div style="font-size:22px; font-weight:600; color:#111827;">
                        {hum if hum is not None else "–"} %
                    </div>
                    <div style="font-size:12px; color:#4b5563; margin-top:2px;">
                        {hum_label}
                    </div>
                </div>
                """
                colH.markdown(hum_html, unsafe_allow_html=True)

            # Optional kleines Debug, falls wir weiter graben müssen
            if st.checkbox("Aqara Sensor Debug anzeigen", value=False):
                temp_raw = aqara_client.get_device_value(
                    AQARA_ACCESS_TOKEN,
                    AQARA_SENSOR_DEVICE_ID,
                    AQARA_TEMP_RESOURCE,
                )
                hum_raw = aqara_client.get_device_value(
                    AQARA_ACCESS_TOKEN,
                    AQARA_SENSOR_DEVICE_ID,
                    AQARA_HUM_RESOURCE,
                )
                st.write("Temp raw:", temp_raw)
                st.write("Hum raw:", hum_raw)

        st.markdown("---")

        # AQARA STECKDOSE
        st.write("### Aqara Steckdose Fotobox")
        if not AQARA_ENABLED:
            st.info(
                "Aqara ist nicht konfiguriert. Bitte [aqara] in secrets.toml setzen."
            )
        else:
            col_toggle, col_on, col_off = st.columns(3)

            if col_toggle.button("Toggle 🔁", use_container_width=True):
                res = aqara_client.switch_socket(
                    AQARA_ACCESS_TOKEN,
                    AQARA_SOCKET_DEVICE_ID,
                    turn_on=True,
                    resource_id=AQARA_SOCKET_RESOURCE_ID,
                    mode="toggle",
                )
                if res.get("code") == 0:
                    st.success("Steckdose getoggelt.")
                else:
                    st.error("Fehler beim Toggle:")
                    st.code(json.dumps(res, indent=2))

            if col_on.button("Steckdose AN 🔌", use_container_width=True):
                res = aqara_client.switch_socket(
                    AQARA_ACCESS_TOKEN,
                    AQARA_SOCKET_DEVICE_ID,
                    turn_on=True,
                    resource_id=AQARA_SOCKET_RESOURCE_ID,
                    mode="state",
                )
                if res.get("code") == 0:
                    st.success("Steckdose eingeschaltet.")
                else:
                    st.error("Fehler beim Einschalten:")
                    st.code(json.dumps(res, indent=2))

            if col_off.button("Steckdose AUS ⛔", use_container_width=True):
                res = aqara_client.switch_socket(
                    AQARA_ACCESS_TOKEN,
                    AQARA_SOCKET_DEVICE_ID,
                    turn_on=False,
                    resource_id=AQARA_SOCKET_RESOURCE_ID,
                    mode="state",
                )
                if res.get("code") == 0:
                    st.success("Steckdose ausgeschaltet.")
                else:
                    st.error("Fehler beim Ausschalten:")
                    st.code(json.dumps(res, indent=2))
