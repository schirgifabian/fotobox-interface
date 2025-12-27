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
import plotly.express as px

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
    render_fleet_overview,
    render_hero_card,
    render_link_card,
    render_card_header,
    inject_screensaver_css,
    render_screensaver_content
)

# --------------------------------------------------------------------
# GRUNDKONFIG
# --------------------------------------------------------------------
PAGE_TITLE = "Fotobox Drucker Status Testserver"
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
        "fotoshare_url": "https://fotoshare.co/account/login",
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
        "fotoshare_url": "https://weinkellerei.tirol/fame",
    },
}

# --------------------------------------------------------------------
# LOGIN (Unverändert)
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
    
    # --- NEU: Manager für den Rest des Skripts speichern ---
    st.session_state["cookie_manager_ref"] = cookie_manager
    # -------------------------------------------------------

    cookie_val = cookie_manager.get("auth_pin")

    if st.session_state.get("is_logged_in", False):
        return True

    if cookie_val is not None and str(cookie_val) == secret_pin:
        st.session_state["is_logged_in"] = True
        return True

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

# --------------------------------------------------------------------
# NTFY & DSR
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
    if not val: val = default
    return val

def send_ntfy_push(title: str, message: str, tags: str = "warning", priority: str = "default") -> None:
    if not st.session_state.get("ntfy_active", False):
        return
    topic = st.session_state.get("ntfy_topic")
    if not topic: return
    try:
        headers = {
            "Title": _sanitize_header_value(title, default="Status"),
            "Tags": _sanitize_header_value(tags, default="info"),
            "Priority": _sanitize_header_value(priority, default="default"),
        }
        requests.post(f"https://ntfy.sh/{topic}", data=message.encode("utf-8"), headers=headers, timeout=5)
    except Exception as e:
        st.error(f"ntfy Fehler: {e}")

def send_dsr_command(cmd: str) -> None:
    if not DSR_ENABLED or not DSR_CONTROL_TOPIC: return
    try:
        requests.post(f"https://ntfy.sh/{DSR_CONTROL_TOPIC}", data=cmd.encode("utf-8"), timeout=5)
    except Exception: pass

# --------------------------------------------------------------------
# AQARA
# --------------------------------------------------------------------
def init_aqara() -> Tuple[bool, Optional[AqaraClient], Optional[str], str]:
    try:
        if "aqara" not in st.secrets: return False, None, None, "4.1.85"
        aqara_cfg = st.secrets["aqara"]
        client = AqaraClient()
        return True, client, aqara_cfg["device_id"], aqara_cfg.get("resource_id", "4.1.85")
    except Exception as e:
        print(f"Aqara Init Fehler: {e}")
        return False, None, None, "4.1.85"

AQARA_ENABLED, aqara_client, AQARA_SOCKET_DEVICE_ID, AQARA_SOCKET_RESOURCE_ID = init_aqara()


# --------------------------------------------------------------------
# SESSION
# --------------------------------------------------------------------
def init_session_state():
    defaults = {
        "screensaver_mode": False,
        "confirm_reset": False,
        "last_warn_status": None,
        "last_sound_status": None,
        "max_prints": None,
        "selected_printer": None,
        "socket_state": "unknown",
        "socket_debug": None,
        "lockscreen_state": "off",
        "maintenance_mode": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v
            
# --------------------------------------------------------------------
# LIVE-STATUS VIEW
# --------------------------------------------------------------------
@st.fragment(run_every=10, show_spinner=False)
def show_live_status(media_factor: int, cost_per_roll: float, sound_enabled: bool, event_mode: bool, cloud_url: str = None) -> None:
    df = get_data(st.session_state.sheet_id, event_mode=event_mode)
    if df.empty:
        st.info("System wartet auf Start…")
        return

    try:
        last = df.iloc[-1]
        timestamp = str(last.get("Timestamp", ""))
        raw_status = str(last.get("Status", ""))
        try: media_remaining_raw = int(last.get("MediaRemaining", 0))
        except Exception: media_remaining_raw = 0
        media_remaining = media_remaining_raw * media_factor

        maint_active = st.session_state.get("maintenance_mode", False)
        
        status_mode, display_text, display_color, push, minutes_diff = evaluate_status(
            raw_status, media_remaining, timestamp
        )

        if push is not None:
            title, msg, tags = push
            send_ntfy_push(title, msg, tags=tags)

        maybe_play_sound(status_mode, sound_enabled)
        heartbeat_info = f" (vor {minutes_diff} Min)" if minutes_diff is not None else ""

        stats = compute_print_stats(df, window_min=30, media_factor=media_factor)
        prints_since_reset = max(0, (st.session_state.max_prints or 0) - media_remaining)
        
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
                forecast_str = humanize_minutes(minutes_left)
                end_time_str = f" (bis {end_time.strftime('%H:%M')})"
            elif media_remaining > 0:
                forecast_str = "Warte auf Drucke..."
            else:
                forecast_str = "0 Min."
        
        cost_txt = "–"
        if cost_per_roll and (st.session_state.max_prints or 0) > 0:
            try:
                c_print = cost_per_roll / st.session_state.max_prints
                cost_txt = f"{prints_since_reset * c_print:0.2f} €"
            except Exception: pass

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

        if status_mode == "error": st.error("Bitte Drucker und Papier prüfen (Störung aktiv).")
        elif status_mode == "stale": st.warning("Seit einigen Minuten keine Daten – Verbindung prüfen.")
            
        if cloud_url:
            st.write("") 
            render_link_card(url=cloud_url, title="Bilder Überblick", subtitle="Zur Galerie", icon="☁️")

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

    # --- NEU: PLOTLY CHART ---
    # Wir erstellen ein interaktives Liniendiagramm
    fig = px.line(
        df_hist, 
        y="RemainingPrints", 
        title="Papierverlauf (Interaktiv)",
        labels={"RemainingPrints": "Verbleibende Bilder", "index": "Zeitpunkt"},
        template="plotly_white"
    )
    
    # Styling: Blaue Linie, etwas dicker
    fig.update_traces(line_color='#3B82F6', line_width=3)
    
    # Layout: Hover-Effekt, Achsen formatieren
    fig.update_layout(
        hovermode="x unified",
        height=350,
        margin=dict(l=20, r=20, t=40, b=20),
        yaxis=dict(rangemode="tozero") # Y-Achse startet immer bei 0
    )
    
    st.plotly_chart(fig, use_container_width=True)
    # -------------------------

    stats = compute_print_stats(df, window_min=30, media_factor=media_factor)
    last_remaining = int(df_hist["RemainingPrints"].iloc[-1])
    prints_since_reset = max(0, (st.session_state.max_prints or 0) - last_remaining)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Log-Einträge", len(df_hist))
    c2.metric("Drucke seit Reset", prints_since_reset)
    c3.metric("Ø Drucke/Std (Total)", f"{stats['ppm_overall'] * 60:.1f}" if stats['ppm_overall'] else "–")
    c4.metric("Ø Drucke/Std (30 Min)", f"{stats['ppm_window'] * 60:.1f}" if stats['ppm_window'] else "–")

    st.markdown("#### Rohdaten (letzte 200 Zeilen)")
    st.dataframe(df.tail(200), use_container_width=True)


# --------------------------------------------------------------------
# ADMIN PANEL (DESIGN UPDATE)
# --------------------------------------------------------------------
def render_admin_panel(printer_cfg: Dict[str, Any], warning_threshold: int, printer_key: str) -> None:
    """
    Admin-Bereich mit Dashboard-Look (Cards statt Tabs für Inhalt).
    """
    printer_has_aqara = printer_cfg.get("has_aqara", False)
    printer_has_dsr = printer_cfg.get("has_dsr", False)

    st.write("")
    st.markdown("### 🛠️ Administration") 
    st.write("")

    # Tabs als Navigation oben behalten, aber Inhalte als "Cards" rendern
    tab_paper, tab_report, tab_devices, tab_notify = st.tabs([
        "🧻 Papier & Reset", 
        "📊 Report", 
        "🔌 Steuerung",
        "🔔 System & Tests"
    ])

    # ------------------------------------------------------------------
    # TAB 1: PAPIERWECHSEL CARD
    # ------------------------------------------------------------------
    with tab_paper:
        # Nutzung von st.container(border=True), der via CSS gestylt ist
        with st.container(border=True):
            render_card_header(
                icon="🧻", 
                title="Papierwechsel", 
                subtitle="Zähler zurücksetzen und Log leeren",
                color_class="blue"
            )
            
            st.write("") # Spacer

            c1, c2 = st.columns([1, 2])
            with c1:
                st.caption("Paketgröße wählen")
                size_options = [200, 400]
                try: current_size = int(st.session_state.max_prints or printer_cfg["default_max_prints"])
                except: current_size = printer_cfg["default_max_prints"]
                idx = 1 if current_size == 400 else 0
                
                size = st.radio(
                    "Paketgröße", size_options, horizontal=True, index=idx,
                    label_visibility="collapsed", key=f"tab_paper_size_{printer_key}"
                )
            
            with c2:
                st.caption("Notiz (optional)")
                reset_note = st.text_input(
                    "Notiz", key=f"reset_note_{printer_key}", label_visibility="collapsed",
                    placeholder="z.B. neue Rolle eingelegt"
                )

            st.write("")
            
            if not st.session_state.confirm_reset:
                if st.button("Reset durchführen", use_container_width=True, key=f"btn_init_reset_{printer_key}", type="primary"):
                    st.session_state.confirm_reset = True
                    st.session_state.temp_package_size = size
                    st.session_state.temp_reset_note = reset_note
                    st.rerun()
            else:
                st.info(f"Wirklich Log löschen und auf {st.session_state.get('temp_package_size')}er Rolle setzen?")
                cy, cn = st.columns(2)
                if cy.button("Ja, Reset ✅", use_container_width=True, key=f"btn_yes_{printer_key}", type="primary"):
                    st.session_state.max_prints = st.session_state.temp_package_size
                    try: set_setting("package_size", st.session_state.max_prints)
                    except: pass
                    clear_google_sheet()
                    log_reset_event(st.session_state.temp_package_size, st.session_state.temp_reset_note)
                    st.session_state.confirm_reset = False
                    st.session_state.last_warn_status = None
                    st.rerun()
                if cn.button("Abbrechen", use_container_width=True, key=f"btn_no_{printer_key}"):
                    st.session_state.confirm_reset = False
                    st.rerun()

    # ------------------------------------------------------------------
    # TAB 2: REPORT CARD
    # ------------------------------------------------------------------
    with tab_report:
        with st.container(border=True):
            render_card_header(
                icon="📄", 
                title="Event Report", 
                subtitle="PDF Zusammenfassung generieren",
                color_class="green"
            )
            st.write("")
            st.markdown(
                """<div style="font-size: 0.9rem; color: #64748B; margin-bottom: 16px;">
                Erstellt ein PDF mit Verbrauchskurve, Statistiken und den letzten Fehlermeldungen.
                </div>""", 
                unsafe_allow_html=True
            )

            if st.button("PDF Bericht erstellen", use_container_width=True, key=f"btn_pdf_{printer_key}"):
                df_rep = get_data_admin(st.session_state.sheet_id)
                media_factor = printer_cfg.get("media_factor", 1)
                stats = compute_print_stats(df_rep, media_factor=media_factor)
                
                last_val = 0
                if not df_rep.empty:
                    try: last_val = int(df_rep.iloc[-1].get("MediaRemaining", 0)) * media_factor
                    except: pass
                prints_done = max(0, (st.session_state.max_prints or 0) - last_val)
                
                cost_str = "N/A"
                cpr = printer_cfg.get("cost_per_roll_eur")
                if cpr and st.session_state.max_prints:
                    c_used = prints_done * (cpr / st.session_state.max_prints)
                    cost_str = f"{c_used:.2f} EUR"

                pdf_bytes = generate_event_pdf(
                    df=df_rep, printer_name=st.session_state.selected_printer,
                    stats=stats, prints_since_reset=prints_done,
                    cost_info=cost_str, media_factor=media_factor
                )
                
                st.download_button(
                    label="⬇️ PDF jetzt herunterladen",
                    data=pdf_bytes,
                    file_name=f"report_{datetime.date.today()}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"dl_btn_{printer_key}"
                )

    # ------------------------------------------------------------------
    # TAB 3: DEVICES CARDS
    # ------------------------------------------------------------------
    with tab_devices:
        if not printer_has_aqara and not printer_has_dsr:
            st.info("Keine Geräte konfiguriert.")
        else:
            col_aqara, col_dsr = st.columns(2)

            # --- Aqara Card ---
            with col_aqara:
                with st.container(border=True):
                    status_text = "N/A"
                    status_color = "slate"
                    
                    if printer_has_aqara and AQARA_ENABLED:
                        if st.session_state.socket_state == "on":
                            status_text = "AN"
                            status_color = "green"
                        elif st.session_state.socket_state == "off":
                            status_text = "AUS"
                            status_color = "slate"
                        else:
                            # Try fetch current state
                            try:
                                curr, _ = aqara_client.get_socket_state(AQARA_SOCKET_DEVICE_ID, AQARA_SOCKET_RESOURCE_ID)
                                st.session_state.socket_state = curr
                                if curr == "on": 
                                    status_text = "AN"
                                    status_color = "green"
                                elif curr == "off": 
                                    status_text = "AUS"
                                    status_color = "slate"
                            except: pass

                    render_card_header(
                        icon="⚡", 
                        title="Strom", 
                        subtitle=f"Status: {status_text}",
                        color_class=status_color
                    )
                    
                    if printer_has_aqara and AQARA_ENABLED:
                        ca, cb = st.columns(2)
                        if ca.button("An", key=f"aq_on_{printer_key}", use_container_width=True):
                            aqara_client.switch_socket(AQARA_SOCKET_DEVICE_ID, True, AQARA_SOCKET_RESOURCE_ID)
                            st.session_state.socket_state = "on"
                            st.rerun()
                        if cb.button("Aus", key=f"aq_off_{printer_key}", use_container_width=True):
                            aqara_client.switch_socket(AQARA_SOCKET_DEVICE_ID, False, AQARA_SOCKET_RESOURCE_ID)
                            st.session_state.socket_state = "off"
                            st.rerun()
                    else:
                        st.caption("Nicht verfügbar")

            # --- DSR Card ---
            with col_dsr:
                with st.container(border=True):
                    lock_state = st.session_state.get("lockscreen_state", "off")
                    l_color = "orange" if lock_state == "on" else "slate"
                    l_text = "GESPERRT" if lock_state == "on" else "FREI"

                    render_card_header(
                        icon="🔒", 
                        title="Screen", 
                        subtitle=f"Modus: {l_text}",
                        color_class=l_color
                    )

                    if printer_has_dsr and DSR_ENABLED:
                        la, lb = st.columns(2)
                        if la.button("Sperren", key=f"dsr_l_{printer_key}", use_container_width=True):
                            send_dsr_command("lock_on")
                            st.session_state.lockscreen_state = "on"
                            st.rerun()
                        if lb.button("Freigeben", key=f"dsr_u_{printer_key}", use_container_width=True):
                            send_dsr_command("lock_off")
                            st.session_state.lockscreen_state = "off"
                            st.rerun()
                    else:
                        st.caption("Nicht verfügbar")
                        
            st.write("")
            with st.container(border=True):
                is_maint = st.session_state.get("maintenance_mode", False)
            
                # Header rendern
                render_card_header(
                    icon="🚚", 
                    title="Box im Lager", 
                    subtitle="Transport & Lagerung",
                    color_class="slate" if is_maint else "green" # Grau wenn aktiv, sonst grün (oder umgekehrt, wie du magst)
                )
            
                c_text, c_toggle = st.columns([3, 1])
                with c_text:
                    st.caption("Unterdrückt 'Keine Verbindung' Warnungen und Push-Nachrichten.")
            
                with c_toggle:
                    # Toggle
                    new_maint = st.toggle("Aktiv", value=is_maint, key=f"toggle_maint_{printer_key}")
                
                    if new_maint != is_maint:
                        st.session_state.maintenance_mode = new_maint
                        set_setting("maintenance_mode", new_maint)
                        st.rerun()

    # ------------------------------------------------------------------
    # TAB 4: NOTIFY CARD
    # ------------------------------------------------------------------
    with tab_notify:
        with st.container(border=True):
            render_card_header(
                icon="🔔", 
                title="System Tests", 
                subtitle="Push & Simulation",
                color_class="orange"
            )
            st.write("")
            
            # Topic Info
            st.caption("Konfiguriertes Topic")
            st.code(st.session_state.ntfy_topic or "Kein Topic", language="text")

            st.write("---")
            
            c_test, c_sim = st.columns(2)
            with c_test:
                if st.button("🔔 Ping senden", use_container_width=True, key=f"btn_test_push_{printer_key}"):
                    send_ntfy_push("Test", "Test erfolgreich", tags="tada")
                    st.toast("Ping gesendet")
            
            with c_sim:
                sim_opt = st.selectbox(
                    "Simulieren", 
                    ["Fehler", "Low Paper", "Stale"], 
                    key=f"sim_{printer_key}", 
                    label_visibility="collapsed"
                )
                if st.button("Auslösen", use_container_width=True, key=f"btn_sim_trig_{printer_key}"):
                    map_sim = {
                        "Fehler": ("error", "🔴 Fehler (Sim)", "rotating_light"),
                        "Low Paper": ("low_paper", "⚠️ Papier (Sim)", "warning"),
                        "Stale": ("stale", "⚠️ Stale (Sim)", "hourglass")
                    }
                    mode, title, tag = map_sim[sim_opt]
                    send_ntfy_push(title, "Simulation aktiv", tags=tag)
                    maybe_play_sound(mode, st.session_state.sound_enabled)
                    st.toast(f"Simulation {mode} gesendet")


# --------------------------------------------------------------------
# Screensaver
# --------------------------------------------------------------------


@st.fragment(run_every=10, show_spinner=False)
def run_screensaver_loop(media_factor: int):
    # Daten holen
    df = get_data(st.session_state.sheet_id, event_mode=True)
    
    if df.empty:
        st.warning("Warte auf Daten...")
        return

    try:
        last = df.iloc[-1]
        full_timestamp = str(last.get("Timestamp", "")) # Voller Zeitstempel für die Logik
        display_timestamp = full_timestamp[-8:]         # Nur Uhrzeit für die Anzeige
        raw_status = str(last.get("Status", ""))
        
        try: media_remaining = int(last.get("MediaRemaining", 0)) * media_factor
        except: media_remaining = 0
        
        # Hier full_timestamp übergeben!
        status_mode, display_text, display_color, _, _ = evaluate_status(
            raw_status, media_remaining, full_timestamp
        )
        
        # HIER NUR NOCH CONTENT RENDERN, KEIN CSS MEHR
        render_screensaver_content(
            status_mode=status_mode,
            media_remaining=media_remaining,
            display_text=display_text,
            display_color=display_color,
            timestamp=display_timestamp # Hier die gekürzte Version nutzen
        )
        
        # Der Button wird nun via CSS am unteren Rand fixiert
        if st.button("Beenden", key="btn_exit_saver"):
            st.session_state.screensaver_mode = False
            st.rerun()

    except Exception as e:
        # Im Screensaver Fehler lieber dezent anzeigen oder ignorieren
        print(f"Screensaver Error: {e}")


# --------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------
def main():
    st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="centered")
    
    # 1. CSS laden
    inject_custom_css()
    
    init_session_state()
    check_login()

    # --- SCREENSAVER CHECK ---
    if st.session_state.screensaver_mode:
        inject_screensaver_css()
        printer_name = st.session_state.get("selected_printer")
        if not printer_name: 
            printer_name = list(PRINTERS.keys())[0]
        printer_cfg = PRINTERS.get(printer_name, {})
        media_factor = printer_cfg.get("media_factor", 1)
        run_screensaver_loop(media_factor)
        return
    # -------------------------
    
    # --- SIDEBAR TEIL 1: NAVIGATION ---
    with st.sidebar:
        # HEADER
        st.markdown("### ⚙️ Control Panel")
        
        # 1. USER PROFILE
        with st.container(border=True):
            st.markdown("""
                <div class="user-profile-card">
                    <div class="user-avatar">A</div>
                    <div class="user-info">
                        <span class="user-name">Admin User</span>
                        <span class="user-role">Administrator</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            st.write("") 
            if st.button("Ausloggen", key="sidebar_logout", use_container_width=True):
                if "cookie_manager_ref" in st.session_state:
                    st.session_state["cookie_manager_ref"].delete("auth_pin")
                st.session_state["is_logged_in"] = False
                time.sleep(0.5) 
                st.rerun()

        # 2. NAVIGATION & AUSWAHL
        with st.container(border=True):
            st.markdown("#### Navigation")
            view_mode = st.radio(
                "Ansicht", 
                ["Einzelne Fotobox", "Alle Boxen"],
                label_visibility="collapsed"
            )

            # Dropdown nur zeigen, wenn nötig
            if view_mode != "Alle Boxen":
                st.write("") 
                st.markdown("#### Aktives Gerät")
                printer_name = st.selectbox(
                    "Fotobox auswählen", 
                    list(PRINTERS.keys()), 
                    label_visibility="collapsed"
                )
            else:
                printer_name = None

    # --- LOGIK WEICHE ---
    
    # FALL 1: FLEET OVERVIEW (Alle Boxen)
    # Wenn wir hier rein gehen, beenden wir die Funktion danach mit 'return'.
    # Das spart uns Einrückungs-Probleme für den Rest.
    if view_mode == "Alle Boxen":
        st.title(f"{PAGE_ICON} {PAGE_TITLE}")
        render_fleet_overview(PRINTERS)
        return 

    # --- FALL 2: EINZELANSICHT ---
    # Ab hier läuft der Code für die Einzelansicht weiter.
    
    printer_cfg = PRINTERS[printer_name]
    printer_key = printer_cfg["key"]
    media_factor = printer_cfg.get("media_factor", 2)
    cost_per_roll = printer_cfg.get("cost_per_roll_eur")
    warning_threshold = printer_cfg.get("warning_threshold", 20)
    printer_has_admin = printer_cfg.get("has_admin", True)
    fotoshare_url = printer_cfg.get("fotoshare_url")
    
    printers_secrets = st.secrets.get("printers", {})
    printer_secret = printers_secrets.get(printer_key, {})
    sheet_id = printer_secret.get("sheet_id")
    ntfy_topic = printer_secret.get("ntfy_topic")

    if not sheet_id:
        st.error(f"Keine 'sheet_id' für '{printer_name}' gefunden.")
        st.stop()

    st.session_state.sheet_id = sheet_id
    st.session_state.ntfy_topic = ntfy_topic
    
    # Reset Logic bei Druckerwechsel
    if st.session_state.selected_printer != printer_name:
        st.session_state.selected_printer = printer_name
        st.session_state.confirm_reset = False
        st.session_state.socket_state = "unknown"
        st.session_state.last_warn_status = None
        st.session_state.last_sound_status = None
        try: st.session_state.max_prints = int(get_setting("package_size", printer_cfg["default_max_prints"]))
        except: st.session_state.max_prints = printer_cfg["default_max_prints"]
        try: st.session_state.maintenance_mode = (str(get_setting("maintenance_mode", "False")).lower() == "true")
        except: st.session_state.maintenance_mode = False

    # --- SIDEBAR TEIL 2: SETTINGS ---
    # Diese Boxen zeigen wir nur in der Einzelansicht an
    with st.sidebar:
        with st.container(border=True):
            st.markdown("#### Einstellungen")
            
            # Init Session Vars
            if "ntfy_active" not in st.session_state:
                try: st.session_state.ntfy_active = str(get_setting("ntfy_active", str(NTFY_ACTIVE_DEFAULT))).lower() == "true"
                except: st.session_state.ntfy_active = NTFY_ACTIVE_DEFAULT
            if "event_mode" not in st.session_state:
                try: st.session_state.event_mode = get_setting("default_view", "admin") == "event"
                except: st.session_state.event_mode = False
            if "sound_enabled" not in st.session_state: st.session_state.sound_enabled = False

            # UI Layout (Schön ausgerichtet)
            c_txt, c_tog = st.columns([3, 1])
            with c_txt: st.markdown('<div class="settings-row">Event-Ansicht</div>', unsafe_allow_html=True)
            with c_tog: event_mode = st.toggle("Event", value=st.session_state.event_mode, label_visibility="collapsed")
            
            c_txt, c_tog = st.columns([3, 1])
            with c_txt: st.markdown('<div class="settings-row">Sound Effekte</div>', unsafe_allow_html=True)
            with c_tog: sound_enabled = st.toggle("Sound", value=st.session_state.sound_enabled, label_visibility="collapsed")

            c_txt, c_tog = st.columns([3, 1])
            with c_txt: st.markdown('<div class="settings-row">Push Nachrichten</div>', unsafe_allow_html=True)
            with c_tog: ntfy_active_ui = st.toggle("Push", value=st.session_state.ntfy_active, label_visibility="collapsed")

            # Logic Update & Save
            if event_mode != st.session_state.event_mode:
                st.session_state.event_mode = event_mode
                try: set_setting("default_view", "event" if event_mode else "admin")
                except: pass
            if ntfy_active_ui != st.session_state.ntfy_active:
                st.session_state.ntfy_active = ntfy_active_ui
                try: set_setting("ntfy_active", ntfy_active_ui)
                except: pass
            st.session_state.sound_enabled = sound_enabled

        # Zen Mode Button
        with st.container(border=True):
             c1, c2 = st.columns([1, 4])
             with c1: st.write("🖥️")
             with c2:
                 if st.button("Zen Mode starten", key="zen_start", use_container_width=True):
                    st.session_state.screensaver_mode = True
                    st.rerun()

    # --- HAUPTBEREICH RENDERN ---
    st.title(f"{PAGE_ICON} {PAGE_TITLE}")
    
    view_event_mode = event_mode or not printer_has_admin

    if view_event_mode:
        show_live_status(media_factor, cost_per_roll, sound_enabled, event_mode=True, cloud_url=fotoshare_url)
    else:
        tab_live, tab_hist = st.tabs(["Live-Status", "Historie & Analyse"])
        with tab_live:
            show_live_status(media_factor, cost_per_roll, sound_enabled, event_mode=False, cloud_url=fotoshare_url)
        with tab_hist:
            show_history(media_factor, cost_per_roll)
        
        render_admin_panel(printer_cfg, warning_threshold, printer_key)

if __name__ == "__main__":
    main()
