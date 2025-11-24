import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import requests
from streamlit_lottie import st_lottie
import pandas as pd
from datetime import datetime

# --- KONFIGURATION ---
SHEET_ID = "10uLjotNMT3AewBHdkuYyOudbbOCEuquDqGbwr2Wu7ig"
PAGE_TITLE = "Fotobox Drucker Status"
PAGE_ICON = "🖨️"

# --- NTFY EINSTELLUNGEN (Push Nachrichten) ---
NTFY_TOPIC = "fotobox_status_secret_4566"
NTFY_ACTIVE_DEFAULT = True
WARNING_THRESHOLD = 20  # Ab wie vielen Bildern Warnung?

# --- SEITEN KONFIGURATION ---
st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="centered")

# --- SESSION STATE ---
if "confirm_reset" not in st.session_state:
    st.session_state.confirm_reset = False
if "ntfy_active" not in st.session_state:
    st.session_state.ntfy_active = NTFY_ACTIVE_DEFAULT
if "last_warn_status" not in st.session_state:
    st.session_state.last_warn_status = None   # "error", "low_paper", "ok"
if "max_prints" not in st.session_state:
    st.session_state.max_prints = 400


# --- FUNKTION: Push Nachricht Senden ---
def send_ntfy_push(title, message, tags="warning", priority="default"):
    if not st.session_state.ntfy_active:
        return
    try:
        headers = {
            "Title": title.encode("utf-8"),
            "Tags": tags,
            "Priority": priority,
        }
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode(encoding="utf-8"),
            headers=headers,
            timeout=5,
        )
    except Exception as e:
        print(f"Push Fehler: {e}")


# --- FUNKTION: Lottie Laden ---
@st.cache_data(ttl=3600)
def load_lottieurl(url):
    try:
        r = requests.get(url, timeout=5)
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None


# Lotties (stabile URLs)
lottie_printing = load_lottieurl(
    "https://assets9.lottiefiles.com/packages/lf20_q5pk6p1k.json"   # Drucker / Loading
)
lottie_ready = load_lottieurl(
    "https://assets9.lottiefiles.com/packages/lf20_jbrw3hcz.json"   # Success / bereit
)
lottie_warning = load_lottieurl(
    "https://assets1.lottiefiles.com/packages/lf20_touohxv0.json"   # Warn-Dreieck
)
lottie_error = load_lottieurl(
    "https://assets7.lottiefiles.com/private_files/lf30_editor_e7qk3x0q.json"  # Error
)

# Fallbacks: wenn was nicht lädt, nimm etwas anderes damit nie „nichts“ da ist
if lottie_warning is None:
    lottie_warning = lottie_ready
if lottie_error is None:
    lottie_error = lottie_warning
if lottie_printing is None:
    lottie_printing = lottie_ready


# --- GOOGLE SHEETS HELPER ---
def get_worksheet():
    secrets = st.secrets["gcp_service_account"]
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(secrets, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    return sh.sheet1


@st.cache_data(ttl=0)
def get_data():
    try:
        worksheet = get_worksheet()
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        return df
    except Exception:
        return pd.DataFrame()


def clear_google_sheet():
    try:
        ws = get_worksheet()
        ws.batch_clear(["A2:Z10000"])
        st.cache_data.clear()
        st.toast("Log erfolgreich zurückgesetzt!", icon="♻️")
    except Exception as e:
        st.error(f"Fehler beim Reset: {e}")


# --- MAIN APP LOGIK ---
st.title(f"{PAGE_ICON} {PAGE_TITLE}")


@st.fragment(run_every=10)
def show_live_status():
    df = get_data()

    if not df.empty:
        try:
            last_entry = df.iloc[-1]

            # Wichtig: Spaltennamen exakt wie im Sheet:
            # Timestamp | Status | Paper_Status | Media_Remaining
            timestamp_str = str(last_entry.get("Timestamp", ""))

            try:
                last_update = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            except:
                last_update = None

            raw_status = str(last_entry.get("Status", "")).lower()
            # HIER der Fix: richtiger Spaltenname "Media_Remaining"
            media_remaining = int(last_entry.get("Media_Remaining", 0))
            current_max = st.session_state.max_prints

            prev_status = st.session_state.last_warn_status

            # --- ENTSCHEIDUNGSBAUM ---
            if (
                "error" in raw_status
                or "unknown" in raw_status
                or "stau" in raw_status
                or "failure" in raw_status
                or "fehler" in raw_status
            ):
                status_mode = "error"
                display_text = f"⚠️ STÖRUNG: {last_entry.get('Status')}"
                display_color = "red"
                current_lottie = lottie_error

                if prev_status != "error":
                    send_ntfy_push(
                        "🔴 KRITISCHER FEHLER",
                        f"Drucker: {last_entry.get('Status')}",
                        tags="rotating_light",
                        priority="high",
                    )
                st.session_state.last_warn_status = "error"

            elif media_remaining <= WARNING_THRESHOLD:
                status_mode = "low_paper"
                display_text = "Papier fast leer!"
                display_color = "orange"
                current_lottie = lottie_warning

                if prev_status == "error":
                    send_ntfy_push(
                        "✅ Störung behoben",
                        "Papierstörung behoben, Drucker läuft wieder.",
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
                status_mode = "printing"
                display_text = "Druckt gerade..."
                display_color = "blue"
                current_lottie = lottie_printing

                if prev_status == "error":
                    send_ntfy_push(
                        "✅ Störung behoben",
                        "Papierstörung behoben, Drucker druckt wieder.",
                        tags="white_check_mark",
                    )

                st.session_state.last_warn_status = "ok"

            else:
                status_mode = "ready"
                display_text = "Bereit"
                display_color = "green"
                current_lottie = lottie_ready

                if prev_status == "error":
                    send_ntfy_push(
                        "✅ Störung behoben",
                        "Papierstörung behoben, Drucker ist wieder bereit.",
                        tags="white_check_mark",
                    )

                st.session_state.last_warn_status = "ok"

            # --- ANZEIGE HEADER ---
            col1, col2 = st.columns([1, 2])
            with col1:
                if current_lottie:
                    st_lottie(current_lottie, height=180, key="status_anim_main")
                else:
                    st.markdown("## 🤖")

            with col2:
                st.markdown(
                    f"<h2 style='color:{display_color}; margin-top:0;'>{display_text}</h2>",
                    unsafe_allow_html=True,
                )
                st.caption(f"Letztes Signal: {timestamp_str}")

                if status_mode == "error":
                    st.error("Bitte Drucker prüfen (Störung aktiv).")
                else:
                    if prev_status == "error":
                        st.success("Störung behoben – Drucker läuft wieder.")

            # --- PAPIERSTATUS ---
            st.markdown("#### Papierstatus")

            # Restlaufzeit-Text
            if status_mode == "error":
                forecast_text = "Unbekannt (Störung)"
            else:
                if media_remaining > 0:
                    minutes_left = int(media_remaining * 1.5)
                    if minutes_left > 60:
                        hours = minutes_left // 60
                        mins = minutes_left % 60
                        forecast_text = f"ca. {hours} Std. {mins} Min."
                    else:
                        forecast_text = f"ca. {minutes_left} Min."
                else:
                    forecast_text = "0 Min."

            # Anzeige der verbleibenden Stück
            if status_mode == "error":
                remaining_text = "–"
            else:
                remaining_text = f"{media_remaining} Stk"

            m_col1, m_col2 = st.columns(2)
            m_col1.metric("Verbleibend", remaining_text, f"von {current_max}")
            m_col2.metric("Restlaufzeit (geschätzt)", forecast_text)

            # Fortschrittsbalken
            if status_mode == "error":
                progress_val = 0.0
                bar_color = "red"
            else:
                progress_val = max(0.0, min(1.0, media_remaining / current_max))
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

    else:
        st.info("System wartet auf Start...")
        st.caption("Noch keine Druckdaten empfangen.")


show_live_status()

st.markdown("---")

# --- ADMIN BEREICH ---
with st.expander("🛠️ Admin & Einstellungen", expanded=False):
    col_admin1, col_admin2 = st.columns(2)

    with col_admin1:
        st.write("### Externe Links")
        st.link_button(
            "🔗 Fotoshare Cloud",
            "https://fotoshare.co/admin/index",
            use_container_width=True,
        )

        st.write("### Benachrichtigungen")
        st.code(NTFY_TOPIC, language="text")

        st.session_state.ntfy_active = st.checkbox(
            "Push-Nachrichten aktiv", value=st.session_state.ntfy_active
        )
        if st.button("Test Push 🔔"):
            send_ntfy_push(
                "Test",
                f"Test erfolgreich! Paketgröße: {st.session_state.max_prints}",
                tags="tada",
            )
            st.toast("Test gesendet!")

    with col_admin2:
        st.write("### Neuer Auftrag")
        st.write("Welches Papier liegt ein?")
        new_package_size = st.radio(
            "Paketgröße:",
            [200, 400],
            horizontal=True,
            index=1 if st.session_state.max_prints == 400 else 0,
        )

        if not st.session_state.confirm_reset:
            if st.button(
                "Papierwechsel durchgeführt (Reset) 🔄", use_container_width=True
            ):
                st.session_state.confirm_reset = True
                st.session_state.temp_package_size = new_package_size
                st.rerun()
        else:
            st.warning(
                f"Log löschen & auf {st.session_state.temp_package_size}er Rolle setzen?"
            )
            col_yes, col_no = st.columns(2)
            if col_yes.button("✅ Ja", use_container_width=True):
                st.session_state.max_prints = st.session_state.temp_package_size
                clear_google_sheet()
                st.session_state.confirm_reset = False
                st.session_state.last_warn_status = None
                st.rerun()

            if col_no.button("❌ Nein", use_container_width=True):
                st.session_state.confirm_reset = False
                st.rerun()
