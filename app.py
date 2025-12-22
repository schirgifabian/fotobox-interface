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

# Importe
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
    # render_status_help wurde entfernt
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
# AQARA – KONFIG
# --------------------------------------------------------------------
def init_aqara() -> Tuple[bool, Optional[AqaraClient], Optional[str], str]:
    try:
        if "aqara" not in st.secrets:
            return False, None, None, "4.1.85"
            
        aqara_cfg = st.secrets["aqara"]
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
# LIVE-STATUS VIEW
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

        # HERO HEADER
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%);
                padding: 30px;
                border-radius: 24px;
                border: 1px solid #E2E8F0;
                margin-bottom: 24px;
                text-align: center;
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05);
            ">
                <div style="font-size: 1rem; color: #64748B; margin-bottom: 8px; font-weight: 600;">
                    AKTUELLER STATUS
                </div>
                <div style="
                    font-size: 2.5rem; 
                    font-weight: 800; 
                    color: {display_color};
                    letter-spacing: -0.02em;
                    margin-bottom: 8px;
                ">
                    {display_text.replace('✅ ', '').replace('🔴 ', '').replace('⚠️ ', '')}
                </div>
                 <div style="
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    background: #F1F5F9;
                    padding: 6px 16px;
                    border-radius: 99px;
                    color: #475569;
                    font-size: 0.85rem;
                ">
                    <span>🕒</span> Letztes Signal: {timestamp} {heartbeat_info}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if status_mode == "error":
            st.error("Bitte Drucker und Papier prüfen (Störung aktiv).")
        elif status_mode == "stale":
            st.warning("Seit einigen Minuten keine Daten – Verbindung / Script prüfen.")

        # PAPIER STATUS
        st.markdown("### Papierstatus")

        prints_since_reset = max(0, (st.session_state.max_prints or 0) - media_remaining)
        stats = compute_print_stats(df, window_min=30, media_factor=media_factor)
        
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

        colA, colB, colC = st.columns(3)
        colA.metric("Verbleibend", f"{media_remaining} Stk", f"von {st.session_state.max_prints}")
        colB.metric("Reichweite", forecast_str, end_time_str)

        cost_txt = "–"
        if cost_per_roll and (st.session_state.max_prints or 0) > 0:
            try:
                cost_per_print = cost_per_roll / st.session_state.max_prints
                cost_used = prints_since_reset * cost_per_print
                cost_txt = f"{cost_used:0.2f} €"
                colC.metric("Kosten (live)", cost_txt)
            except Exception:
                colC.metric("Kosten (live)", "–")
        else:
            colC.metric("Kosten (live)", "–")

        # Progress-Bar
        if status_mode == "error" and media_remaining == 0:
            bar_color = "red"
            progress_val = 0
        else:
            if not st.session_state.max_prints:
                progress_val = 0
            else:
                progress_val = max(0.0, min(1.0, media_remaining / st.session_state.max_prints))

            if progress_val < 0.1:
                bar_color = "red"
            elif progress_val < 0.25:
                bar_color = "orange"
            else:
                bar_color = "blue"

        st.markdown(
            f"""<style>.stProgress > div > div > div > div {{ background-color: {bar_color}; }}</style>""",
            unsafe_allow_html=True,
        )
        st.progress(progress_val)

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
        st.info("Keine auswertbaren Daten.")
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
    c2.metric("Drucke seit Reset", prints_since_reset)
    
    val_ppm = f"{stats['ppm_overall'] * 60:.1f}" if stats['ppm_overall'] else "–"
    c3.metric("Ø Drucke/Std (Gesamt)", val_ppm)
    
    val_win = f"{stats['ppm_window'] * 60:.1f}" if stats['ppm_window'] else "–"
    c4.metric("Ø Drucke/Std (30 Min)", val_win)

    st.markdown("#### Rohdaten (letzte 200 Zeilen)")
    st.dataframe(df.tail(200), use_container_width=True)


# --------------------------------------------------------------------
# ADMIN PANEL (OPTIMIERT: TABS STATT ENDLOS-LISTE)
# --------------------------------------------------------------------
def render_admin_panel(printer_cfg: Dict[str, Any], warning_threshold: int) -> None:
    """
    Admin-Bereich: Jetzt mit Tabs für bessere Übersicht.
    """
    printer_has_aqara = printer_cfg.get("has_aqara", False)
    printer_has_dsr = printer_cfg.get("has_dsr", False)

    with st.expander("🛠️ Admin & Einstellungen", expanded=False):
        
        # Tabs erstellen
        tab_paper, tab_report, tab_devices, tab_notify = st.tabs([
            "🔄 Papier & Auftrag", 
            "📄 Bericht", 
            "🔌 Geräte", 
            "🔔 System & Tests"
        ])

        # --- TAB 1: PAPIERWECHSEL ---
        with tab_paper:
            st.markdown("#### Papierwechsel & Reset")
            
            col_size, col_note = st.columns([1, 2])
            with col_size:
                st.caption("Paketgröße")
                size_options = [200, 400]
                try:
                    curr = int(st.session_state.max_prints or printer_cfg["default_max_prints"])
                except:
                    curr = printer_cfg["default_max_prints"]
                idx = 0 if curr == 200 else 1
                size = st.radio("Size", size_options, horizontal=True, index=idx, label_visibility="collapsed")
            
            with col_note:
                st.caption("Notiz (optional)")
                reset_note = st.text_input("Reset-Notiz", key="reset_note", label_visibility="collapsed", placeholder="z.B. neue Rolle")

            st.write("")
            if not st.session_state.confirm_reset:
                if st.button("Zähler zurücksetzen 🔄", use_container_width=True):
                    st.session_state.confirm_reset = True
                    st.session_state.temp_package_size = size
                    st.session_state.temp_reset_note = reset_note
                    st.rerun()
            else:
                st.info("Bestätigung erforderlich:")
                col_yes, col_no = st.columns(2)
                if col_yes.button("Ja, Reset ✅", use_container_width=True):
                    st.session_state.max_prints = st.session_state.temp_package_size
                    try: set_setting("package_size", st.session_state.max_prints)
                    except: pass
                    clear_google_sheet()
                    log_reset_event(st.session_state.temp_package_size, st.session_state.temp_reset_note)
                    st.session_state.confirm_reset = False
                    st.rerun()
                if col_no.button("Abbruch ❌", use_container_width=True):
                    st.session_state.confirm_reset = False
                    st.rerun()

        # --- TAB 2: PDF REPORT ---
        with tab_report:
            st.markdown("#### Event-Abschluss & PDF")
            st.write("Erstelle einen PDF-Bericht über das aktuelle Event.")
            
            if st.button("PDF Bericht erstellen 📄", use_container_width=True):
                df_rep = get_data_admin(st.session_state.sheet_id)
                media_factor = printer_cfg.get("media_factor", 1)
                stats = compute_print_stats(df_rep, media_factor=media_factor)
                
                last_val = 0
                if not df_rep.empty:
                    last_val = int(df_rep.iloc[-1].get("MediaRemaining", 0)) * media_factor
                prints_done = max(0, (st.session_state.max_prints or 0) - last_val)
                
                cost_str = "N/A"
                cpr = printer_cfg.get("cost_per_roll_eur")
                if cpr and st.session_state.max_prints:
                     cost_str = f"{prints_done * (cpr / st.session_state.max_prints):.2f} EUR"

                pdf_bytes = generate_event_pdf(
                    df=df_rep,
                    printer_name=st.session_state.selected_printer,
                    stats=stats,
                    prints_since_reset=prints_done,
                    cost_info=cost_str
                )
                
                st.download_button(
                    "⬇️ PDF Herunterladen",
                    data=pdf_bytes,
                    file_name=f"report_{datetime.date.today()}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

        # --- TAB 3: GERÄTE (AQARA/DSR) ---
        with tab_devices:
            st.markdown("#### Gerätesteuerung")
            
            if not printer_has_aqara and not printer_has_dsr:
                st.info("Keine Geräte konfiguriert.")
            else:
                col_aq, col_ds = st.columns(2)
                
                with col_aq:
                    st.caption("Strom (Aqara)")
                    if printer_has_aqara and AQARA_ENABLED:
                        state = st.session_state.socket_state
                        c_on, c_off = render_toggle_card(
                            "Steckdose", "Strom", state,
                            "AN", "AUS", "?", "Zustand", "🟢", "⚪️", "⚠️", "Ein", "Aus", "bq_on", "bq_off"
                        )
                        target = True if c_on else (False if c_off else None)
                        if target is not None:
                            res = aqara_client.switch_socket(AQARA_SOCKET_DEVICE_ID, turn_on=target)
                            if res.get("code") == 0:
                                st.session_state.socket_state = "on" if target else "off"
                                st.rerun()
                    else:
                        st.write("Nicht verfügbar")

                with col_ds:
                    st.caption("Lockscreen (dsrBooth)")
                    if printer_has_dsr and DSR_ENABLED:
                        l_state = st.session_state.lockscreen_state
                        c_l, c_ul = render_toggle_card(
                            "Sperre", "Gäste-Modus", l_state,
                            "GESPERRT", "FREI", "?", "Modus", "🔒", "🔓", "⚠️", "Sperren", "Freigeben", "l_on", "l_off"
                        )
                        if c_l: 
                            send_dsr_command("lock_on")
                            st.session_state.lockscreen_state = "on"
                            st.rerun()
                        if c_ul:
                            send_dsr_command("lock_off")
                            st.session_state.lockscreen_state = "off"
                            st.rerun()
                    else:
                        st.write("Nicht verfügbar")

        # --- TAB 4: SYSTEM & TESTS ---
        with tab_notify:
            st.markdown("#### System & Tests")
            
            st.text_input("ntfy Topic", value=st.session_state.ntfy_topic or "-", disabled=True)
            if st.button("🔔 Test-Push senden", use_container_width=True):
                send_ntfy_push("Test", "Test OK", tags="tada")
                st.toast("Gesendet")
            
            st.write("")
            sim = st.selectbox("Status simulieren", ["Keine", "Fehler", "Papier leer"], label_visibility="collapsed")
            if st.button("Simulation starten", use_container_width=True) and sim != "Keine":
                tags = "rotating_light" if sim == "Fehler" else "warning"
                send_ntfy_push(f"Sim: {sim}", "Test-Nachricht", tags=tags)
                st.toast("Simuliert")


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

    if view_mode == "Alle Boxen":
        render_fleet_overview(PRINTERS)
        return

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
        st.error(f"Fehler: Keine sheet_id für {printer_name} gefunden.")
        st.stop()

    st.session_state.sheet_id = sheet_id
    st.session_state.ntfy_topic = ntfy_topic

    if st.session_state.selected_printer != printer_name:
        st.session_state.selected_printer = printer_name
        st.session_state.last_warn_status = None
        st.session_state.last_sound_status = None
        try:
            pkg = get_setting("package_size", printer_cfg["default_max_prints"])
            st.session_state.max_prints = int(pkg)
        except:
            st.session_state.max_prints = printer_cfg["default_max_prints"]

    if "ntfy_active" not in st.session_state:
        try: st.session_state.ntfy_active = str(get_setting("ntfy_active", str(NTFY_ACTIVE_DEFAULT))).lower() == "true"
        except: st.session_state.ntfy_active = NTFY_ACTIVE_DEFAULT

    if "event_mode" not in st.session_state:
        try: st.session_state.event_mode = get_setting("default_view", "admin") == "event"
        except: st.session_state.event_mode = False

    if "sound_enabled" not in st.session_state:
        st.session_state.sound_enabled = False

    event_mode = st.sidebar.toggle("Event-Ansicht", value=st.session_state.event_mode)
    sound_enabled = st.sidebar.toggle("Sound", value=st.session_state.sound_enabled)
    ntfy_active_ui = st.sidebar.toggle("Push Aktiv", value=st.session_state.ntfy_active)

    if event_mode != st.session_state.event_mode:
        st.session_state.event_mode = event_mode
        try: set_setting("default_view", "event" if event_mode else "admin")
        except: pass

    if ntfy_active_ui != st.session_state.ntfy_active:
        st.session_state.ntfy_active = ntfy_active_ui
        try: set_setting("ntfy_active", ntfy_active_ui)
        except: pass

    st.session_state.sound_enabled = sound_enabled

    # UI RENDERING
    st.title(f"{PAGE_ICON} {PAGE_TITLE}")
    view_event_mode = event_mode or not printer_has_admin

    if view_event_mode:
        show_live_status(media_factor, cost_per_roll, sound_enabled, event_mode=True)
        # Hilfe & Legende entfernt
        st.write("")
        st.link_button("☁️ Fotoshare Cloud", "https://fotoshare.co/admin/index", use_container_width=True)
    else:
        tab_live, tab_hist = st.tabs(["Live-Status", "Historie & Analyse"])
        with tab_live:
            show_live_status(media_factor, cost_per_roll, sound_enabled, event_mode=False)
            # Hilfe & Legende entfernt
            st.write("")
            st.link_button("☁️ Fotoshare Cloud", "https://fotoshare.co/admin/index", use_container_width=True)
        with tab_hist:
            show_history(media_factor, cost_per_roll)

        st.markdown("---")
        render_admin_panel(printer_cfg, warning_threshold)


if __name__ == "__main__":
    main()
