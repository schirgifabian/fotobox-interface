# app.py

import time
import json
import datetime
import re
import unicodedata

import requests
import streamlit as st
import extra_streamlit_components as stx
import pandas as pd

from aqara_client import AqaraClient
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
    render_status_help,
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
        "warning_threshold": 20,
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
        "cost_per_roll_eur": 60,
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


def send_ntfy_push(title, message, tags="warning", priority="default"):
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
        resp = requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode("utf-8"),
            headers=headers,
            timeout=5,
        )
        if not resp.ok:
            st.error(f"ntfy Fehler: {resp.status_code} – {resp.text[:200]}")
    except Exception as e:
        st.error(f"Exception bei ntfy: {e}")


def send_dsr_command(cmd: str):
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
# AQARA – KONFIG
# --------------------------------------------------------------------
def init_aqara():
    try:
        if "aqara" not in st.secrets:
            return False, None, None, "4.1.85"
            
        aqara_cfg = st.secrets["aqara"]
        # Keine Argumente mehr, Client liest Secrets/Datei selbst
        client = AqaraClient()
        
        return True, client, aqara_cfg["device_id"], aqara_cfg.get("resource_id", "4.1.85")
    except Exception as e:
        print(f"Aqara Init Fehler: {e}")
        return False, None, None, "4.1.85"

# Beachte: AQARA_ACCESS_TOKEN ist hier weggefallen!
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
# LIVE-STATUS VIEW
# --------------------------------------------------------------------
@st.fragment(run_every=10)
def show_live_status(media_factor: int, cost_per_roll: float, sound_enabled: bool, event_mode: bool):
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

        st.markdown(
            f"""
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
            """,
            unsafe_allow_html=True,
        )

        if status_mode == "error":
            st.error("Bitte Drucker und Papier prüfen (Störung aktiv).")
        elif status_mode == "stale":
            st.warning("Seit einigen Minuten keine Daten – Verbindung / Script prüfen.")

        # Papierstatus
        st.markdown("### Papierstatus")

        prints_since_reset = max(0, (st.session_state.max_prints or 0) - media_remaining)

        stats = compute_print_stats(df, window_min=30, media_factor=media_factor)
        forecast = "–"

        if status_mode == "error":
            forecast = "Gestört"
        else:
            ppm = stats.get("ppm_window") or stats.get("ppm_overall")
            if ppm and ppm > 0 and media_remaining > 0:
                minutes_left = media_remaining / ppm
                forecast = humanize_minutes(minutes_left)
            elif media_remaining > 0:
                minutes_left = media_remaining * 1.0
                forecast = humanize_minutes(minutes_left)
            else:
                forecast = "0 Min."

        colA, colB, colC = st.columns(3)
        colA.metric("Verbleibend", f"{media_remaining} Stk", f"von {st.session_state.max_prints}")
        colB.metric("Restlaufzeit (geschätzt)", forecast)

        if cost_per_roll and (st.session_state.max_prints or 0) > 0:
            try:
                cost_per_print = cost_per_roll / st.session_state.max_prints
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


# --------------------------------------------------------------------
# HISTORIE VIEW
# --------------------------------------------------------------------
def show_history(media_factor: int, cost_per_roll: float):
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
# ADMIN PANEL (neue, aufgeräumte Version)
# --------------------------------------------------------------------
def render_admin_panel(printer_cfg, warning_threshold):
    """
    Admin-Bereich in 3 klare Blöcke:
    1) Papierwechsel
    2) Benachrichtigungen & Tests
    3) Gerätesteuerung (Aqara / dsrBooth)
    """

    printer_has_aqara = printer_cfg.get("has_aqara", False)
    printer_has_dsr = printer_cfg.get("has_dsr", False)

    with st.expander("🛠️ Admin & Einstellungen"):

        # ------------------------------------------------------------------
        # 1) NEUER AUFTRAG / PAPIERWECHSEL
        # ------------------------------------------------------------------
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
            )

        with col_note:
            st.caption("Notiz zum Papierwechsel (optional)")
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
                if st.button(
                    "Papierwechsel durchführen & Zähler zurücksetzen 🔄",
                    use_container_width=True,
                ):
                    # Schritt 1: nur vormerken, nicht sofort löschen
                    st.session_state.confirm_reset = True
                    st.session_state.temp_package_size = size
                    st.session_state.temp_reset_note = reset_note
                    st.rerun()
            else:
                st.info("Bitte unten bestätigen oder abbrechen.")

        # Bestätigungsbereich nur anzeigen, wenn confirm_reset = True
        if st.session_state.confirm_reset:
            st.warning(
                f"Möchtest du wirklich das Log löschen und auf eine {st.session_state.temp_package_size}er Rolle zurücksetzen?"
            )
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("Ja, zurücksetzen ✅", use_container_width=True):
                    # Paketgröße übernehmen & in Settings speichern
                    st.session_state.max_prints = st.session_state.temp_package_size
                    try:
                        set_setting("package_size", st.session_state.max_prints)
                    except Exception:
                        pass
                    # Log löschen & Meta-Log-Eintrag
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

        st.markdown("---")

        # ------------------------------------------------------------------
        # 2) BENACHRICHTIGUNGEN & TESTS
        # ------------------------------------------------------------------
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
                    maybe_play_sound("stale", st.session_state.sound_enabled)
                st.toast("Simulation gesendet.")

        st.markdown("---")

        # ------------------------------------------------------------------
        # 3) GERÄTESTEUERUNG (Aqara & dsrBooth)
        # ------------------------------------------------------------------
        st.markdown("### Gerätesteuerung")

        if not printer_has_aqara and not printer_has_dsr:
            st.info("Für diese Fotobox sind keine Geräte-Steuerungen konfiguriert.")
            return

        col_aqara, col_dsr = st.columns(2)

        # --- Aqara Steckdose ------------------------------------------------
        with col_aqara:
            st.subheader("Aqara Steckdose", anchor=False)

            if not printer_has_aqara:
                st.info("Keine Aqara-Steckdose für diese Box hinterlegt.")
            elif not AQARA_ENABLED:
                st.info(
                    "Aqara ist nicht konfiguriert. Bitte [aqara] in secrets.toml setzen."
                )
            else:
                current_state, debug_data = aqara_client.get_socket_state(
                    AQARA_SOCKET_DEVICE_ID,
                    AQARA_SOCKET_RESOURCE_ID,
                )

                st.session_state.socket_debug = debug_data

                if current_state in ("on", "off"):
                    st.session_state.socket_state = current_state
                elif st.session_state.socket_state not in ("on", "off"):
                    st.session_state.socket_state = "unknown"

                state = st.session_state.socket_state

                click_on, click_off = render_toggle_card(
                    section_title="Fotobox-Steckdose",
                    description=(
                        "Schaltet die Stromversorgung der Fotobox über die Aqara-Steckdose."
                    ),
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

                desired_state = True if click_on else False if click_off else None

                if desired_state is not None and desired_state != (state == "on"):
                    res = aqara_client.switch_socket(
                    AQARA_SOCKET_DEVICE_ID,
                    turn_on=desired_state,
                    resource_id=AQARA_SOCKET_RESOURCE_ID
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

        # --- dsrBooth Lockscreen -------------------------------------------
        with col_dsr:
            st.subheader("dsrBooth Lockscreen", anchor=False)

            if not printer_has_dsr:
                st.info("Kein dsrBooth-Lockscreen für diese Box hinterlegt.")
            elif not DSR_ENABLED:
                st.info(
                    "dsrBooth-Steuerung ist nicht konfiguriert. "
                    "Bitte [dsrbooth] mit control_topic in secrets.toml setzen."
                )
            else:
                # Status aus Session lesen (Default: off/unlocked)
                state = st.session_state.get("lockscreen_state", "off")

                click_on, click_off = render_toggle_card(
                    section_title="Gäste-Lockscreen",
                    description=(
                        "Sperrt oder gibt den Gästemodus in dsrBooth frei. "
                        "Status basiert auf letzter Aktion (kein Rückkanal)."
                    ),
                    state=state,
                    title_on="GESPERRT",
                    title_off="FREIGEGEBEN",
                    title_unknown="UNBEKANNT",
                    badge_prefix="Status",
                    icon_on="🔒",
                    icon_off="🔓",
                    icon_unknown="⚠️",
                    btn_left_label="Sperren",
                    btn_right_label="Freigeben",
                    btn_left_key="dsr_btn_lock",
                    btn_right_key="dsr_btn_unlock",
                )

                # Ermitteln, welcher Status gewünscht ist
                desired_state = None
                if click_on:
                    desired_state = True  # Sperren
                elif click_off:
                    desired_state = False # Freigeben

                # Wenn ein Button geklickt wurde:
                if desired_state is not None:
                    cmd = "lock_on" if desired_state else "lock_off"
                    
                    # 1. Befehl senden
                    send_dsr_command(cmd)
                    
                    # 2. Lokalen Status aktualisieren & speichern
                    st.session_state.lockscreen_state = "on" if desired_state else "off"
                    
                    # 3. Feedback geben & UI aktualisieren
                    action_text = "aktiviert" if desired_state else "deaktiviert"
                    st.success(f"Befehl gesendet: Lockscreen {action_text}.")
                    
                    time.sleep(0.5) 
                    st.rerun()




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

    # Settings laden (max_prints, ntfy_active, default_view)
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
        render_status_help(warning_threshold)
        
        # NEUER BUTTON
        st.write("")
        st.link_button("☁️ Fotoshare Cloud", "https://fotoshare.co/admin/index", use_container_width=True)

    else:
        tab_live, tab_hist = st.tabs(["Live-Status", "Historie & Analyse"])
        with tab_live:
            show_live_status(media_factor, cost_per_roll, sound_enabled, event_mode=False)
            render_status_help(warning_threshold)
            
            # NEUER BUTTON
            st.write("")
            st.link_button("☁️ Fotoshare Cloud", "https://fotoshare.co/admin/", use_container_width=True)

        with tab_hist:
            show_history(media_factor, cost_per_roll)

        st.markdown("---")
        render_admin_panel(printer_cfg, warning_threshold)


if __name__ == "__main__":
    main()
