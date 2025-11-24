import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import requests
import pandas as pd
from datetime import datetime

# --- KONFIGURATION ---
SHEET_ID = "10uLjotNMT3AewBHdkuYyOudbbOCEuquDqGbwr2Wu7ig"
PAGE_TITLE = "Fotobox Drucker Status"
PAGE_ICON = "🖨️"

# --- NTFY EINSTELLUNGEN ---
NTFY_TOPIC = "fotobox_status_secret_4566"
NTFY_ACTIVE_DEFAULT = True
WARNING_THRESHOLD = 20  # Ab wie vielen Bildern Warnung?

# --- SEITEN LAYOUT ---
st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="centered")

# --- SESSION STATE ---
if "confirm_reset" not in st.session_state:
    st.session_state.confirm_reset = False
if "ntfy_active" not in st.session_state:
    st.session_state.ntfy_active = NTFY_ACTIVE_DEFAULT
if "last_warn_status" not in st.session_state:
    st.session_state.last_warn_status = None  # "error", "low_paper", "ok"
if "max_prints" not in st.session_state:
    st.session_state.max_prints = 400

# --- PUSH ---
def send_ntfy_push(title, message, tags="warning", priority="default"):
    if not st.session_state.ntfy_active:
        return
    try:
        headers = {"Title": title.encode("utf-8"), "Tags": tags, "Priority": priority}
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers=headers,
            timeout=5,
        )
    except Exception:
        pass


# --- GOOGLE SHEETS ---
def get_worksheet():
    secrets = st.secrets["gcp_service_account"]
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(secrets, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID).sheet1


@st.cache_data(ttl=0)
def get_data():
    try:
        data = get_worksheet().get_all_records()
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()


def clear_google_sheet():
    try:
        ws = get_worksheet()
        ws.batch_clear(["A2:Z10000"])
        st.cache_data.clear()
        st.toast("Log erfolgreich zurückgesetzt!", icon="♻️")
    except Exception:
        st.error("Fehler beim Reset")


# --- UI START ---
st.title(f"{PAGE_ICON} {PAGE_TITLE}")


@st.fragment(run_every=10)
def show_live_status():
    df = get_data()

    if df.empty:
        st.info("System wartet auf Start…")
        st.caption("Noch keine Druckdaten empfangen.")
        return

    try:
        last = df.iloc[-1]

        # Spalten im Sheet: Timestamp | Status | Paper_Status | Media_Remaining
        timestamp       = str(last.get("Timestamp", ""))
        raw_status      = str(last.get("Status", "")).lower()
        media_remaining = int(last.get("Media_Remaining", 0))

        prev_status = st.session_state.last_warn_status

        # --- STATUS ERMITTELN ---
        if any(w in raw_status for w in ["error", "failure", "fehler", "stau", "unknown"]):
            status_mode   = "error"
            display_text  = f"⚠️ STÖRUNG: {last.get('Status')}"
            display_color = "red"

            if prev_status != "error":
                send_ntfy_push(
                    "🔴 Fehler",
                    f"Druckerfehler: {last.get('Status')}",
                    tags="rotating_light",
                    priority="high",
                )
            st.session_state.last_warn_status = "error"

        elif media_remaining <= WARNING_THRESHOLD:
            status_mode   = "low_paper"
            display_text  = "⚠️ Papier fast leer!"
            display_color = "orange"

            if prev_status == "error":
                send_ntfy_push(
                    "✅ Störung behoben",
                    "Drucker läuft wieder.",
                    tags="white_check_mark",
                )
            if prev_status != "low_paper":
                send_ntfy_push(
                    "⚠️ Papierwarnung",
                    f"Noch {media_remaining} Bilder!",
                    tags="warning",
                )
            st.session_state.last_warn_status = "low_paper"

        elif "printing" in raw_status or "processing" in raw_status:
            status_mode   = "printing"
            display_text  = "🖨️ Druckt gerade…"
            display_color = "blue"

            if prev_status == "error":
                send_ntfy_push(
                    "✅ Störung behoben",
                    "Drucker druckt wieder.",
                    tags="white_check_mark",
                )
            st.session_state.last_warn_status = "ok"

        else:
            status_mode   = "ready"
            display_text  = "✅ Bereit"
            display_color = "green"

            if prev_status == "error":
                send_ntfy_push(
                    "✅ Störung behoben",
                    "Drucker ist wieder bereit.",
                    tags="white_check_mark",
                )
            st.session_state.last_warn_status = "ok"

        # --- HEADER (nur Text + Icon im Text) ---
        st.markdown(
            f"<h2 style='color:{display_color}; margin-top:0; text-align:center;'>{display_text}</h2>",
            unsafe_allow_html=True,
        )
        st.caption(f"Letztes Signal: {timestamp}")

        if status_mode == "error":
            st.error("Bitte Drucker prüfen (Störung aktiv).")

        # --- PAPIERSTATUS ---
        st.markdown("#### Papierstatus")

        if status_mode == "error":
            remaining_text = "–"
            forecast = "Unbekannt (Störung)"
        else:
            remaining_text = f"{media_remaining} Stk"
            if media_remaining > 0:
                m = int(media_remaining * 1.5)
                if m < 60:
                    forecast = f"{m} Min."
                else:
                    forecast = f"{m//60} Std. {m%60} Min."
            else:
                forecast = "0 Min."

        c1, c2 = st.columns(2)
        c1.metric("Verbleibend", remaining_text, f"von {st.session_state.max_prints}")
        c2.metric("Restlaufzeit (geschätzt)", forecast)

        # Fortschrittsbalken
        if status_mode == "error":
            progress_val = 0.0
            bar_color = "red"
        else:
            progress_val = max(0.0, min(1.0, media_remaining / st.session_state.max_prints))
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


show_live_status()

st.markdown("---")

# --- ADMIN ---
with st.expander("🛠️ Admin & Einstellungen"):
    c1, c2 = st.columns(2)

    with c1:
        st.write("### Externe Links")
        st.link_button(
            "🔗 Fotoshare Cloud",
            "https://fotoshare.co/admin/index",
            use_container_width=True,
        )

        st.write("### Benachrichtigungen")
        st.code(NTFY_TOPIC)
        st.session_state.ntfy_active = st.checkbox(
            "Push-Nachrichten aktiv",
            st.session_state.ntfy_active,
        )
        if st.button("Test Push 🔔"):
            send_ntfy_push("Test", "Test erfolgreich", tags="tada")
            st.toast("Test gesendet!")

    with c2:
        st.write("### Neuer Auftrag")
        st.write("Welches Papier liegt ein?")
        size = st.radio(
            "Paketgröße",
            [200, 400],
            horizontal=True,
            index=1 if st.session_state.max_prints == 400 else 0,
        )

        if not st.session_state.confirm_reset:
            if st.button("Papierwechsel durchgeführt (Reset) 🔄", use_container_width=True):
                st.session_state.confirm_reset = True
                st.session_state.temp_package_size = size
                st.rerun()
        else:
            st.warning(f"Log löschen & {st.session_state.temp_package_size}-Rolle setzen?")
            y, n = st.columns(2)
            if y.button("✅ Ja", use_container_width=True):
                st.session_state.max_prints = st.session_state.temp_package_size
                clear_google_sheet()
                st.session_state.confirm_reset = False
                st.session_state.last_warn_status = None
                st.rerun()
            if n.button("❌ Nein", use_container_width=True):
                st.session_state.confirm_reset = False
                st.rerun()
