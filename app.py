import streamlit as st
import gspread
from gspread.exceptions import WorksheetNotFound
from google.oauth2.service_account import Credentials
import requests
import pandas as pd
import datetime
import time
import uuid
import hashlib
import json
import extra_streamlit_components as stx
import pytz

# --- PIN ABFRAGE START ---

def check_login():
    # Session State initialisieren
    if "is_logged_in" not in st.session_state:
        st.session_state["is_logged_in"] = False

    # Cookie Manager initialisieren
    cookie_manager = stx.CookieManager(key="fotobox_auth")
    
    # Echten PIN holen und als String casten
    secret_pin = str(st.secrets["general"]["app_pin"])
    
    # Cookie lesen
    cookie_val = cookie_manager.get("auth_pin")

    # --- PRÜFUNG 1: Ist der Nutzer laut Cookie schon eingeloggt? ---
    if cookie_val is not None and str(cookie_val) == secret_pin:
        st.session_state["is_logged_in"] = True
    
    # --- PRÜFUNG 2: Ist der Nutzer laut Session State eingeloggt? ---
    if st.session_state["is_logged_in"]:
        return True

    # --- FALL 3: Login Formular zeigen ---
    st.title("🔒 Zugriff geschützt")
    
    msg_placeholder = st.empty()

    with st.form("login_form"):
        user_input = st.text_input("Bitte PIN eingeben:", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            if str(user_input) == secret_pin:
                # 1. Session freigeben
                st.session_state["is_logged_in"] = True
                
                # 2. Cookie setzen
                expires = datetime.datetime.now() + datetime.timedelta(hours=1)
                cookie_manager.set("auth_pin", user_input, expires_at=expires)
                
                msg_placeholder.success("Login korrekt! Geht sofort los...")
                
                # Kurze Pause, dann Reload
                time.sleep(1)
                st.rerun()
            else:
                msg_placeholder.error("Falscher PIN!")

    # Hier stoppt alles, solange nicht eingeloggt
    st.stop()

# Login-Check ausführen, bevor irgendetwas anderes passiert
check_login()

# --- PIN ABFRAGE ENDE ---


# --------------------------------------------------------------------
# AQARA CLIENT
# --------------------------------------------------------------------

class AqaraClient:
    def __init__(self, app_id, key_id, app_secret, region="ger"):
        self.app_id = app_id
        self.key_id = key_id
        self.app_secret = app_secret
        self.base_url = f"https://open-{region}.aqara.com/v3.0/open/api"

    def _generate_headers(self, access_token=None):
        nonce = uuid.uuid4().hex
        timestamp = str(int(time.time() * 1000))

        sign_params = {
            "Appid": self.app_id,
            "Keyid": self.key_id,
            "Nonce": nonce,
            "Time": timestamp,
        }
        if access_token:
            sign_params["Accesstoken"] = access_token

        sign_str = "&".join(
            f"{k}={sign_params[k]}" for k in sorted(sign_params.keys())
        )
        sign_str += self.app_secret
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

    def _query_resource_value(self, access_token, device_id, resource_ids):
        if isinstance(resource_ids, str):
            resource_ids = [resource_ids]

        url = self.base_url
        headers = self._generate_headers(access_token)

        payload = {
            "intent": "query.resource.value",
            "data": {
                "resources": [
                    {
                        "subjectId": device_id,
                        "resourceIds": resource_ids,
                    }
                ]
            },
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            return response.json()
        except Exception as e:
            return {"code": -1, "message": str(e)}

    def get_socket_state(self, access_token, device_id, resource_id="4.1.85"):
        data = self._query_resource_value(access_token, device_id, resource_id)

        if data.get("code") != 0:
            return "unknown", data

        result = data.get("result")
        value = None

        if isinstance(result, list):
            for item in result:
                if item.get("resourceId") == resource_id and "value" in item:
                    value = item["value"]
                    break
        elif isinstance(result, dict):
            for item in result.get("data", []):
                if item.get("resourceId") == resource_id and "value" in item:
                    value = item["value"]
                    break
                for r in item.get("resources", []):
                    if r.get("resourceId") == resource_id and "value" in r:
                        value = r["value"]
                        break

        if value is None:
            return "unknown", data

        value_str = str(value).lower()
        if value_str in ("1", "true", "on"):
            return "on", data
        if value_str in ("0", "false", "off"):
            return "off", data

        return "unknown", data

    def switch_socket(
        self,
        access_token,
        device_id,
        turn_on: bool,
        resource_id="4.1.85",
        mode: str = "state",
    ):
        url = self.base_url
        headers = self._generate_headers(access_token)

        if mode == "toggle":
            value = "2"
        else:
            value = "1" if turn_on else "0"

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
# AQARA KONFIG AUS SECRETS
# --------------------------------------------------------------------
AQARA_ENABLED = False
aqara_client = None
AQARA_ACCESS_TOKEN = None
AQARA_SOCKET_DEVICE_ID = None
AQARA_SOCKET_RESOURCE_ID = "4.1.85"

try:
    aqara_cfg = st.secrets["aqara"]
    AQARA_APP_ID = aqara_cfg["app_id"]
    AQARA_KEY_ID = aqara_cfg["key_id"]
    AQARA_APP_SECRET = aqara_cfg["app_secret"]
    AQARA_ACCESS_TOKEN = aqara_cfg["access_token"]

    AQARA_SOCKET_DEVICE_ID = aqara_cfg["socket_device_id"]
    AQARA_SOCKET_RESOURCE_ID = aqara_cfg.get("socket_resource_id", "4.1.85")

    aqara_client = AqaraClient(
        app_id=AQARA_APP_ID,
        key_id=AQARA_KEY_ID,
        app_secret=AQARA_APP_SECRET,
        region="ger",
    )
    AQARA_ENABLED = True
except Exception:
    AQARA_ENABLED = False


# --------------------------------------------------------------------
# DSLRBOOTH STEUERUNG VIA NTFY (nur Topic, kein API-Key hier)
# --------------------------------------------------------------------
DSR_ENABLED = False
DSR_CONTROL_TOPIC = None

try:
    dsr_cfg = st.secrets["dsrbooth"]
    DSR_CONTROL_TOPIC = dsr_cfg.get("control_topic")
    if DSR_CONTROL_TOPIC:
        DSR_ENABLED = True
except Exception:
    DSR_ENABLED = False


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

HEARTBEAT_WARN_MINUTES = 60
NTFY_ACTIVE_DEFAULT = True
ALERT_SOUND_URL = "https://actions.google.com/sounds/v1/alarms/beep_short.ogg"

# --------------------------------------------------------------------
# LAYOUT & SESSION STATE
# --------------------------------------------------------------------
st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="centered")

# ---- Globales Styling für Settings / Karten ----
CUSTOM_CSS = """
<style>
.settings-wrapper {
  margin-top: 0.75rem;
}

/* generische Karten-Optik (wird aktuell nur für Device-Cards genutzt) */
.control-card {
  border-radius: 16px;
  padding: 14px 18px;
  background: linear-gradient(135deg, #ffffff, #f9fafb);
  border: 1px solid #e5e7eb;
  box-shadow: 0 18px 45px rgba(15,23,42,0.08);
  margin-bottom: 12px;
}

/* kleine Überschrift über der Karte */
.control-header-label {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: .08em;
  color:#9ca3af;
  margin-bottom: 2px;
}

/* Hauptzeile mit Icon + Text */
.control-headline {
  font-size: 1.05rem;
  font-weight: 600;
  color:#111827;
  display:flex;
  align-items:center;
  gap: 0.4rem;
  margin-bottom: 6px;
}

/* Status-Badge */
.status-pill {
  margin-top: 4px;
  padding: 4px 10px;
  border-radius:999px;
  font-size: 0.7rem;
  font-weight:600;
  display:inline-flex;
  align-items:center;
  gap:4px;
}
.status-pill--ok {
  background:#dcfce7;
  color:#166534;
}
.status-pill--muted {
  background:#e5e7eb;
  color:#374151;
}
.status-pill--warn {
  background:#fef3c7;
  color:#92400e;
}

/* Zusatzinfos unten */
.control-meta {
  margin-top: 6px;
  font-size: 0.7rem;
  color:#9ca3af;
}

/* rechte Spalte – wir brauchen nur ein sauberes Layout für das Radio */
.segment-wrapper {
  display:flex;
  justify-content:flex-end;
  align-items:center;
}

/* horizontales Radio etwas kompakter */
.control-card .stRadio > div {
  padding-top: 0;
}

/* ========= ADMIN-CARDS OBEN ========= */

.admin-card {
  border-radius: 18px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
  box-shadow: 0 12px 30px rgba(15,23,42,0.05);
  padding: 16px 18px;
  margin-bottom: 16px;
}

.admin-card-title {
  font-size: 18px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 10px;
}

.admin-card-subtitle {
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: .12em;
  color: #9ca3af;
  margin-top: 10px;
  margin-bottom: 4px;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

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
if "socket_state" not in st.session_state:
    st.session_state.socket_state = "unknown"
if "socket_debug" not in st.session_state:
    st.session_state.socket_debug = None
if "lockscreen_state" not in st.session_state:
    # Wir kennen den echten Status nicht → nur "letzte Aktion"
    st.session_state.lockscreen_state = "off"

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
        pass


def send_dsr_command(cmd: str):
    """
    Schickt einen einfachen Steuerbefehl ('lock_on' / 'lock_off')
    an das ntfy-Topic, das der Agent am Surface abonniert.
    """
    if not DSR_ENABLED or not DSR_CONTROL_TOPIC:
        return
    try:
        requests.post(
            f"https://ntfy.sh/{DSR_CONTROL_TOPIC}",
            data=cmd.encode("utf-8"),
            timeout=5,
        )
    except Exception:
        pass


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
            [datetime.datetime.now().isoformat(timespec="seconds"), package_size, note]
        )
    except Exception as e:
        st.warning(f"Reset konnte nicht im Meta-Log gespeichert werden: {e}")


# --------------------------------------------------------------------
# STATUS-LOGIK
# --------------------------------------------------------------------

def evaluate_status(raw_status: str, media_remaining: int, timestamp: str):
    prev_status = st.session_state.last_warn_status
    raw_status_l = (raw_status or "").lower().strip()

    # --- Gruppen laut Drucker-Status ---
    hard_errors = [
        "paper end",
        "ribbon end",
        "paper jam",
        "ribbon error",
        "paper definition error",
        "data error"
    ]

    cover_open_kw = ["cover open"]
    cooldown_kw = ["head cooling down"]
    printing_kw = ["printing", "processing", "drucken"]
    idle_kw = ["idle", "standby mode"]

    # ---------------------------------------------------
    # 1) Harte Fehler
    # ---------------------------------------------------
    if any(k in raw_status_l for k in hard_errors):
        status_mode = "error"
        display_text = f"🔴 STÖRUNG: {raw_status}"
        display_color = "red"

    # ---------------------------------------------------
    # 2) Cover Open → eigenes Level, orange
    # ---------------------------------------------------
    elif any(k in raw_status_l for k in cover_open_kw):
        status_mode = "cover_open"
        display_text = "⚠️ Deckel offen!"
        display_color = "orange"

    # ---------------------------------------------------
    # 3) Druckkopf kühlt ab
    # ---------------------------------------------------
    elif any(k in raw_status_l for k in cooldown_kw):
        status_mode = "cooldown"
        display_text = "⏳ Druckkopf kühlt ab…"
        display_color = "orange"

    # ---------------------------------------------------
    # 4) Papier fast leer (nur wenn kein Fehler)
    # ---------------------------------------------------
    elif media_remaining <= WARNING_THRESHOLD:
        status_mode = "low_paper"
        display_text = f"⚠️ Papier fast leer! ({media_remaining} Stk)"
        display_color = "orange"

    # ---------------------------------------------------
    # 5) Druckt gerade
    # ---------------------------------------------------
    elif any(k in raw_status_l for k in printing_kw):
        status_mode = "printing"
        display_text = "🖨️ Druckt gerade…"
        display_color = "blue"

    # ---------------------------------------------------
    # 6) Leerlauf
    # ---------------------------------------------------
    elif any(k in raw_status_l for k in idle_kw) or raw_status_l == "":
        status_mode = "ready"
        display_text = "✅ Bereit"
        display_color = "green"

    else:
        status_mode = "ready"
        display_text = f"✅ Bereit ({raw_status})"
        display_color = "green"

    # ---------------------------------------------------
    # HEARTBEAT
    # ---------------------------------------------------
    minutes_diff = None
    LOCAL_TZ = pytz.timezone("Europe/Vienna")
    ts_parsed = pd.to_datetime(timestamp, errors="coerce")

    if pd.notna(ts_parsed):
        # Falls Timestamp keine TZ hat → als lokale Zeit interpretieren
        if ts_parsed.tzinfo is None:
            ts_parsed = LOCAL_TZ.localize(ts_parsed)

        # Jetzt aktuellen Zeitpunkt ebenfalls in der gleichen TZ holen
        now_local = datetime.datetime.now(LOCAL_TZ)
        delta = now_local - ts_parsed
        minutes_diff = int(delta.total_seconds() // 60)

        if minutes_diff >= HEARTBEAT_WARN_MINUTES and status_mode not in ["error"]:
            status_mode = "stale"
            display_text = "⚠️ Keine aktuellen Daten"
            display_color = "orange"

    # ---------------------------------------------------
    # PUSH LOGIK
    # → nur bei Statuswechsel UND nur bei kritischen Zuständen
    # ---------------------------------------------------
    critical_states = ["error", "cover_open", "low_paper", "stale"]
    push = None

    if status_mode in critical_states and prev_status != status_mode:
        title_map = {
            "error":       "🔴 Fehler",
            "cover_open":  "⚠️ Deckel offen",
            "low_paper":   "⚠️ Papier fast leer",
            "stale":       "⚠️ Keine aktuellen Daten"
        }
        msg_map = {
            "error":       f"Status: {raw_status}",
            "cover_open":  "Der Druckerdeckel ist offen.",
            "low_paper":   f"Nur noch {media_remaining} Bilder!",
            "stale":       f"Seit {minutes_diff} Min kein Signal."
        }
        push = (title_map[status_mode], msg_map[status_mode], "warning")

    # Wenn vorher ERROR war und jetzt OK → nur dann Erfolgspush
    if prev_status == "error" and status_mode not in critical_states:
        push = ("✅ Störung behoben", "Drucker läuft wieder.", "white_check_mark")

    st.session_state.last_warn_status = status_mode
    return status_mode, display_text, display_color, push, minutes_diff


def maybe_play_sound(status_mode: str, sound_enabled: bool):
    """
    Spielt einen Warnton bei kritischen Zuständen,
    aber nur, wenn sich der Status geändert hat.
    """
    if not sound_enabled or not ALERT_SOUND_URL:
        return

    prev = st.session_state.last_sound_status

    # gleiche kritische Zustände wie bei den Pushes
    critical_states_with_sound = ["error", "cover_open", "low_paper"]

    if status_mode in critical_states_with_sound and prev != status_mode:
        st.session_state.last_sound_status = status_mode
        st.markdown(
            f"""
            <audio autoplay>
                <source src="{ALERT_SOUND_URL}" type="audio/ogg">
            </audio>
            """,
            unsafe_allow_html=True,
        )
    elif status_mode not in critical_states_with_sound and prev is not None:
        # zurücksetzen, wenn wieder alles ok ist
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
        
        # --- DATENABFRAGE NEU ---
        # Spalten: Timestamp, Status, MediaRemaining
        timestamp = str(last.get("Timestamp", ""))
        raw_status = str(last.get("Status", ""))
        
        # Sicherstellen, dass MediaRemaining eine Zahl ist
        # Die Datenbank liefert den Wert halbiert → hier verdoppeln
        try:
            mr_val = last.get("MediaRemaining", 0)
            media_remaining_raw = int(mr_val)
            media_remaining = media_remaining_raw * 2
        except:
            media_remaining_raw = 0
            media_remaining = 0

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
            <div style='color: #888; font-size: 12px; margin-bottom: 20px;'>
                 Statusmeldung: {raw_status}
            </div>
        </div>
        """
        st.markdown(header_html, unsafe_allow_html=True)

        if status_mode == "error":
            st.error("Bitte Drucker und Papier prüfen (Störung aktiv).")
        elif status_mode == "stale":
            st.warning("Seit einigen Minuten keine Daten – Verbindung / Script prüfen.")

        # Papierstatus
        st.markdown("### Papierstatus")

        if status_mode == "error":
            remaining_text = f"{media_remaining} Stk (?)"
            forecast = "Gestört"
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
        if status_mode == "error" and media_remaining == 0:
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

    # Spaltennamen angepasst (MediaRemaining)
    if "Timestamp" in df.columns and "MediaRemaining" in df.columns:
        df_plot = df.copy()
        df_plot["Timestamp"] = pd.to_datetime(df_plot["Timestamp"], errors="coerce")
        df_plot = df_plot.dropna(subset=["Timestamp"]).set_index("Timestamp")
        st.line_chart(df_plot["MediaRemaining"], use_container_width=True)

    last = df.iloc[-1]
    try:
        media_remaining = int(last.get("MediaRemaining", 0))
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

        # LINKS & BENACHRICHTIGUNGEN – CARD
        with col1:
            with st.container():
                st.markdown('<div class="admin-card">', unsafe_allow_html=True)
                st.markdown(
                    '<div class="admin-card-title">Externe Links</div>',
                    unsafe_allow_html=True,
                )

                st.link_button(
                    "🔗 Fotoshare Cloud",
                    "https://fotoshare.co/admin/index",
                    use_container_width=True,
                )

                st.markdown(
                    '<div class="admin-card-subtitle">Benachrichtigungen</div>',
                    unsafe_allow_html=True,
                )

                st.code(st.session_state.ntfy_topic or "(kein Topic konfiguriert)")

                st.write("")  # kleiner Spacer
                if st.button("Test Push 🔔", use_container_width=True):
                    send_ntfy_push("Test", "Test erfolgreich", tags="tada")
                    st.toast("Test gesendet!")

                st.markdown("</div>", unsafe_allow_html=True)

        # NEUER AUFTRAG / PAPIERWECHSEL – CARD
        with col2:
            if not st.session_state.confirm_reset:
                with st.container():
                    st.markdown('<div class="admin-card">', unsafe_allow_html=True)
                    st.markdown(
                        '<div class="admin-card-title">Neuer Auftrag / Papierwechsel</div>',
                        unsafe_allow_html=True,
                    )

                    st.markdown(
                        '<div class="admin-card-subtitle">Paketgröße</div>',
                        unsafe_allow_html=True,
                    )
                    size = st.radio(
                        "",
                        [200, 400],
                        horizontal=True,
                        index=1 if st.session_state.max_prints == 400 else 0,
                        label_visibility="collapsed",
                    )

                    st.markdown(
                        '<div class="admin-card-subtitle">Notiz zum Papierwechsel (optional)</div>',
                        unsafe_allow_html=True,
                    )
                    reset_note = st.text_input(
                        "",
                        key="reset_note",
                        label_visibility="collapsed",
                        placeholder="z.B. neue 400er Rolle eingelegt",
                    )

                    st.write("")  # Spacer nach unten
                    if st.button(
                        "Papierwechsel durchgeführt (Reset) 🔄",
                        use_container_width=True,
                    ):
                        st.session_state.confirm_reset = True
                        st.session_state.temp_package_size = size
                        st.session_state.temp_reset_note = reset_note
                        st.rerun()

                    st.markdown("</div>", unsafe_allow_html=True)
            else:
                # Bestätigungs-Ansicht
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

        # ============================================================
        # AQARA STECKDOSE – MODERNE CARD + BUTTONS
        # ============================================================
        st.write("### Aqara Steckdose Fotobox")

        if not AQARA_ENABLED:
            st.info(
                "Aqara ist nicht konfiguriert. Bitte [aqara] in secrets.toml setzen."
            )
        else:
            # Aktuellen Status holen
            current_state, debug_data = aqara_client.get_socket_state(
                AQARA_ACCESS_TOKEN,
                AQARA_SOCKET_DEVICE_ID,
                AQARA_SOCKET_RESOURCE_ID,
            )
            st.session_state.socket_debug = debug_data

            if current_state in ("on", "off"):
                st.session_state.socket_state = current_state
            else:
                if st.session_state.socket_state not in ("on", "off"):
                    st.session_state.socket_state = "unknown"

            state = st.session_state.socket_state

            # Farben & Texte je nach Status
            if state == "on":
                bg = "#ecfdf3"
                border = "#bbf7d0"
                icon = "🟢"
                title_text = "EINGESCHALTET"
                badge = "Zustand: on"
            elif state == "off":
                bg = "#f9fafb"
                border = "#e5e7eb"
                icon = "⚪️"
                title_text = "AUSGESCHALTET"
                badge = "Zustand: off"
            else:
                bg = "#fffbeb"
                border = "#fed7aa"
                icon = "⚠️"
                title_text = "STATUS UNBEKANNT"
                badge = "Zustand: unbekannt"

            # Karte
            card = st.container()
            with card:
                st.markdown(
                    f"""
                    <div style="
                        border-radius:18px;
                        border:1px solid {border};
                        padding:16px 18px;
                        background:{bg};
                        display:flex;
                        flex-direction:row;
                        justify-content:space-between;
                        gap:18px;
                    ">
                        <div style="flex:1;">
                            <div style="font-size:11px; text-transform:uppercase;
                                        letter-spacing:.16em; color:#9ca3af; margin-bottom:4px;">
                                Fotobox-Steckdose
                            </div>
                            <div style="font-size:18px; font-weight:600; color:#111827;
                                        display:flex; align-items:center; gap:8px; margin-bottom:4px;">
                                <span>{icon}</span>
                                <span>{title_text}</span>
                            </div>
                            <div style="
                                display:inline-flex;
                                align-items:center;
                                padding:3px 10px;
                                border-radius:999px;
                                background:rgba(0,0,0,0.04);
                                font-size:11px;
                                color:#4b5563;
                                margin-bottom:6px;
                            ">
                                {badge}
                            </div>
                            <div style="font-size:12px; color:#6b7280;">
                                Schaltet die Stromversorgung der Fotobox über die Aqara-Steckdose.
                            </div>
                        </div>
                        <div style="flex:0 0 180px; display:flex; flex-direction:column; gap:6px;">
                            <div style="font-size:11px; text-transform:uppercase;
                                        letter-spacing:.12em; color:#9ca3af; margin-bottom:2px;">
                                Steuerung
                            </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Buttons in zwei Spalten
                c_on, c_off = st.columns(2)
                with c_on:
                    click_on = st.button("Ein", key="aqara_btn_on", use_container_width=True)
                with c_off:
                    click_off = st.button("Aus", key="aqara_btn_off", use_container_width=True)

                st.markdown(
                    """
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Button-Logik
            desired_state = None
            if click_on:
                desired_state = True
            elif click_off:
                desired_state = False

            if desired_state is not None and desired_state != (state == "on"):
                res = aqara_client.switch_socket(
                    AQARA_ACCESS_TOKEN,
                    AQARA_SOCKET_DEVICE_ID,
                    turn_on=desired_state,
                    resource_id=AQARA_SOCKET_RESOURCE_ID,
                    mode="state",
                )
                if res.get("code") == 0:
                    st.session_state.socket_state = "on" if desired_state else "off"
                    st.success(
                        "Steckdose eingeschaltet."
                        if desired_state
                        else "Steckdose ausgeschaltet."
                    )
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Fehler beim Schalten der Steckdose:")
                    st.code(json.dumps(res, indent=2))

        st.markdown("---")

        # ============================================================
        # DSRBOOTH LOCKSCREEN – MODERNE CARD + BUTTONS
        # ============================================================
        st.write("### dsrBooth Lockscreen")

        if not DSR_ENABLED:
            st.info(
                "dsrBooth-Steuerung ist nicht konfiguriert. Bitte [dsrbooth] mit control_topic in secrets.toml setzen."
            )
        else:
            if "lockscreen_state" not in st.session_state:
                st.session_state.lockscreen_state = "off"

            state = st.session_state.lockscreen_state

            if state == "on":
                bg = "#eff6ff"
                border = "#bfdbfe"
                icon = "🔒"
                title_text = "LOCKSCREEN AKTIV"
                badge = "Zustand (letzte Aktion): on"
            elif state == "off":
                bg = "#f9fafb"
                border = "#e5e7eb"
                icon = "🔓"
                title_text = "LOCKSCREEN INAKTIV"
                badge = "Zustand (letzte Aktion): off"
            else:
                bg = "#fffbeb"
                border = "#fed7aa"
                icon = "⚠️"
                title_text = "STATUS UNBEKANNT"
                badge = "Zustand (letzte Aktion): unbekannt"

            card2 = st.container()
            with card2:
                st.markdown(
                    f"""
                    <div style="
                        border-radius:18px;
                        border:1px solid {border};
                        padding:16px 18px;
                        background:{bg};
                        display:flex;
                        flex-direction:row;
                        justify-content:space-between;
                        gap:18px;
                    ">
                        <div style="flex:1;">
                            <div style="font-size:11px; text-transform:uppercase;
                                        letter-spacing:.16em; color:#9ca3af; margin-bottom:4px;">
                                dsrBooth – Gästelockscreen
                            </div>
                            <div style="font-size:18px; font-weight:600; color:#111827;
                                        display:flex; align-items:center; gap:8px; margin-bottom:4px;">
                                <span>{icon}</span>
                                <span>{title_text}</span>
                            </div>
                            <div style="
                                display:inline-flex;
                                align-items:center;
                                padding:3px 10px;
                                border-radius:999px;
                                background:rgba(0,0,0,0.04);
                                font-size:11px;
                                color:#4b5563;
                                margin-bottom:6px;
                            ">
                                {badge}
                            </div>
                            <div style="font-size:12px; color:#6b7280; margin-bottom:4px;">
                                Der Status basiert nur auf der letzten Aktion, da die API keinen Status-Endpunkt bereitstellt.
                            </div>
                            <div style="font-size:11px; color:#9ca3af;">
                                Tipp: Bei Problemen ggf. dslrBooth-Client am Surface neu starten.
                            </div>
                        </div>
                        <div style="flex:0 0 180px; display:flex; flex-direction:column; gap:6px;">
                            <div style="font-size:11px; text-transform:uppercase;
                                        letter-spacing:.12em; color:#9ca3af; margin-bottom:2px;">
                                Steuerung
                            </div>
                    """,
                    unsafe_allow_html=True,
                )

                c_on, c_off = st.columns(2)
                with c_on:
                    click_on = st.button("Sperren", key="dsr_btn_on", use_container_width=True)
                with c_off:
                    click_off = st.button("Freigeben", key="dsr_btn_off", use_container_width=True)

                st.markdown(
                    """
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            desired_state = None
            if click_on:
                desired_state = True
            elif click_off:
                desired_state = False

            if desired_state is not None and desired_state != (state == "on"):
                cmd = "lock_on" if desired_state else "lock_off"
                send_dsr_command(cmd)
                st.session_state.lockscreen_state = "on" if desired_state else "off"
                st.success(
                    "Lockscreen-Befehl gesendet (aktivieren)."
                    if desired_state
                    else "Lockscreen-Befehl gesendet (deaktivieren)."
                )
