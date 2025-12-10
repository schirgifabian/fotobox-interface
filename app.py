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

# --- PIN ABFRAGE START --------------------------------------------------------


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
    st.title("Dashboard dieFotobox.")

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

# --- PIN ABFRAGE ENDE --------------------------------------------------------


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

        sign_str = "&".join(f"{k}={sign_params[k]}" for k in sorted(sign_params.keys()))
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

APP_ICON_URL = "https://www.fabianschirgi.com/uploads/tx_bh/710/icon-dashboard.png"

# Konfigurationen, die NICHT geheim sind, bleiben im Code
PRINTERS = {
    "Standard Fotobox": {
        "key": "standard",   # -> secrets.printers.standard
        "warning_threshold": 20,
        "default_max_prints": 400,
        "cost_per_roll_eur": 46.59,
        "has_admin": True,   # Admin-Bereich + Geräte-Steuerung
        "has_aqara": True,   # Aqara-Steckdose vorhanden
        "has_dsr": True,     # dsrBooth-Lockscreen vorhanden
        "media_factor": 1,   # Rohwert * 2 -> altes Papier # Rohwert * 1 -> neues Papier
    },
    "Weinkellerei": {
        "key": "Weinkellerei",       # -> secrets.printers.box2
        "warning_threshold": 20,
        "default_max_prints": 400,
        "cost_per_roll_eur": 60,
        "has_admin": True,  # Admin-Bereich
        "has_aqara": False,  # keine Aqara-Steckdose
        "has_dsr": False,    # kein dsrBooth
        "media_factor": 2,   # Rohwert * 2 -> altes Papier # Rohwert * 1 -> neues Papier
    },
}

HEARTBEAT_WARN_MINUTES = 60
NTFY_ACTIVE_DEFAULT = True
ALERT_SOUND_URL = "https://actions.google.com/sounds/v1/alarms/beep_short.ogg"

# --------------------------------------------------------------------
# LAYOUT & SESSION STATE
# --------------------------------------------------------------------
st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="centered")

CUSTOM_CSS = """
<style>
.settings-wrapper {
  margin-top: 0.75rem;
}

/* generische Karten-Optik (für Device-Cards) */
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

/* ----------------------------------------------------
   Admin-Karte
   ---------------------------------------------------- */
.admin-card {
  border-radius:18px;
  border:1px solid #e5e7eb;
  background:#ffffff;
  box-shadow:0 12px 30px rgba(15,23,42,0.05);
  padding:18px 20px 20px 20px;
  margin-bottom:20px;
}

.admin-card-header {
  display:flex;
  justify-content:space-between;
  align-items:baseline;
  margin-bottom:14px;
}

.admin-card-title {
  font-size:16px;
  font-weight:600;
  color:#111827;
}

.admin-card-subtitle {
  font-size:12px;
  color:#9ca3af;
}

.admin-section-title {
  font-size:15px;
  font-weight:600;
  color:#111827;
  margin-bottom:6px;
}

.admin-label-pill {
  font-size:11px;
  text-transform:uppercase;
  letter-spacing:.14em;
  color:#9ca3af;
  margin-top:10px;
  margin-bottom:4px;
}

.admin-spacer-xs {
  height:4px;
}

.admin-spacer-sm {
  height:8px;
}
</style>
"""

DARK_CSS = """
<style>
body, .main, .stApp {
    background-color: #020617 !important;
    color: #e5e7eb !important;
}
[data-testid="stSidebar"] {
    background-color: #020617 !important;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Session-State Defaults (nur Dinge, die wir nicht über Settings steuern)
if "confirm_reset" not in st.session_state:
    st.session_state.confirm_reset = False
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

# Sidebar – zuerst nur Drucker-Auswahl
st.sidebar.header("Einstellungen")
printer_name = st.sidebar.selectbox("Fotobox auswählen", list(PRINTERS.keys()))
printer_cfg = PRINTERS[printer_name]

# Konfigurierbarer Faktor für Rohwerte -> echte Drucke
MEDIA_FACTOR = printer_cfg.get("media_factor", 2)

# Capability-Flags je Fotobox
printer_has_admin = printer_cfg.get("has_admin", True)
printer_has_aqara = printer_cfg.get("has_aqara", False)
printer_has_dsr = printer_cfg.get("has_dsr", False)

# Zuordnung auf secrets.printers.<key>
printer_key = printer_cfg["key"]
printers_secrets = st.secrets.get("printers", {})
printer_secret = printers_secrets.get(printer_key, {})

sheet_id = printer_secret.get("sheet_id")
ntfy_topic = printer_secret.get("ntfy_topic")

if not sheet_id:
    st.error(
        f"Keine 'sheet_id' für '{printer_name}' in secrets.toml gefunden "
        f"(Sektion [printers.{printer_key}])."
    )
    st.stop()

# Sheet-bezogener State (wird von Settings-Helfern benutzt)
st.session_state.sheet_id = sheet_id
st.session_state.ntfy_topic = ntfy_topic

WARNING_THRESHOLD = printer_cfg.get("warning_threshold", 20)
COST_PER_ROLL_EUR = printer_cfg.get("cost_per_roll_eur")


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
    sheet_id_local = st.session_state.sheet_id
    return gc.open_by_key(sheet_id_local)


def get_main_worksheet():
    return get_spreadsheet().sheet1


# --- SETTINGS-HELPER -------------------------------------------------
def get_settings_ws(sheet_id: str):
    sh = get_gspread_client().open_by_key(sheet_id)
    try:
        return sh.worksheet("Settings")
    except WorksheetNotFound:
        ws = sh.add_worksheet(title="Settings", rows=100, cols=3)
        ws.append_row(["Key", "Value", "UpdatedAt"])
        return ws


@st.cache_data(ttl=60)
def load_settings(sheet_id: str):
    """
    Lädt alle Settings als Dict für das angegebene Sheet.
    """
    try:
        ws = get_settings_ws(sheet_id)
        rows = ws.get_all_records()
        return {row.get("Key"): row.get("Value") for row in rows if row.get("Key")}
    except Exception:
        return {}


def get_setting(key: str, default=None):
    sheet_id_local = st.session_state.get("sheet_id")
    if not sheet_id_local:
        return default
    data = load_settings(sheet_id_local)
    return data.get(key, default)


def set_setting(key: str, value):
    sheet_id_local = st.session_state.get("sheet_id")
    if not sheet_id_local:
        return
    ws = get_settings_ws(sheet_id_local)
    all_rows = ws.get_all_records()
    keys = [r.get("Key") for r in all_rows]

    now = datetime.datetime.now().isoformat(timespec="seconds")
    value_str = str(value)

    if key in keys:
        row_idx = keys.index(key) + 2  # +2 wegen Headerzeile + 1-basiert
        ws.update(f"A{row_idx}:C{row_idx}", [[key, value_str, now]])
    else:
        ws.append_row([key, value_str, now])

    # Cache invalidieren
    load_settings.clear()


@st.cache_data(ttl=300)  # 5 Minuten Cache für Admin / Historie
def get_data_admin(sheet_id: str):
    try:
        ws = get_gspread_client().open_by_key(sheet_id).sheet1
        return pd.DataFrame(ws.get_all_records())
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=30)  # 30 Sekunden Cache für Event-Ansicht
def get_data_event(sheet_id: str):
    try:
        ws = get_gspread_client().open_by_key(sheet_id).sheet1
        return pd.DataFrame(ws.get_all_records())
    except Exception:
        return pd.DataFrame()


def get_data(sheet_id: str, event_mode: bool):
    """
    Wrapper, der je nach Ansicht das passende Cache-Profil benutzt.
    """
    if event_mode:
        return get_data_event(sheet_id)
    else:
        return get_data_admin(sheet_id)


def clear_google_sheet():
    try:
        ws = get_main_worksheet()
        ws.batch_clear(["A2:Z10000"])
        get_data_admin.clear()
        get_data_event.clear()
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


@st.cache_data(ttl=60)
def get_last_reset_info(sheet_id: str):
    """
    Holt die letzte Zeile aus dem 'Meta'-Sheet (Papierwechsel-Log).
    Gibt ein Dict mit Timestamp, PackageSize, Note zurück oder None.
    """
    try:
        sh = get_gspread_client().open_by_key(sheet_id)
        try:
            ws = sh.worksheet("Meta")
        except WorksheetNotFound:
            return None

        rows = ws.get_all_records()
        if not rows:
            return None
        return rows[-1]
    except Exception:
        return None


# --------------------------------------------------------------------
# NACH DEM LADEN DER SHEETS: PRINTER-ABHÄNGIGE DEFAULTS AUS SETTINGS
# --------------------------------------------------------------------
# State aktualisieren, wenn anderer Drucker gewählt wurde
if st.session_state.selected_printer != printer_name:
    st.session_state.selected_printer = printer_name
    st.session_state.last_warn_status = None
    st.session_state.last_sound_status = None

    # Paketgröße aus Settings holen (oder Standard)
    try:
        pkg = get_setting("package_size", printer_cfg["default_max_prints"])
        st.session_state.max_prints = int(pkg)
    except Exception:
        st.session_state.max_prints = printer_cfg["default_max_prints"]

# ntfy_active (Push on/off) aus Settings holen
if "ntfy_active" not in st.session_state:
    try:
        default_ntfy = get_setting("ntfy_active", str(NTFY_ACTIVE_DEFAULT))
        st.session_state.ntfy_active = str(default_ntfy).lower() == "true"
    except Exception:
        st.session_state.ntfy_active = NTFY_ACTIVE_DEFAULT

# Event-Ansicht Default aus Settings
if "event_mode" not in st.session_state:
    try:
        default_view = get_setting("default_view", "admin")
        st.session_state.event_mode = default_view == "event"
    except Exception:
        st.session_state.event_mode = False

# Sound bleibt nur session-basiert (kein Persist)
if "sound_enabled" not in st.session_state:
    st.session_state.sound_enabled = False

# Sidebar – Toggles mit Settings-Defaults
event_mode = st.sidebar.toggle(
    "Event-Ansicht (nur Status)",
    value=st.session_state.event_mode,
)
sound_enabled = st.sidebar.toggle(
    "Sound bei Warnungen",
    value=st.session_state.sound_enabled,
)
ntfy_active_ui = st.sidebar.toggle(
    "Push-Benachrichtigungen aktiv",
    value=st.session_state.ntfy_active,
)

# Ruhezeiten (Night Mode)
if "quiet_enabled" not in st.session_state:
    try:
        q_en = get_setting("quiet_enabled", "false")
        st.session_state.quiet_enabled = str(q_en).lower() == "true"
    except Exception:
        st.session_state.quiet_enabled = False

if "quiet_start" not in st.session_state:
    try:
        q_start = get_setting("quiet_start", "22:00")
        st.session_state.quiet_start = datetime.time.fromisoformat(q_start)
    except Exception:
        st.session_state.quiet_start = datetime.time(22, 0)

if "quiet_end" not in st.session_state:
    try:
        q_end = get_setting("quiet_end", "07:00")
        st.session_state.quiet_end = datetime.time.fromisoformat(q_end)
    except Exception:
        st.session_state.quiet_end = datetime.time(7, 0)

st.sidebar.markdown("---")
st.sidebar.caption("🔕 Ruhezeiten (Push + Sound)")

quiet_enabled_ui = st.sidebar.toggle(
    "Ruhezeiten aktiv",
    value=st.session_state.quiet_enabled,
)

quiet_col1, quiet_col2 = st.sidebar.columns(2)
with quiet_col1:
    quiet_start_ui = st.time_input(
        "Start",
        value=st.session_state.quiet_start,
        step=300,
    )
with quiet_col2:
    quiet_end_ui = st.time_input(
        "Ende",
        value=st.session_state.quiet_end,
        step=300,
    )

# Dark Mode Toggle (rein CSS-basiert)
if "dark_mode" not in st.session_state:
    try:
        theme = get_setting("theme", "light")
        st.session_state.dark_mode = theme == "dark"
    except Exception:
        st.session_state.dark_mode = False

dark_mode_ui = st.sidebar.toggle(
    "🌙 Dark Mode",
    value=st.session_state.dark_mode,
)

# Änderungen in den Settings speichern
if event_mode != st.session_state.event_mode:
    st.session_state.event_mode = event_mode
    try:
        set_setting("default_view", "event" if event_mode else "admin")
    except Exception:
        pass

if ntfy_active_ui != st.session_state.ntfy_active:
    st.session_state.ntfy_active = ntfy_active_ui
    try:
        set_setting("ntfy_active", ntfy_active_ui)
    except Exception:
        pass

# Ruhezeiten speichern
if quiet_enabled_ui != st.session_state.quiet_enabled:
    st.session_state.quiet_enabled = quiet_enabled_ui
    try:
        set_setting("quiet_enabled", quiet_enabled_ui)
    except Exception:
        pass

if quiet_start_ui != st.session_state.quiet_start:
    st.session_state.quiet_start = quiet_start_ui
    try:
        set_setting("quiet_start", quiet_start_ui.isoformat(timespec="minutes"))
    except Exception:
        pass

if quiet_end_ui != st.session_state.quiet_end:
    st.session_state.quiet_end = quiet_end_ui
    try:
        set_setting("quiet_end", quiet_end_ui.isoformat(timespec="minutes"))
    except Exception:
        pass

# Dark Mode speichern
if dark_mode_ui != st.session_state.dark_mode:
    st.session_state.dark_mode = dark_mode_ui
    try:
        set_setting("theme", "dark" if dark_mode_ui else "light")
    except Exception:
        pass

# Sound nur in Session merken
st.session_state.sound_enabled = sound_enabled

# Dark-CSS aktivieren
if st.session_state.get("dark_mode", False):
    st.markdown(DARK_CSS, unsafe_allow_html=True)


def is_quiet_time() -> bool:
    """
    Prüft, ob wir uns innerhalb der konfigurierten Ruhezeiten befinden.
    Ruft Werte aus st.session_state (quiet_enabled, quiet_start, quiet_end) ab.
    """
    if not st.session_state.get("quiet_enabled", False):
        return False

    quiet_start = st.session_state.get("quiet_start")
    quiet_end = st.session_state.get("quiet_end")

    if not quiet_start or not quiet_end:
        return False

    LOCAL_TZ = pytz.timezone("Europe/Vienna")
    now = datetime.datetime.now(LOCAL_TZ).time()

    # Zeitraum innerhalb eines Tages oder über Mitternacht
    if quiet_start < quiet_end:
        return quiet_start <= now < quiet_end
    else:
        return now >= quiet_start or now < quiet_end


# --------------------------------------------------------------------
# PUSH FUNKTIONEN
# --------------------------------------------------------------------
def send_ntfy_push(title, message, tags="warning", priority="default"):
    if not st.session_state.ntfy_active:
        return

    # Ruhezeiten respektieren
    if is_quiet_time():
        return

    topic = st.session_state.get("ntfy_topic")
    if not topic:
        return
    try:
        headers = {
            "Title": title,
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
        "data error",
    ]

    cover_open_kw = ["cover open"]
    cooldown_kw = ["head cooling down"]
    printing_kw = ["printing", "processing", "drucken"]
    idle_kw = ["idle", "standby mode"]

    # 1) Harte Fehler
    if any(k in raw_status_l for k in hard_errors):
        status_mode = "error"
        display_text = f"🔴 STÖRUNG: {raw_status}"
        display_color = "red"

    # 2) Cover Open
    elif any(k in raw_status_l for k in cover_open_kw):
        status_mode = "cover_open"
        display_text = "⚠️ Deckel offen!"
        display_color = "orange"

    # 3) Druckkopf kühlt ab
    elif any(k in raw_status_l for k in cooldown_kw):
        status_mode = "cooldown"
        display_text = "⏳ Druckkopf kühlt ab…"
        display_color = "orange"

    # 4) Papier fast leer (nur wenn kein Fehler)
    elif media_remaining <= WARNING_THRESHOLD:
        status_mode = "low_paper"
        display_text = f"⚠️ Papier fast leer! ({media_remaining} Stk)"
        display_color = "orange"

    # 5) Druckt gerade
    elif any(k in raw_status_l for k in printing_kw):
        status_mode = "printing"
        display_text = "🖨️ Druckt gerade…"
        display_color = "blue"

    # 6) Leerlauf
    elif any(k in raw_status_l for k in idle_kw) or raw_status_l == "":
        status_mode = "ready"
        display_text = "✅ Bereit"
        display_color = "green"

    else:
        status_mode = "ready"
        display_text = f"✅ Bereit ({raw_status})"
        display_color = "green"

    # HEARTBEAT
    minutes_diff = None
    LOCAL_TZ = pytz.timezone("Europe/Vienna")
    ts_parsed = pd.to_datetime(timestamp, errors="coerce")

    if pd.notna(ts_parsed):
        if ts_parsed.tzinfo is None:
            ts_parsed = LOCAL_TZ.localize(ts_parsed)
        else:
            ts_parsed = ts_parsed.astimezone(LOCAL_TZ)

        now_local = datetime.datetime.now(LOCAL_TZ)
        delta = now_local - ts_parsed
        minutes_diff = int(delta.total_seconds() // 60)

        if minutes_diff >= HEARTBEAT_WARN_MINUTES and status_mode not in ["error"]:
            status_mode = "stale"
            display_text = "⚠️ Keine aktuellen Daten"
            display_color = "orange"

    # PUSH LOGIK
    critical_states = ["error", "cover_open", "low_paper", "stale"]
    push = None

    # Bisherige "Warn-Signatur" aus Session holen
    prev_sig = st.session_state.get("last_warn_signature")

    # Neue Signatur definieren
    current_sig = {
        "status_mode": status_mode,
        "raw_status": raw_status_l,
        "media_remaining": media_remaining,
        "minutes_diff": minutes_diff if minutes_diff is not None else -1,
    }

    if status_mode in critical_states:
        # Nur Push, wenn sich die Signatur geändert hat
        if prev_sig != current_sig:
            title_map = {
                "error": "🔴 Fehler",
                "cover_open": "⚠️ Deckel offen",
                "low_paper": "⚠️ Papier fast leer",
                "stale": "⚠️ Keine aktuellen Daten",
            }
            msg_map = {
                "error": f"Status: {raw_status}",
                "cover_open": "Der Druckerdeckel ist offen.",
                "low_paper": f"Nur noch {media_remaining} Bilder!",
                "stale": f"Seit {minutes_diff} Min kein Signal.",
            }
            tag_map = {
                "error": "rotating_light",
                "cover_open": "wrench",
                "low_paper": "warning",
                "stale": "hourglass",
            }
            push = (
                title_map[status_mode],
                msg_map[status_mode],
                tag_map.get(status_mode, "warning"),
            )

        # Signatur merken
        st.session_state.last_warn_signature = current_sig

    # Extra-Case: Störung behoben (Wechsel *weg* von error)
    elif prev_sig is not None and prev_sig.get("status_mode") == "error":
        push = ("✅ Störung behoben", "Drucker läuft wieder.", "white_check_mark")
        # Reset, damit nächster Fehler wieder eine Push auslöst
        st.session_state.last_warn_signature = None

    # Für evtl. andere Zwecke den "plain" Status noch merken
    st.session_state.last_warn_status = status_mode

    return status_mode, display_text, display_color, push, minutes_diff


def maybe_play_sound(status_mode: str, sound_enabled: bool):
    if not sound_enabled or not ALERT_SOUND_URL:
        return

    # Ruhezeiten -> kein Sound
    if is_quiet_time():
        return

    prev = st.session_state.last_sound_status
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
        st.session_state.last_sound_status = None


# --------------------------------------------------------------------
# HISTORIE & STATS
# --------------------------------------------------------------------
def _prepare_history_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Timestamp in Datetime umwandeln, nach Zeit sortieren und Zeilen ohne Timestamp / MediaRemaining rauswerfen.
    """
    if df.empty:
        return df

    if "Timestamp" not in df.columns or "MediaRemaining" not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    df = df.dropna(subset=["Timestamp", "MediaRemaining"])
    if df.empty:
        return df

    df = df.sort_values("Timestamp")
    df = df.set_index("Timestamp")
    df["MediaRemaining"] = pd.to_numeric(df["MediaRemaining"], errors="coerce")
    df = df.dropna(subset=["MediaRemaining"])
    return df


def compute_print_stats(
    df: pd.DataFrame,
    window_min: int = 30,
    media_factor: int = 2,
) -> dict:
    """
    Berechnet Kennzahlen aus dem Verlauf in "echten" Drucken.
    Der Rohwert vom Drucker wird mit media_factor multipliziert
    (z.B. 2 für altes Papier, 1 für neues Papier).
    """
    result = {
        "prints_total": 0,
        "duration_min": 0,
        "ppm_overall": None,
        "ppm_window": None,
    }

    df = _prepare_history_df(df)
    if df.empty or len(df) < 2:
        return result

    first_media_raw = df["MediaRemaining"].iloc[0]
    last_media_raw = df["MediaRemaining"].iloc[-1]

    # Differenz in Roh-Einheiten, dann * media_factor für echte Drucke
    prints_total = max(0, (first_media_raw - last_media_raw) * media_factor)
    duration_min = (df.index[-1] - df.index[0]).total_seconds() / 60.0

    result["prints_total"] = prints_total
    result["duration_min"] = duration_min

    if duration_min > 0 and prints_total > 0:
        result["ppm_overall"] = prints_total / duration_min

    # Fenster (z.B. letzte 30 Minuten)
    window_start = df.index[-1] - datetime.timedelta(minutes=window_min)
    dfw = df[df.index >= window_start]
    if len(dfw) >= 2:
        f_m_raw = dfw["MediaRemaining"].iloc[0]
        l_m_raw = dfw["MediaRemaining"].iloc[-1]
        prints_win = max(0, (f_m_raw - l_m_raw) * media_factor)
        dur_win_min = (dfw.index[-1] - dfw.index[0]).total_seconds() / 60.0
        if dur_win_min > 0 and prints_win > 0:
            result["ppm_window"] = prints_win / dur_win_min

    return result


def humanize_minutes(minutes: float) -> str:
    """
    Formatiert Minuten als schönen String.
    """
    if minutes is None or minutes <= 0:
        return "0 Min."
    m = int(minutes)
    h = m // 60
    r = m % 60
    if h > 0:
        return f"{h} Std. {r} Min."
    else:
        return f"{r} Min."


# --------------------------------------------------------------------
# GENERISCHE TOGGLE-KARTE FÜR GERÄTE
# --------------------------------------------------------------------
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
    """
    Zeichnet eine Status-Karte mit zwei Buttons (links/rechts).
    Gibt (clicked_left, clicked_right) zurück.
    state: "on" | "off" | "unknown"
    """
    if state == "on":
        bg = "#ecfdf3"
        border = "#bbf7d0"
        icon = icon_on
        title_text = title_on
        badge = f"{badge_prefix}: on"
    elif state == "off":
        bg = "#f9fafb"
        border = "#e5e7eb"
        icon = icon_off
        title_text = title_off
        badge = f"{badge_prefix}: off"
    else:
        bg = "#fffbeb"
        border = "#fed7aa"
        icon = icon_unknown
        title_text = title_unknown
        badge = f"{badge_prefix}: unbekannt"

    container = st.container()
    with container:
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
                        {section_title}
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
                        {description}
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

        c_left, c_right = st.columns(2)
        with c_left:
            click_left = st.button(
                btn_left_label, key=btn_left_key, use_container_width=True
            )
        with c_right:
            click_right = st.button(
                btn_right_label, key=btn_right_key, use_container_width=True
            )

        st.markdown(
            """
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return click_left, click_right


# --------------------------------------------------------------------
# SYSTEM-STATUS & HILFE
# --------------------------------------------------------------------
def render_health_overview():
    items = []

    # Google Sheets
    sheets_ok = False
    try:
        _ = get_spreadsheet()
        sheets_ok = True
    except Exception:
        sheets_ok = False
    items.append(("Google Sheets", sheets_ok, "Verbindung zur Log-Tabelle"))

    # ntfy
    ntfy_ok = bool(st.session_state.get("ntfy_topic")) and st.session_state.ntfy_active
    items.append(("ntfy Push", ntfy_ok, "Benachrichtigungen für Probleme"))

    # Aqara
    items.append(("Aqara", AQARA_ENABLED, "Steckdose der Fotobox"))

    # dsrBooth
    items.append(("dsrBooth", DSR_ENABLED, "Lockscreen-Steuerung"))

    st.markdown("#### Systemstatus")

    cols = st.columns(len(items))
    for col, (name, ok, desc) in zip(cols, items):
        emoji = "✅" if ok else "⚠️"
        col.markdown(
            f"""
            <div style="
                border-radius:12px;
                border:1px solid #e5e7eb;
                padding:8px 10px;
                background:#f9fafb;
                font-size:12px;
                margin-bottom:6px;
            ">
                <div style="font-weight:600; margin-bottom:2px;">
                    {emoji} {name}
                </div>
                <div style="color:#6b7280; font-size:11px;">
                    {desc}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_status_help():
    with st.expander("ℹ️ Hilfe zu Status & Geräten"):
        st.markdown(
            f"""
**Druckerstatus**

- `✅ Bereit`  
  Drucker ist verbunden und meldet keinen Fehler.

- `⚠️ Papier fast leer`  
  Weniger als **{WARNING_THRESHOLD}** verbleibende Drucke laut Zähler.

- `⚠️ Deckel offen`  
  Der Druckerdeckel ist nicht geschlossen – bitte Deckel prüfen und erneut testen.

- `⏳ Druckkopf kühlt ab…`  
  Der Drucker pausiert kurz, weil der Kopf zu heiß ist. In der Regel reicht es, kurz zu warten.

- `⚠️ Keine aktuellen Daten`  
  Seit mehr als **{HEARTBEAT_WARN_MINUTES}** Minuten ist kein neuer Eintrag vom Fotobox-Skript eingegangen.  
  → Prüfen: Fotobox-PC an? Script läuft? Internet/Google Sheets erreichbar?

- `🔴 STÖRUNG`  
  Harte Fehler wie „paper end“, „ribbon end“, „paper jam“, „data error“ usw.  
  → Papier/Rolle prüfen, Drucker-Display checken, ggf. Papier neu einlegen.

---

**Geräte-Steuerung**

- **Aqara Steckdose Fotobox**  
  Schaltet die Stromversorgung der Fotobox komplett ein/aus.  
  `Ein` = Fotobox bekommt Strom, `Aus` = Fotobox stromlos.

- **dsrBooth – Gästelockscreen**  
  `Sperren` aktiviert den Gästelockscreen (Gäste können keine Fotos starten).  
  `Freigeben` deaktiviert ihn.  
  Der angezeigte Status basiert nur auf der *letzten gesendeten Aktion*, nicht auf einem echten Status-Request.
            """
        )


def render_fleet_overview():
    """
    Zeigt einen groben Überblick über alle konfigurierten Fotoboxen.
    Nutzt nur die letzte Zeile aus der jeweiligen Tabelle.
    """
    st.subheader("Flottenübersicht (alle Fotoboxen)")

    printers_secrets = st.secrets.get("printers", {})
    cols = st.columns(max(1, min(3, len(PRINTERS))))

    idx = 0
    for name, cfg in PRINTERS.items():
        sheet_id_local = printers_secrets.get(cfg["key"], {}).get("sheet_id")
        if not sheet_id_local:
            continue

        try:
            df = get_data_event(sheet_id_local)
            if df.empty:
                last_ts = "–"
                raw_status = "keine Daten"
                media_raw = None
            else:
                last = df.iloc[-1]
                last_ts = str(last.get("Timestamp", ""))
                raw_status = str(last.get("Status", ""))
                try:
                    media_raw = int(last.get("MediaRemaining", 0)) * cfg.get(
                        "media_factor", 1
                    )
                except Exception:
                    media_raw = None
        except Exception:
            last_ts = "Fehler"
            raw_status = "–"
            media_raw = None

        with cols[idx]:
            st.markdown(
                f"""
                <div style="
                    border-radius:14px;
                    border:1px solid #e5e7eb;
                    padding:10px 12px;
                    background:#f9fafb;
                    font-size:12px;
                    margin-bottom:10px;
                ">
                    <div style="font-weight:600; margin-bottom:4px;">
                        {name}
                    </div>
                    <div style="color:#6b7280; margin-bottom:2px;">
                        Letztes Signal: {last_ts}
                    </div>
                    <div style="color:#6b7280; margin-bottom:2px;">
                        Status: {raw_status}
                    </div>
                    <div style="color:#6b7280;">
                        Verbleibende Drucke: {media_raw if media_raw is not None else '–'}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        idx = (idx + 1) % len(cols)


# --------------------------------------------------------------------
# UI START
# --------------------------------------------------------------------
st.title(f"{PAGE_ICON} {PAGE_TITLE}")
render_fleet_overview()
st.markdown("---")


@st.fragment(run_every=10)
def show_live_status(sound_enabled: bool = False, event_mode: bool = False):
    df = get_data(st.session_state.sheet_id, event_mode=event_mode)
    if df.empty:
        st.info("System wartet auf Start…")
        st.caption("Noch keine Druckdaten empfangen.")
        return

    # Event-Info aus Settings
    event_name = get_setting("event_name", "")
    event_note = get_setting("event_note", "")
    last_reset = get_last_reset_info(st.session_state.sheet_id)

    try:
        last = df.iloc[-1]
        timestamp = str(last.get("Timestamp", ""))
        raw_status = str(last.get("Status", ""))

        # Rohwert vom Drucker -> wird mit MEDIA_FACTOR in echte Drucke umgerechnet
        try:
            media_remaining_raw = int(last.get("MediaRemaining", 0))
        except Exception:
            media_remaining_raw = 0

        # Echte verbleibende Drucke (für Anzeige & Berechnung)
        media_remaining = media_remaining_raw * MEDIA_FACTOR

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

        reset_info_html = ""
        if last_reset:
            reset_ts = last_reset.get("Timestamp", "")
            reset_pkg = last_reset.get("PackageSize", "")
            reset_note = last_reset.get("Note", "")
            reset_info_html = (
                f"<div style='color:#9ca3af; font-size:12px; margin-top:2px;'>"
                f"Letzter Papierwechsel: {reset_ts} – {reset_pkg}er Rolle"
                f"{' – ' + reset_note if reset_note else ''}"
                f"</div>"
            )

        event_html = ""
        if event_name or event_note:
            event_html = "<div style='margin-bottom:6px;'>"
            if event_name:
                event_html += (
                    f"<div style='font-weight:600; font-size:15px;'>{event_name}</div>"
                )
            if event_note:
                event_html += (
                    f"<div style='font-size:12px; color:#6b7280;'>{event_note}</div>"
                )
            event_html += "</div>"

header_html = f"""
<div style='text-align: left; margin-top: 0;'>
  <h2 style='color:{display_color}; font-weight: 700; margin-bottom: 4px;'>
    {display_text}
  </h2>
  {event_html}
  <div style='color: #666; font-size: 14px; margin-bottom: 4px;'>
    Letztes Signal: {timestamp}{heartbeat_info}
  </div>
  <div style='color: #888; font-size: 12px; margin-bottom: 8px;'>
    Statusmeldung: {raw_status}
  </div>
  {reset_info_html}
</div>
"""
st.markdown(header_html, unsafe_allow_html=True)

        if status_mode == "error":
            st.error("Bitte Drucker und Papier prüfen (Störung aktiv).")
        elif status_mode == "stale":
            st.warning("Seit einigen Minuten keine Daten – Verbindung / Script prüfen.")

        if status_mode == "error":
            with st.expander("Details / letzte Statusmeldungen"):
                try:
                    df_tail = df.tail(15)[["Timestamp", "Status"]]
                    st.dataframe(df_tail, use_container_width=True)
                except Exception:
                    st.info("Keine Detaildaten verfügbar.")

        # Papierstatus
        st.markdown("### Papierstatus")

        # Drucke seit Reset: max_prints (echte Drucke) - media_remaining (echte Drucke)
        prints_since_reset = max(0, (st.session_state.max_prints or 0) - media_remaining)

        # Restlaufzeit aus Historie (alles in echten Drucken dank compute_print_stats)
        stats = compute_print_stats(df, window_min=30, media_factor=MEDIA_FACTOR)
        forecast = "–"

        if status_mode == "error":
            forecast = "Gestört"
        else:
            ppm = stats.get("ppm_window") or stats.get("ppm_overall")
            if ppm and ppm > 0 and media_remaining > 0:
                minutes_left = media_remaining / ppm
                forecast = humanize_minutes(minutes_left)
            elif media_remaining > 0:
                # Fallback: 1 Druck/Min
                minutes_left = media_remaining * 1.0
                forecast = humanize_minutes(minutes_left)
            else:
                forecast = "0 Min."

        colA, colB, colC = st.columns(3)
        colA.metric("Verbleibend", f"{media_remaining} Stk", f"von {st.session_state.max_prints}")
        colB.metric("Restlaufzeit (geschätzt)", forecast)

        if COST_PER_ROLL_EUR and (st.session_state.max_prints or 0) > 0:
            try:
                cost_per_print = COST_PER_ROLL_EUR / st.session_state.max_prints
                cost_used = prints_since_reset * cost_per_print
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
            if not st.session_state.max_prints:
                progress_val = 0
            else:
                progress_val = max(
                    0.0, min(1.0, media_remaining / st.session_state.max_prints)
                )

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
    df = get_data_admin(st.session_state.sheet_id)
    if df.empty:
        st.info("Noch keine Daten für die Historie.")
        return

    st.subheader("Verlauf & Analyse")

    df_hist = _prepare_history_df(df)
    if df_hist.empty:
        st.info("Keine auswertbaren Daten (Timestamp / MediaRemaining fehlen).")
        return

    df_hist = df_hist.copy()
    # Echte verbleibende Drucke
    df_hist["RemainingPrints"] = df_hist["MediaRemaining"] * MEDIA_FACTOR

    # Event-Statistiken
    stats = compute_print_stats(df, window_min=30, media_factor=MEDIA_FACTOR)
    prints_total = stats.get("prints_total", 0)
    duration_min = stats.get("duration_min", 0)
    ppm_overall = stats.get("ppm_overall")
    ppm_window = stats.get("ppm_window")

    st.markdown("#### Event-Übersicht")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Gesamtdrucke (Event)", int(prints_total))
    c2.metric("Dauer", humanize_minutes(duration_min))

    if ppm_overall:
        c3.metric("Ø Drucke/Std (Event)", f"{ppm_overall * 60:.1f}")
    else:
        c3.metric("Ø Drucke/Std (Event)", "–")

    if ppm_window:
        c4.metric("Ø Drucke/Std (letzte 30 Min)", f"{ppm_window * 60:.1f}")
    else:
        c4.metric("Ø Drucke/Std (letzte 30 Min)", "–")

    st.markdown("#### Medienverlauf (echte Drucke)")
    st.line_chart(df_hist["RemainingPrints"], use_container_width=True)

    # Drucke pro Stunde
    st.markdown("#### Drucke pro Stunde")
    df_hist["Prints"] = -df_hist["MediaRemaining"].diff().fillna(0) * MEDIA_FACTOR
    hourly = df_hist["Prints"].resample("1H").sum()
    hourly = hourly[hourly > 0]
    if not hourly.empty:
        st.bar_chart(hourly, use_container_width=True)
    else:
        st.caption("Noch zu wenig Daten für eine Stunden-Auswertung.")

    # Kosten
    last_remaining = int(df_hist["RemainingPrints"].iloc[-1])
    prints_since_reset = max(0, (st.session_state.max_prints or 0) - last_remaining)

    st.markdown("#### Kostenabschätzung")
    col_cost1, col_cost2 = st.columns(2)
    if COST_PER_ROLL_EUR and (st.session_state.max_prints or 0) > 0:
        try:
            cost_per_print = COST_PER_ROLL_EUR / st.session_state.max_prints
            cost_used = prints_since_reset * cost_per_print
            col_cost1.metric("Kosten seit Reset", f"{cost_used:0.2f} €")
            col_cost2.metric("Kosten pro Druck (ca.)", f"{cost_per_print:0.3f} €")
        except Exception:
            col_cost1.metric("Kosten seit Reset", "–")
            col_cost2.metric("Kosten pro Druck (ca.)", "–")
    else:
        col_cost1.metric("Kosten seit Reset", "–")
        col_cost2.metric("Kosten pro Druck (ca.)", "–")

    st.markdown("#### Rohdaten (letzte 200 Zeilen)")
    st.dataframe(df.tail(200), use_container_width=True)


def show_meta_history():
    """
    Zeigt das Meta-Log (Papierwechsel) an, falls vorhanden.
    """
    try:
        sh = get_spreadsheet()
        try:
            ws = sh.worksheet("Meta")
        except WorksheetNotFound:
            st.info("Noch keine Meta-Daten (Papierwechsel) vorhanden.")
            return

        rows = ws.get_all_records()
        if not rows:
            st.info("Noch keine Meta-Daten (Papierwechsel) vorhanden.")
            return

        st.subheader("Papierwechsel-Historie")
        df_meta = pd.DataFrame(rows)
        st.dataframe(df_meta.tail(50), use_container_width=True)
    except Exception as e:
        st.warning(f"Meta-Log konnte nicht geladen werden: {e}")


# --------------------------------------------------------------------
# RENDER MAIN VIEW
# --------------------------------------------------------------------
# Für Boxen ohne Admin erzwingen wir Event-Ansicht
view_event_mode = event_mode or not printer_has_admin

if view_event_mode:
    show_live_status(sound_enabled, event_mode=True)
    render_status_help()
else:
    tab_live, tab_hist = st.tabs(["Live-Status", "Historie & Analyse"])
    with tab_live:
        show_live_status(sound_enabled, event_mode=False)
        render_status_help()
    with tab_hist:
        show_history()
        st.markdown("---")
        show_meta_history()

st.markdown("---")

# --------------------------------------------------------------------
# ADMIN
# --------------------------------------------------------------------
if (not view_event_mode) and printer_has_admin:
    with st.expander("🛠️ Admin & Einstellungen"):

        # ============================================================
        # ADMIN-KARTE: Schnellzugriff & Papierwechsel
        # ============================================================
        admin_card = st.container()
        with admin_card:
            st.markdown(
                """
                <div class="admin-card">
                    <div class="admin-card-header">
                        <div class="admin-card-title">
                            Schnellzugriff & Papierwechsel
                        </div>
                        <div class="admin-card-subtitle">
                            Links, Benachrichtigungen und Rollenwechsel
                        </div>
                    </div>
                """,
                unsafe_allow_html=True,
            )

            col1, col2 = st.columns(2)

            # LINKS / NTFY / Event Angaben
            with col1:
                st.markdown(
                    '<div class="admin-section-title">Externe Links</div>',
                    unsafe_allow_html=True,
                )
                st.link_button(
                    "🔗 Fotoshare Cloud",
                    "https://fotoshare.co/admin/index",
                    use_container_width=True,
                )

                st.markdown(
                    '<div class="admin-label-pill">Benachrichtigungen</div>',
                    unsafe_allow_html=True,
                )
                st.text_input(
                    "",
                    value=st.session_state.ntfy_topic
                    or "(kein Topic konfiguriert)",
                    key="ntfy_topic_display",
                    disabled=True,
                    label_visibility="collapsed",
                )

                st.markdown(
                    '<div class="admin-spacer-sm"></div>',
                    unsafe_allow_html=True,
                )

                if st.button("Test Push 🔔", use_container_width=True):
                    send_ntfy_push("Test", "Test erfolgreich", tags="tada")
                    st.toast("Test gesendet!")

                st.markdown(
                    '<div class="admin-label-pill">Status-Simulation</div>',
                    unsafe_allow_html=True,
                )
                sim_option = st.selectbox(
                    "",
                    ["Keine", "Fehler", "Papier fast leer", "Keine Daten"],
                    label_visibility="collapsed",
                    key="status_sim_option",
                )
                if st.button("Simulation auslösen", use_container_width=True):
                    if sim_option == "Fehler":
                        send_ntfy_push(
                            "🔴 Fehler (Test)",
                            "Simulierter Fehlerzustand",
                            tags="rotating_light",
                        )
                        maybe_play_sound("error", st.session_state.sound_enabled)
                    elif sim_option == "Papier fast leer":
                        send_ntfy_push(
                            "⚠️ Papier fast leer (Test)",
                            "Simulierter Low-Paper-Status",
                            tags="warning",
                        )
                        maybe_play_sound("low_paper", st.session_state.sound_enabled)
                    elif sim_option == "Keine Daten":
                        send_ntfy_push(
                            "⚠️ Keine aktuellen Daten (Test)",
                            "Simulierter Stale-Status",
                            tags="hourglass",
                        )
                        # kein Sound für stale
                    st.toast("Simulation gesendet")

                st.markdown(
                    '<div class="admin-label-pill">Event-Infos</div>',
                    unsafe_allow_html=True,
                )
                event_name_current = get_setting("event_name", "")
                event_note_current = get_setting("event_note", "")

                event_name_input = st.text_input(
                    "Event-Name",
                    value=event_name_current,
                    key="event_name_input",
                )
                event_note_input = st.text_input(
                    "Notiz",
                    value=event_note_current,
                    key="event_note_input",
                )

                if st.button("Event-Infos speichern", use_container_width=True):
                    try:
                        set_setting("event_name", event_name_input)
                        set_setting("event_note", event_note_input)
                        st.toast("Event-Infos gespeichert", icon="✅")
                    except Exception as e:
                        st.error(f"Event-Infos konnten nicht gespeichert werden: {e}")

            # PAPIER / RESET
            with col2:
                st.markdown(
                    '<div class="admin-section-title">Neuer Auftrag / Papierwechsel</div>',
                    unsafe_allow_html=True,
                )

                st.markdown(
                    '<div class="admin-label-pill">Paketgröße</div>',
                    unsafe_allow_html=True,
                )
                size_options = [200, 400]
                try:
                    current_size = int(
                        st.session_state.max_prints
                        or printer_cfg["default_max_prints"]
                    )
                except Exception:
                    current_size = printer_cfg["default_max_prints"]
                idx = 0 if current_size == 200 else 1
                size = st.radio(
                    "",
                    size_options,
                    horizontal=True,
                    index=idx,
                    label_visibility="collapsed",
                )

                st.markdown(
                    '<div class="admin-label-pill">Notiz zum Papierwechsel (optional)</div>',
                    unsafe_allow_html=True,
                )
                reset_note = st.text_input(
                    "",
                    key="reset_note",
                    label_visibility="collapsed",
                    placeholder="z.B. neue 400er Rolle eingelegt",
                )

                st.markdown(
                    '<div class="admin-spacer-sm"></div>',
                    unsafe_allow_html=True,
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
                    st.info("Bestätigung unten abschließen …")

            st.markdown("</div>", unsafe_allow_html=True)

        # ============================================================
        # RESET-BESTÄTIGUNGSBLOCK
        # ============================================================
        if st.session_state.confirm_reset:
            st.warning(
                f"Log löschen & auf {st.session_state.temp_package_size}er Rolle setzen?",
            )
            y, n = st.columns(2)
            if y.button("Ja", use_container_width=True):
                st.session_state.max_prints = st.session_state.temp_package_size
                # Paketgröße in Settings persistieren
                try:
                    set_setting("package_size", st.session_state.max_prints)
                except Exception:
                    pass
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
        # AQARA STECKDOSE – CARD + BUTTONS
        # ============================================================
        st.write("### Aqara Steckdose Fotobox")

        if not printer_has_aqara:
            st.info("Für diese Fotobox ist keine Aqara-Steckdose hinterlegt.")
        elif not AQARA_ENABLED:
            st.info(
                "Aqara ist nicht konfiguriert. Bitte [aqara] in secrets.toml setzen."
            )
        else:
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

            click_on, click_off = render_toggle_card(
                section_title="Fotobox-Steckdose",
                description="Schaltet die Stromversorgung der Fotobox über die Aqara-Steckdose.",
                state=state,
                title_on="EINGESCHALTET",
                title_off="AUSGESCHALTET",
                title_unknown="STATUS UNBEKANNT",
                badge_prefix="Zustand",
                icon_on="🟢",
                icon_off="⚪️",
                icon_unknown="⚠️",
                btn_left_label="Ein",
                btn_right_label="Aus",
                btn_left_key="aqara_btn_on",
                btn_right_key="aqara_btn_off",
            )

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
        # DSRBOOTH LOCKSCREEN – CARD + BUTTONS
        # ============================================================
        st.write("### dsrBooth Lockscreen")

        if not printer_has_dsr:
            st.info("Für diese Fotobox ist kein dsrBooth-Lockscreen hinterlegt.")
        elif not DSR_ENABLED:
            st.info(
                "dsrBooth-Steuerung ist nicht konfiguriert. Bitte [dsrbooth] mit control_topic in secrets.toml setzen."
            )
        else:
            if "lockscreen_state" not in st.session_state:
                st.session_state.lockscreen_state = "off"

            state = st.session_state.lockscreen_state

            click_on, click_off = render_toggle_card(
                section_title="dsrBooth – Gästelockscreen",
                description=(
                    "Sperrt oder gibt den Gästemodus in dsrBooth frei. "
                    "Der Status basiert nur auf der letzten Aktion, da die API keinen "
                    "Status-Endpunkt bereitstellt."
                ),
                state=state,
                title_on="LOCKSCREEN AKTIV",
                title_off="LOCKSCREEN INAKTIV",
                title_unknown="STATUS UNBEKANNT",
                badge_prefix="Zustand (letzte Aktion)",
                icon_on="🔒",
                icon_off="🔓",
                icon_unknown="⚠️",
                btn_left_label="Sperren",
                btn_right_label="Freigeben",
                btn_left_key="dsr_btn_on",
                btn_right_key="dsr_btn_off",
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

        st.markdown("---")

        # ============================================================
        # SYSTEMSTATUS GANZ UNTEN IM ADMINBEREICH
        # ============================================================
        render_health_overview()
