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

# Neue Importe für die optimierte Struktur
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
    render_hero_card,
)

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
        "has_aqara": False,
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
    if not isinstance(val, str):
        val = str(val)

    val = val.replace("\r", " ").replace("\n", " ")
    val = unicodedata.normalize("NFKC", val)
    val = re.sub(r"[\U00010000-\U0010FFFF]", "", val)
    val = val.encode("latin-1", "ignore").decode("latin-1")
    val = val.strip()

    if not val:
        val = default

    return val


def send_ntfy_push(title: str, message: str, tags: str = "warning", priority: str = "default") -> None:
    if not st.session_state.get("ntfy_active", False):
        return

    topic = st.session_state.get("ntfy_topic")
    if not topic:
        return

    safe_title = _sanitize_header_value(title, default="Status")
    safe_tags = _sanitize_header_value(tags, default="info")
    safe_priority = _sanitize_header_value(priority, default="default")

    try:
        headers = {
            "Title": safe_title,
            "Tags": safe_tags,
            "Priority": safe_priority,
        }
        # Requests ohne Retry, da Push "Fire & Forget" ist
        requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode("utf-8"),
            headers=headers,
            timeout=5,
        )
    except Exception as e:
        st.error(f"ntfy Fehler: {e}")


def send_dsr_command(cmd: str) -> None:
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
# AQARA – KONFIG (Optimiert 3.B)
# --------------------------------------------------------------------
def init_aqara() -> Tuple[bool, Optional[AqaraClient], Optional[str], str]:
    try:
        if "aqara" not in st.secrets:
            return False, None, None, "4.1.85"
            
        aqara_cfg = st.secrets["aqara"]
        # Client liest Secrets und Tokens jetzt selbständig
        client = AqaraClient()
        
        return True, client, aqara_cfg["device_id"], aqara_cfg.get("resource_id", "4.1.85")
    except Exception as e:
        print(f"Aqara Init Fehler: {e}")
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
# LIVE-STATUS VIEW (Optimiert 2.C & 4.A)
# --------------------------------------------------------------------
@st.fragment(run_every=10)
def show_live_status(media_factor: int, cost_per_roll: float, sound_enabled: bool, event_mode: bool) -> None:
    df = get_data(st.session_state.sheet_id, event_mode=event_mode)
    if df.empty:
        st.info("System wartet auf Start…")
        st.caption("Noch keine Druckdaten empfangen.")
        return

    try:
        last = df.iloc[-1]
        timestamp = str(last.get("Timestamp", ""))
        raw_status = str(last.get("Status", ""))

        try:
            media_remaining_raw = int(last.get("MediaRemaining", 0))
        except Exception:
            media_remaining_raw = 0

        media_remaining = media_remaining_raw * media_factor

        status_mode, display_text, display_color, push, minutes_diff = evaluate_status(
            raw_status, media_remaining, timestamp
        )

        if push is not None:
            title, msg, tags = push
            send_ntfy_push(title, msg, tags=tags)

        maybe_play_sound(status_mode, sound_enabled)

        heartbeat_info = f" (vor {minutes_diff} Min)" if minutes_diff is not None else ""

        # --- BERECHNUNGEN VORZIEHEN (für Unified Card) ---
        stats = compute_print_stats(df, window_min=30, media_factor=media_factor)
        prints_since_reset = max(0, (st.session_state.max_prints or 0) - media_remaining)
        
        # Prognose berechnen
        forecast_str = "–"
        end_time_str = ""
        if status_mode == "error":
            forecast_str = "Gestört"
        else:
            ppm = stats.get("ppm_window") or stats.get("ppm_overall")
            if ppm and ppm > 0 and media_remaining > 0:
                minutes_left = media_remaining / ppm
                now = datetime.datetime.now()
                end_time = now + datetime.timedelta(minutes=minutes_left)
                end_time_formatted = end_time.strftime("%H:%M")
                
                forecast_str = humanize_minutes(minutes_left)
                end_time_str = f" (bis ca. {end_time_formatted} Uhr)"
            elif media_remaining > 0:
                forecast_str = "Warte auf Drucke..."
            else:
                forecast_str = "0 Min."
        
        # Kosten berechnen
        cost_txt = "–"
        if cost_per_roll and (st.session_state.max_prints or 0) > 0:
            try:
                cost_per_print = cost_per_roll / st.session_state.max_prints
                cost_used = prints_since_reset * cost_per_print
                cost_txt = f"{cost_used:0.2f} €"
            except Exception: pass

        # --- NEUES UI RENDERN ---
        render_hero_card(
            status_mode=status_mode,
            display_text=display_text,
            display_color=display_color,
            timestamp=timestamp,
            heartbeat_info=heartbeat_info,
            media_remaining=media_remaining,
            max_prints=st.session_state.max_prints or 400,
            forecast_str=forecast_str,
            end_time_str=end_time_str,
            cost_txt=cost_txt
        )

        if status_mode == "error":
            st.error("Bitte Drucker und Papier prüfen (Störung aktiv).")
        elif status_mode == "stale":
            st.warning("Seit einigen Minuten keine Daten – Verbindung / Script prüfen.")

    except Exception as e:
        st.error(f"Fehler bei der Datenverarbeitung: {e}")


# --------------------------------------------------------------------
# HISTORIE VIEW
# --------------------------------------------------------------------
def show_history(media_factor: int, cost_per_roll: float) -> None:
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
    df_hist["RemainingPrints"] = df_hist["MediaRemaining"] * media_factor

    st.markdown("#### Medienverlauf (echte Drucke)")
    st.line_chart(df_hist["RemainingPrints"], use_container_width=True)

    stats = compute_print_stats(df, window_min=30, media_factor=media_factor)

    last_remaining = int(df_hist["RemainingPrints"].iloc[-1])
    prints_since_reset = max(0, (st.session_state.max_prints or 0) - last_remaining)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Log-Einträge", len(df_hist))
    c2.metric("Drucke seit Reset (geschätzt)", prints_since_reset)

    if stats["ppm_overall"]:
        c3.metric("Ø Drucke/Std (Session)", f"{stats['ppm_overall'] * 60:.1f}")
    else:
        c3.metric("Ø Drucke/Std (Session)", "–")

    if stats["ppm_window"]:
        c4.metric("Ø Drucke/Std (letzte 30 Min)", f"{stats['ppm_window'] * 60:.1f}")
    else:
        c4.metric("Ø Drucke/Std (letzte 30 Min)", "–")

    st.markdown("#### Kostenabschätzung")
    col_cost1, col_cost2 = st.columns(2)
    if cost_per_roll and (st.session_state.max_prints or 0) > 0:
        try:
            cost_per_print = cost_per_roll / st.session_state.max_prints
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


# --------------------------------------------------------------------
# ADMIN PANEL (Optimiert - Mit Tabs)
# --------------------------------------------------------------------
def render_admin_panel(printer_cfg: Dict[str, Any], warning_threshold: int, printer_key: str) -> None:
    """
    Admin-Bereich mit Tabs für bessere Übersicht.
    Keys sind jetzt unique durch printer_key suffix.
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

    # ------------------------------------------------------------------
    # TAB 1: GERÄTESTEUERUNG
    # ------------------------------------------------------------------
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
                    # ACHTUNG: Hier wird globaler Device ID genutzt. 
                    # Falls du pro Drucker verschiedene Dosen hast, muss das hier dynamisch gelöst werden.
                    current_state, debug_data = aqara_client.get_socket_state(
                        AQARA_SOCKET_DEVICE_ID, AQARA_SOCKET_RESOURCE_ID,
                    )
                    st.session_state.socket_debug = debug_data

                    if current_state in ("on", "off"):
                        st.session_state.socket_state = current_state
                    
                    state = st.session_state.socket_state

                    st.write(f"Status: **{state.upper()}**")
                    
                    c_on, c_off = st.columns(2)
                    # UNIQUE KEY FIX:
                    if c_on.button("An 🟢", use_container_width=True, key=f"aq_on_{printer_key}"):
                        response = aqara_client.switch_socket(AQARA_SOCKET_DEVICE_ID, True, AQARA_SOCKET_RESOURCE_ID)
                        if response.get("code") == 0:
                            st.session_state.socket_state = "on"
                            st.toast("Steckdose eingeschaltet!", icon="✅")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Schalten fehlgeschlagen: {response}")
                            
                    # UNIQUE KEY FIX:
                    if c_off.button("Aus ⚪", use_container_width=True, key=f"aq_off_{printer_key}"):
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
                    # UNIQUE KEY FIX:
                    if l_on.button("Sperren 🔒", use_container_width=True, key=f"dsr_l_{printer_key}"):
                        send_dsr_command("lock_on")
                        st.session_state.lockscreen_state = "on"
                        st.rerun()
                    # UNIQUE KEY FIX:
                    if l_off.button("Frei 🔓", use_container_width=True, key=f"dsr_u_{printer_key}"):
                        send_dsr_command("lock_off")
                        st.session_state.lockscreen_state = "off"
                        st.rerun()

    
    # ------------------------------------------------------------------
    # TAB 2: NEUER AUFTRAG / PAPIERWECHSEL
    # ------------------------------------------------------------------
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
            
            # Fallback falls current_size nicht in options ist
            idx = 1 # Default 400
            if current_size == 200: idx = 0
            
            # UNIQUE KEY FIX:
            size = st.radio(
                "Paketgröße",
                size_options,
                horizontal=True,
                index=idx,
                label_visibility="collapsed",
                key=f"tab_paper_size_{printer_key}"
            )

        with col_note:
            st.caption("Notiz zum Papierwechsel (optional)")
            # UNIQUE KEY FIX:
            reset_note = st.text_input(
                "Notiz zum Papierwechsel",
                key=f"reset_note_{printer_key}",
                label_visibility="collapsed",
                placeholder="z.B. neue 400er Rolle eingelegt",
            )

        st.markdown("")
        col_btn, _ = st.columns([1, 3])
        with col_btn:
            if not st.session_state.confirm_reset:
                if st.button(
                    "Papierwechsel & Reset 🔄",
                    use_container_width=True,
                    key=f"btn_init_reset_{printer_key}" # UNIQUE KEY
                ):
                    st.session_state.confirm_reset = True
                    st.session_state.temp_package_size = size
                    st.session_state.temp_reset_note = reset_note
                    st.rerun()
            else:
                st.info("Bitte bestätigen.")

        # Bestätigungsbereich
        if st.session_state.confirm_reset:
            st.warning(
                f"Wirklich Log löschen und auf {st.session_state.get('temp_package_size', '?')}er Rolle zurücksetzen?"
            )
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("Ja, zurücksetzen ✅", use_container_width=True, key=f"btn_yes_{printer_key}"):
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
                if st.button("Abbrechen ❌", use_container_width=True, key=f"btn_no_{printer_key}"):
                    st.session_state.confirm_reset = False
                    st.rerun()

    # ------------------------------------------------------------------
    # TAB 3: REPORT & EXPORT
    # ------------------------------------------------------------------
    with tab_report:
        st.markdown("### 📊 Event-Abschluss")
        st.write("Erstelle einen PDF-Bericht über das aktuelle Event.")
        
        # UNIQUE KEY FIX:
        if st.button("PDF Bericht erstellen 📄", use_container_width=True, key=f"btn_pdf_{printer_key}"):
            df_rep = get_data_admin(st.session_state.sheet_id)
            media_factor = printer_cfg.get("media_factor", 1)
            stats = compute_print_stats(df_rep, media_factor=media_factor)
            
            if not df_rep.empty:
                try:
                    last_val = int(df_rep.iloc[-1].get("MediaRemaining", 0)) * media_factor
                except: last_val = 0
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
                use_container_width=True,
                key=f"dl_btn_{printer_key}" # UNIQUE KEY
            )

    # ------------------------------------------------------------------
    # TAB 4: BENACHRICHTIGUNGEN
    # ------------------------------------------------------------------
    with tab_notify:
        st.markdown("### Benachrichtigungen & Tests")

        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.caption("ntfy Topic (nur zur Info)")
            # UNIQUE KEY FIX:
            st.text_input(
                "ntfy Topic",
                value=st.session_state.ntfy_topic or "(kein Topic konfiguriert)",
                key=f"ntfy_topic_display_{printer_key}",
                disabled=True,
                label_visibility="collapsed",
            )
            # UNIQUE KEY FIX:
            if st.button("Test-Push senden 🔔", use_container_width=True, key=f"btn_test_push_{printer_key}"):
                send_ntfy_push("Test", "Test erfolgreich", tags="tada")
                st.toast("Test wurde gesendet.")

        with col_right:
            st.caption("Status-Simulation")
            # UNIQUE KEY FIX:
            sim_option = st.selectbox(
                "Status simulieren",
                ["Keine", "Fehler", "Papier fast leer", "Keine Daten"],
                label_visibility="collapsed",
                key=f"status_sim_option_{printer_key}",
            )

            if st.button("Auslösen", use_container_width=True, key=f"btn_sim_trigger_{printer_key}"):
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



# --------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------
def main():
    st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="centered")
    inject_custom_css()
    init_session_state()
    check_login()
    render_logout_button()

    st.sidebar.header("Einstellungen")

    view_mode = st.sidebar.radio("Ansicht", ["Einzelne Fotobox", "Alle Boxen"])

    # Flottenübersicht
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
        
        # --- FIX: State aufräumen beim Wechsel ---
        st.session_state.confirm_reset = False
        st.session_state.socket_state = "unknown"
        st.session_state.last_warn_status = None
        st.session_state.last_sound_status = None
        # -----------------------------------------

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
        tab_live, tab_hist = st.tabs(["Live-Status", "Historie & Analyse"])
        with tab_live:
            show_live_status(media_factor, cost_per_roll, sound_enabled, event_mode=False)
            # Legende / Hilfe entfernt
            
            st.write("")
            st.link_button("☁️ Fotoshare Cloud", "https://fotoshare.co/admin/index", use_container_width=True)
    
        with tab_hist:
            show_history(media_factor, cost_per_roll)

        st.markdown("---")
        # HIER: printer_key übergeben!
        render_admin_panel(printer_cfg, warning_threshold, printer_key)


if __name__ == "__main__":
    main()
