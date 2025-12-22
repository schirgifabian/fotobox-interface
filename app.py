# app.py

import time
import json
import datetime
import re
import unicodedata
from typing import Optional, Tuple, Any, Dict, List

import requests
import streamlit as st
import extra_streamlit_components as stx
import pandas as pd
from streamlit_lottie import st_lottie

# --- NEUE & BESTEHENDE IMPORTE ---
from aqara_client import AqaraClient
from report_generator import generate_event_pdf
from sheets_helpers import (
    get_data,
    get_data_admin,
    get_setting,
    set_setting,
    clear_google_sheet,
    log_reset_event,
)
from status_logic import (
    evaluate_status,
    maybe_play_sound,
    compute_print_stats,
    humanize_minutes,
    _prepare_history_df,
)
from ui_components import (
    inject_custom_css,
    render_toggle_card,
    render_fleet_overview,
    render_hero_status,
    render_custom_progress_bar
)

# --------------------------------------------------------------------
# LOTTIE ANIMATION LOADER
# --------------------------------------------------------------------
@st.cache_data
def load_lottieurl(url: str):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

# Lottie URLs (Open Source Animationen)
LOTTIE_PRINTING = "https://lottie.host/5a8e0f06-5a7a-4286-905c-37e466479f6e/8wG9QnF6wK.json" # Drucker Animation
LOTTIE_READY = "https://lottie.host/9e4d5818-4940-4235-9854-3e6188e7343e/8X1q1X1q1X.json" # Clean Checkmark (Generic Placeholder URL - using a safe fallback logic ideally)
LOTTIE_WARNING = "https://assets10.lottiefiles.com/packages/lf20_s9m78f.json" # Warning Triangle
LOTTIE_ERROR = "https://assets9.lottiefiles.com/packages/lf20_qpwbv89w.json" # Error Cross

# Fallback auf statische URLs, da Lottie-URLs sich ändern können. 
# Für Produktion empfiehlt es sich, die JSONs herunterzuladen und lokal zu laden.
# Hier verwende ich Dummys, die funktionieren sollten.

# --------------------------------------------------------------------
# GRUNDKONFIG
# --------------------------------------------------------------------
PAGE_TITLE = "Fotobox Drucker Status"
PAGE_ICON = "🖨️"
NTFY_ACTIVE_DEFAULT = True

PRINTERS = {
    "die Fotobox": {
        "key": "standard",
        "warning_threshold": 40,
        "default_max_prints": 400,
        "cost_per_roll_eur": 46.59,
        "has_admin": True,
        "has_aqara": True,
        "has_dsr": True,
        "media_factor": 1,
    },
    "Weinkellerei": {
        "key": "Weinkellerei",
        "warning_threshold": 20,
        "default_max_prints": 400,
        "cost_per_roll_eur": 55,
        "has_admin": True,
        "has_aqara": False,
        "has_dsr": False,
        "media_factor": 2,
    },
}
# --------------------------------------------------------------------
# LOGIN
# --------------------------------------------------------------------
def get_cookie_manager():
    return stx.CookieManager(key="fotobox_auth")


def check_login():
    try:
        secret_pin = str(st.secrets["general"]["app_pin"])
    except FileNotFoundError:
        st.error("Secrets nicht gefunden. Bitte .streamlit/secrets.toml prüfen.")
        st.stop()
        return

    cookie_manager = get_cookie_manager()
    cookie_val = cookie_manager.get("auth_pin")

    # Session schon freigeschaltet
    if st.session_state.get("is_logged_in", False):
        return True

    # Korrektes Cookie vorhanden
    if cookie_val is not None and str(cookie_val) == secret_pin:
        st.session_state["is_logged_in"] = True
        return True

    # Login-Form anzeigen
    st.title("Dashboard dieFotobox.")
    msg_placeholder = st.empty()

    with st.form("login_form"):
        user_input = st.text_input("Bitte PIN eingeben:", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            if str(user_input) == secret_pin:
                st.session_state["is_logged_in"] = True
                expires = datetime.datetime.now() + datetime.timedelta(days=30)
                cookie_manager.set("auth_pin", user_input, expires_at=expires)
                msg_placeholder.success("Login korrekt! Lade neu...")
                time.sleep(0.5)
                st.rerun()
            else:
                msg_placeholder.error("Falscher PIN!")

    st.stop()


def render_logout_button():
    if st.sidebar.button("Logout"):
        get_cookie_manager().delete("auth_pin")
        st.session_state["is_logged_in"] = False
        st.rerun()


# --------------------------------------------------------------------
# NTFY & DSR – BENACHRICHTIGUNGEN / STEUERUNG
# --------------------------------------------------------------------
try:
    dsr_cfg = st.secrets["dsrbooth"]
    DSR_CONTROL_TOPIC = dsr_cfg.get("control_topic")
    DSR_ENABLED = bool(DSR_CONTROL_TOPIC)
except Exception:
    DSR_CONTROL_TOPIC = None
    DSR_ENABLED = False


def _sanitize_header_value(val: str, default: str = "ntfy") -> str:
    if not isinstance(val, str): val = str(val)
    val = val.replace("\r", " ").replace("\n", " ")
    val = unicodedata.normalize("NFKC", val)
    val = re.sub(r"[\U00010000-\U0010FFFF]", "", val)
    val = val.encode("latin-1", "ignore").decode("latin-1")
    val = val.strip()
    return val if val else default

def send_ntfy_push(title: str, message: str, tags: str = "warning", priority: str = "default") -> None:
    if not st.session_state.get("ntfy_active", False): return
    topic = st.session_state.get("ntfy_topic")
    if not topic: return
    
    try:
        requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode("utf-8"),
            headers={"Title": _sanitize_header_value(title), "Tags": _sanitize_header_value(tags), "Priority": priority},
            timeout=5
        )
    except: pass

def send_dsr_command(cmd: str) -> None:
    try:
        dsr_cfg = st.secrets["dsrbooth"]
        DSR_CONTROL_TOPIC = dsr_cfg.get("control_topic")
        if DSR_CONTROL_TOPIC:
            requests.post(f"https://ntfy.sh/{DSR_CONTROL_TOPIC}", data=cmd.encode("utf-8"), timeout=5)
    except: pass

def init_aqara() -> Tuple[bool, Optional[AqaraClient], Optional[str], str]:
    try:
        if "aqara" not in st.secrets: return False, None, None, "4.1.85"
        client = AqaraClient()
        aqara_cfg = st.secrets["aqara"]
        return True, client, aqara_cfg["device_id"], aqara_cfg.get("resource_id", "4.1.85")
    except: return False, None, None, "4.1.85"

AQARA_ENABLED, aqara_client, AQARA_SOCKET_DEVICE_ID, AQARA_SOCKET_RESOURCE_ID = init_aqara()
try:
    dsr_cfg = st.secrets["dsrbooth"]
    DSR_CONTROL_TOPIC = dsr_cfg.get("control_topic")
    DSR_ENABLED = bool(DSR_CONTROL_TOPIC)
except:
    DSR_ENABLED = False

def init_session_state():
    defaults = {"confirm_reset": False, "last_warn_status": None, "last_sound_status": None, "max_prints": None, "selected_printer": None, "socket_state": "unknown", "socket_debug": None, "lockscreen_state": "off"}
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

# --------------------------------------------------------------------
# AQARA – KONFIG (Optimiert 3.B)
# --------------------------------------------------------------------
# app.py - Ersetze die bestehende init_aqara Funktion hiermit:

def init_aqara() -> Tuple[bool, Optional[AqaraClient], Optional[str], str]:
    try:
        if "aqara" not in st.secrets:
            return False, None, None, "4.1.85"
            
        # Debugging: Wir probieren den Login manuell und zeigen das Ergebnis
        client = AqaraClient()
        
        # Test: Haben wir einen Token bekommen?
        if not client.tokens.get("access_token"):
            st.error("❌ Aqara Login fehlgeschlagen! Keine tokens.json erstellt.")
            
            # Wir machen manuell einen Request, um den Fehler zu sehen
            url = f"{client.root_url}/auth/token"
            headers = client._generate_headers(access_token=None)
            payload = {"intent": 0}
            data = client._request_with_retry(url, headers, payload)
            
            st.code(f"Antwort vom Aqara Server:\n{json.dumps(data, indent=2)}", language="json")
            
            if data.get("code") == 302:
                 st.warning("⚠️ Fehler 302: Signatur falsch. Bitte App ID & Key ID prüfen.")
            elif data.get("code") == 301:
                 st.warning("⚠️ Fehler 301: Falsche Region. Ist dein Aqara-Konto auf Europa eingestellt?")
                 
        aqara_cfg = st.secrets["aqara"]
        return True, client, aqara_cfg["device_id"], aqara_cfg.get("resource_id", "4.1.85")
        
    except Exception as e:
        st.error(f"Aqara Init Fehler: {e}")
        return False, None, None, "4.1.85"

AQARA_ENABLED, aqara_client, AQARA_SOCKET_DEVICE_ID, AQARA_SOCKET_RESOURCE_ID = init_aqara()


# --------------------------------------------------------------------
# SESSION INITIALISIERUNG
# --------------------------------------------------------------------
def init_session_state():
    defaults = {
        "confirm_reset": False,
        "last_warn_status": None,
        "last_sound_status": None,
        "max_prints": None,
        "selected_printer": None,
        "socket_state": "unknown",
        "socket_debug": None,
        "lockscreen_state": "off",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# --------------------------------------------------------------------
# LIVE-STATUS VIEW (MIT WOW-EFFEKT)
# --------------------------------------------------------------------
@st.fragment(run_every=10)
def show_live_status(media_factor: int, cost_per_roll: float, sound_enabled: bool, event_mode: bool) -> None:
    df = get_data(st.session_state.sheet_id, event_mode=event_mode)
    if df.empty:
        st.info("Warte auf Daten...")
        return

    try:
        last = df.iloc[-1]
        timestamp = str(last.get("Timestamp", ""))
        raw_status = str(last.get("Status", ""))
        try: media_remaining_raw = int(last.get("MediaRemaining", 0))
        except: media_remaining_raw = 0
        media_remaining = media_remaining_raw * media_factor

        status_mode, display_text, display_color, push, minutes_diff = evaluate_status(
            raw_status, media_remaining, timestamp
        )

        if push:
            send_ntfy_push(*push)
        maybe_play_sound(status_mode, sound_enabled)
        
        heartbeat_info = f" (vor {minutes_diff} Min)" if minutes_diff is not None else ""

        # --- HERO STATUS (Mit Animation) ---
        # Wir teilen das Layout oben: Links Animation, Rechts Text
        
        # Lottie laden (basierend auf Status)
        lottie_json = None
        if status_mode == "printing":
             # Wir nutzen hier stattdessen eine lokale Referenz oder URL laden
             # Da wir keine lokalen Files haben, laden wir URL (Achtung: Performance)
             # Für Production: Lade JSON einmal global.
             lottie_json = load_lottieurl("https://lottie.host/5a8e0f06-5a7a-4286-905c-37e466479f6e/8wG9QnF6wK.json")
        elif status_mode == "error":
             lottie_json = load_lottieurl("https://assets9.lottiefiles.com/packages/lf20_qpwbv89w.json")
        
        # Zeige die überarbeitete Hero Card
        render_hero_status(status_mode, display_text, timestamp, heartbeat_info)
        
        # Wenn wir drucken oder Fehler haben, zeigen wir die Animation UNTERHALB der Card groß an
        if lottie_json:
            st_lottie(lottie_json, height=150, key="status_anim")

        if status_mode == "error":
            st.error("Störung aktiv! Bitte Drucker prüfen.")
        elif status_mode == "stale":
            st.warning("Verbindung prüfen (Keine Daten seit > 60 Min).")

        # --- PAPIER STATUS & FORECAST ---
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### 🧻 Papierstand & Analyse")

        prints_since_reset = max(0, (st.session_state.max_prints or 0) - media_remaining)
        stats = compute_print_stats(df, window_min=30, media_factor=media_factor)
        
        forecast_str = "–"
        end_time_str = ""
        ppm = stats.get("ppm_window") or stats.get("ppm_overall")
        
        if status_mode != "error" and ppm and ppm > 0 and media_remaining > 0:
            minutes_left = media_remaining / ppm
            now = datetime.datetime.now()
            end_time = now + datetime.timedelta(minutes=minutes_left)
            forecast_str = humanize_minutes(minutes_left)
            end_time_str = f" (bis {end_time.strftime('%H:%M')})"
        elif media_remaining > 0:
            forecast_str = "Warte..."
        else:
            forecast_str = "Leer"

        # Metrics Row
        colA, colB, colC = st.columns(3)
        colA.metric("Verbleibend", f"{media_remaining}", f"von {st.session_state.max_prints}")
        colB.metric("Laufzeit", forecast_str, end_time_str.replace("(", "").replace(")", ""))
        
        cost_txt = "–"
        if cost_per_roll and st.session_state.max_prints:
            cost_used = prints_since_reset * (cost_per_roll / st.session_state.max_prints)
            cost_txt = f"{cost_used:.2f} €"
        colC.metric("Kosten (Live)", cost_txt)

        # --- ANIMATED PROGRESS BAR ---
        # Berechnung
        progress_val = 0.0
        if st.session_state.max_prints and media_remaining > 0:
             progress_val = media_remaining / st.session_state.max_prints
        
        # Farben definieren
        if status_mode == "error" and media_remaining == 0:
            c_start, c_end = "#EF4444", "#B91C1C" # Rot
        elif progress_val < 0.15:
            c_start, c_end = "#F59E0B", "#D97706" # Orange
        else:
            c_start, c_end = "#3B82F6", "#2563EB" # Blau
            
        render_custom_progress_bar(progress_val, c_start, c_end)
        
        st.caption(f"Füllstand: {int(progress_val*100)}%")

    except Exception as e:
        st.error(f"Render Fehler: {e}")


# --------------------------------------------------------------------
# HISTORIE VIEW
# --------------------------------------------------------------------
def show_history(media_factor: int, cost_per_roll: float) -> None:
    df = get_data_admin(st.session_state.sheet_id)
    if df.empty:
        st.info("Noch keine Daten für die Historie.")
        return

    # Das CSS aus ui_components sorgt automatisch für schöneres Styling hier
    st.markdown("### 📈 Verlauf & Analyse")

    df_hist = _prepare_history_df(df)
    if df_hist.empty:
        st.info("Keine auswertbaren Daten (Timestamp / MediaRemaining fehlen).")
        return

    df_hist = df_hist.copy()
    df_hist["RemainingPrints"] = df_hist["MediaRemaining"] * media_factor

    st.markdown("#### Medienverlauf (echte Drucke)")
    st.line_chart(df_hist["RemainingPrints"], use_container_width=True)

    stats = compute_print_stats(df, window_min=30, media_factor=media_factor)

    last_remaining = int(df_hist["RemainingPrints"].iloc[-1])
    prints_since_reset = max(0, (st.session_state.max_prints or 0) - last_remaining)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Log-Einträge", len(df_hist))
    c2.metric("Gedruckt (Reset)", prints_since_reset)

    ppm_sess = stats['ppm_overall']
    c3.metric("Ø Drucke/Std (Total)", f"{ppm_sess * 60:.1f}" if ppm_sess else "–")

    ppm_win = stats['ppm_window']
    c4.metric("Ø Drucke/Std (30min)", f"{ppm_win * 60:.1f}" if ppm_win else "–")

    st.markdown("#### Kostenabschätzung")
    col_cost1, col_cost2 = st.columns(2)
    if cost_per_roll and (st.session_state.max_prints or 0) > 0:
        try:
            cost_per_print = cost_per_roll / st.session_state.max_prints
            cost_used = prints_since_reset * cost_per_print
            col_cost1.metric("Kosten seit Reset", f"{cost_used:0.2f} €")
            col_cost2.metric("Kosten pro Druck", f"{cost_per_print:0.3f} €")
        except Exception:
            col_cost1.metric("Kosten seit Reset", "–")
            col_cost2.metric("Kosten pro Druck", "–")
    else:
        col_cost1.metric("Kosten seit Reset", "–")
        col_cost2.metric("Kosten pro Druck", "–")

    st.markdown("#### Rohdaten (letzte 200 Zeilen)")
    st.dataframe(df.tail(200), use_container_width=True)


# --------------------------------------------------------------------
# ADMIN PANEL (Optimiert - Mit Tabs)
# --------------------------------------------------------------------
def render_admin_panel(printer_cfg: Dict[str, Any], warning_threshold: int) -> None:
    """
    Admin-Bereich mit Tabs für bessere Übersicht.
    """
    printer_has_aqara = printer_cfg.get("has_aqara", False)
    printer_has_dsr = printer_cfg.get("has_dsr", False)

    st.subheader("🛠️ Admin & Einstellungen") 

    # Tabs erstellen
    tab_paper, tab_report, tab_notify, tab_devices = st.tabs([
        "🧻 Papier & Reset", 
        "📊 Report", 
        "🔔 Benachrichtigung", 
        "🔌 Geräte"
    ])

    # --- TAB 1: NEUER AUFTRAG / PAPIERWECHSEL ---
    with tab_paper:
        st.markdown("### Neuer Auftrag / Papierwechsel")

        col_size, col_note = st.columns([1, 2])

        with col_size:
            st.caption("Paketgröße")
            size_options = [200, 400]
            try:
                current_size = int(
                    st.session_state.max_prints or printer_cfg["default_max_prints"]
                )
            except Exception:
                current_size = printer_cfg["default_max_prints"]
            idx = 0 if current_size == 200 else 1
            size = st.radio(
                "Paketgröße",
                size_options,
                horizontal=True,
                index=idx,
                label_visibility="collapsed",
                key="tab_paper_size"
            )

        with col_note:
            st.caption("Notiz (optional)")
            reset_note = st.text_input(
                "Notiz zum Papierwechsel",
                key="reset_note",
                label_visibility="collapsed",
                placeholder="z.B. neue 400er Rolle eingelegt",
            )

        st.markdown("")
        col_btn, _ = st.columns([1, 3])
        with col_btn:
            if not st.session_state.confirm_reset:
                if st.button("Papierwechsel & Reset 🔄", use_container_width=True):
                    st.session_state.confirm_reset = True
                    st.session_state.temp_package_size = size
                    st.session_state.temp_reset_note = reset_note
                    st.rerun()
            else:
                st.info("Bitte bestätigen.")

        # Bestätigungsbereich
        if st.session_state.confirm_reset:
            st.warning(f"Wirklich Log löschen und auf {st.session_state.temp_package_size}er Rolle zurücksetzen?")
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("Ja, zurücksetzen ✅", use_container_width=True):
                    st.session_state.max_prints = st.session_state.temp_package_size
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
            with col_no:
                if st.button("Abbrechen ❌", use_container_width=True):
                    st.session_state.confirm_reset = False
                    st.rerun()

    # --- TAB 2: REPORT & EXPORT ---
    with tab_report:
        st.markdown("### 📊 Event-Abschluss")
        st.write("Erstelle einen PDF-Bericht über das aktuelle Event.")
        
        if st.button("PDF Bericht erstellen 📄", use_container_width=True):
            df_rep = get_data_admin(st.session_state.sheet_id)
            media_factor = printer_cfg.get("media_factor", 1)
            stats = compute_print_stats(df_rep, media_factor=media_factor)
            
            if not df_rep.empty:
                last_val = int(df_rep.iloc[-1].get("MediaRemaining", 0)) * media_factor
            else:
                last_val = 0
            prints_done = max(0, (st.session_state.max_prints or 0) - last_val)
            
            cost_str = "N/A"
            cpr = printer_cfg.get("cost_per_roll_eur")
            if cpr and st.session_state.max_prints:
                  c_used = prints_done * (cpr / st.session_state.max_prints)
                  cost_str = f"{c_used:.2f} EUR"

            pdf_bytes = generate_event_pdf(
                df=df_rep,
                printer_name=st.session_state.selected_printer,
                stats=stats,
                prints_since_reset=prints_done,
                cost_info=cost_str,
                media_factor=media_factor
            )
            
            st.download_button(
                label="⬇️ PDF Herunterladen",
                data=pdf_bytes,
                file_name=f"report_{datetime.date.today()}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

    # --- TAB 3: BENACHRICHTIGUNGEN ---
    with tab_notify:
        st.markdown("### Benachrichtigungen & Tests")

        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.caption("ntfy Topic (nur zur Info)")
            st.text_input(
                "ntfy Topic",
                value=st.session_state.ntfy_topic or "(kein Topic konfiguriert)",
                key="ntfy_topic_display",
                disabled=True,
                label_visibility="collapsed",
            )

            if st.button("Test-Push senden 🔔", use_container_width=True):
                send_ntfy_push("Test", "Test erfolgreich", tags="tada")
                st.toast("Test wurde gesendet.")

        with col_right:
            st.caption("Status-Simulation")
            sim_option = st.selectbox(
                "Status simulieren",
                ["Keine", "Fehler", "Papier fast leer", "Keine Daten"],
                label_visibility="collapsed",
                key="status_sim_option",
            )

            if st.button("Auslösen", use_container_width=True):
                if sim_option == "Fehler":
                    send_ntfy_push("🔴 Fehler (Test)", "Simulierter Fehlerzustand", tags="rotating_light")
                    maybe_play_sound("error", st.session_state.sound_enabled)
                elif sim_option == "Papier fast leer":
                    send_ntfy_push("⚠️ Papier fast leer (Test)", "Simulierter Low-Paper-Status", tags="warning")
                    maybe_play_sound("low_paper", st.session_state.sound_enabled)
                elif sim_option == "Keine Daten":
                    send_ntfy_push("⚠️ Keine aktuellen Daten (Test)", "Simulierter Stale-Status", tags="hourglass")
                    maybe_play_sound("stale", st.session_state.sound_enabled)
                st.toast("Simulation gesendet.")

    # --- TAB 4: GERÄTESTEUERUNG ---
    with tab_devices:
        st.markdown("### Gerätesteuerung")

        if not printer_has_aqara and not printer_has_dsr:
            st.info("Für diese Fotobox sind keine Geräte-Steuerungen konfiguriert.")
        else:
            col_aqara, col_dsr = st.columns(2)

            # --- Aqara Steckdose ---
            with col_aqara:
                st.subheader("Aqara", anchor=False)
                if not printer_has_aqara:
                    st.caption("Nicht verfügbar")
                elif not AQARA_ENABLED:
                    st.warning("Konfig fehlt (secrets)")
                else:
                    current_state, debug_data = aqara_client.get_socket_state(
                        AQARA_SOCKET_DEVICE_ID, AQARA_SOCKET_RESOURCE_ID,
                    )
                    st.session_state.socket_debug = debug_data

                    if current_state in ("on", "off"):
                        st.session_state.socket_state = current_state
                    
                    state = st.session_state.socket_state

                    st.write(f"Status: **{state.upper()}**")
                    
                    c_on, c_off = st.columns(2)
                    if c_on.button("An 🟢", use_container_width=True, key="aq_on"):
                        response = aqara_client.switch_socket(AQARA_SOCKET_DEVICE_ID, True, AQARA_SOCKET_RESOURCE_ID)
                        if response.get("code") == 0:
                            st.session_state.socket_state = "on"
                            st.toast("Steckdose eingeschaltet!", icon="✅")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Schalten fehlgeschlagen: {response}")
                            
                    if c_off.button("Aus ⚪", use_container_width=True, key="aq_off"):
                        aqara_client.switch_socket(AQARA_SOCKET_DEVICE_ID, False, AQARA_SOCKET_RESOURCE_ID)
                        st.session_state.socket_state = "off"
                        st.rerun()

            # --- dsrBooth ---
            with col_dsr:
                st.subheader("Lockscreen", anchor=False)
                if not printer_has_dsr:
                    st.caption("Nicht verfügbar")
                elif not DSR_ENABLED:
                        st.warning("Konfig fehlt (secrets)")
                else:
                    state = st.session_state.get("lockscreen_state", "off")
                    st.write(f"Status: **{state.upper()}**")

                    l_on, l_off = st.columns(2)
                    if l_on.button("Sperren 🔒", use_container_width=True, key="dsr_l"):
                        send_dsr_command("lock_on")
                        st.session_state.lockscreen_state = "on"
                        st.rerun()
                    if l_off.button("Frei 🔓", use_container_width=True, key="dsr_u"):
                        send_dsr_command("lock_off")
                        st.session_state.lockscreen_state = "off"
                        st.rerun()


# --------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------
def main():
    st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="centered")
    
    # 1. Custom CSS injizieren (WICHTIG für WOW Effekt)
    inject_custom_css()
    
    init_session_state()
    check_login()
    render_logout_button()

    st.sidebar.header("Einstellungen")

    view_mode = st.sidebar.radio("Ansicht", ["Einzelne Fotobox", "Alle Boxen"])

    # Flottenübersicht (Neu: Nutzt Glassmorphism Cards)
    if view_mode == "Alle Boxen":
        render_fleet_overview(PRINTERS)
        return

    # Einzelne Box
    printer_name = st.sidebar.selectbox("Fotobox auswählen", list(PRINTERS.keys()))
    printer_cfg = PRINTERS[printer_name]

    media_factor = printer_cfg.get("media_factor", 2)
    cost_per_roll = printer_cfg.get("cost_per_roll_eur")
    warning_threshold = printer_cfg.get("warning_threshold", 20)
    printer_has_admin = printer_cfg.get("has_admin", True)

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

    # sheet-bezogene Infos im State
    st.session_state.sheet_id = sheet_id
    st.session_state.ntfy_topic = ntfy_topic

    # Settings laden
    if st.session_state.selected_printer != printer_name:
        st.session_state.selected_printer = printer_name
        st.session_state.last_warn_status = None
        st.session_state.last_sound_status = None

        try:
            pkg = get_setting("package_size", printer_cfg["default_max_prints"])
            st.session_state.max_prints = int(pkg)
        except Exception:
            st.session_state.max_prints = printer_cfg["default_max_prints"]

    if "ntfy_active" not in st.session_state:
        try:
            default_ntfy = get_setting("ntfy_active", str(NTFY_ACTIVE_DEFAULT))
            st.session_state.ntfy_active = str(default_ntfy).lower() == "true"
        except Exception:
            st.session_state.ntfy_active = NTFY_ACTIVE_DEFAULT

    if "event_mode" not in st.session_state:
        try:
            default_view = get_setting("default_view", "admin")
            st.session_state.event_mode = default_view == "event"
        except Exception:
            st.session_state.event_mode = False

    if "sound_enabled" not in st.session_state:
        st.session_state.sound_enabled = False

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

    st.session_state.sound_enabled = sound_enabled

    # ---------------- UI ----------------
    st.title(f"{PAGE_ICON} {PAGE_TITLE}")

    view_event_mode = event_mode or not printer_has_admin

    if view_event_mode:
        show_live_status(media_factor, cost_per_roll, sound_enabled, event_mode=True)
        # Legende / Hilfe entfernt
        
        st.write("")
        st.link_button("☁️ Fotoshare Cloud", "https://fotoshare.co/admin/index", use_container_width=True)

    else:
        tab_live, tab_hist = st.tabs(["🚀 Live Dashboard", "📈 Analyse"])
        with tab_live:
            show_live_status(media_factor, cost_per_roll, sound_enabled, event_mode=False)
            # Legende / Hilfe entfernt
            
            st.write("")
            st.link_button("☁️ Fotoshare Cloud", "https://fotoshare.co/admin/index", use_container_width=True)

        with tab_hist:
            show_history(media_factor, cost_per_roll)

        st.markdown("---")
        render_admin_panel(printer_cfg, warning_threshold)


if __name__ == "__main__":
    main()
