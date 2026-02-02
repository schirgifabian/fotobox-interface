# status_logic.py

import time
import datetime
import pandas as pd
import pytz
import streamlit as st

# Lokale Zeitzone für Heartbeat
LOCAL_TZ = pytz.timezone("Europe/Vienna")

# nach X Minuten ohne Daten -> stale
HEARTBEAT_WARN_MINUTES = 60

# Sound für Warnungen
ALERT_SOUND_URL = "https://actions.google.com/sounds/v1/alarms/medium_severity_alert.ogg"


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
    Der Rohwert vom Drucker wird mit media_factor multipliziert.
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


def evaluate_status(raw_status: str, media_remaining: int, timestamp: str, maintenance_active: bool = False, warning_threshold: int = 20):
    """
    Leitet aus Roh-Status + Papierstand den UI-Status ab
    und entscheidet, ob ein Push gesendet werden soll.
    Parameter maintenance_active unterdrückt Stale-Warnungen.
    Parameter warning_threshold bestimmt, wann 'Wenig Papier' ausgelöst wird.
    """
    raw_status_l = (raw_status or "").lower().strip()

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

    # 0) Spezialfall: Drucker offline / unbekannt (-1)
    # WICHTIG: Das muss vor allen anderen Checks stehen!
    if media_remaining < 0:
        status_mode = "offline"
        display_text = "🔌 Drucker offline (-1)"
        display_color = "slate"  # "slate" macht es grau, "red" würde es rot machen

    
    # 1) Harte Fehler (haben Vorrang, auch im Wartungsmodus)
    elif any(k in raw_status_l for k in hard_errors):
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

    # 4) Papier fast leer (Nutzt jetzt den Threshold!)
    elif media_remaining <= warning_threshold:
        status_mode = "low_paper"
        display_text = f"⚠️ Papier fast leer (<{warning_threshold})!"
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

    # HEARTBEAT CHECK
    minutes_diff = None
    ts_parsed = pd.to_datetime(timestamp, errors="coerce")

    if pd.notna(ts_parsed):
        if ts_parsed.tzinfo is None:
            ts_parsed = LOCAL_TZ.localize(ts_parsed)
        else:
            ts_parsed = ts_parsed.astimezone(LOCAL_TZ)

        now_local = datetime.datetime.now(LOCAL_TZ)
        delta = now_local - ts_parsed
        minutes_diff = int(delta.total_seconds() // 60)

        # Wenn zu lange keine Daten und KEIN Fehler vorliegt
        if minutes_diff >= HEARTBEAT_WARN_MINUTES and status_mode not in ["error"]:
            if maintenance_active:
                status_mode = "maintenance"
                display_text = "Box im Lager / Wartung"
                display_color = "slate"
            else:
                status_mode = "stale"
                display_text = "⚠️ Keine aktuellen Daten"
                display_color = "orange"

    # PUSH LOGIK VORBEREITUNG (Wird von app.py ignoriert, aber für Rückgabewerte wichtig)
    critical_states = ["error", "cover_open", "low_paper", "stale"]
    push = None

    prev_sig = st.session_state.get("last_warn_signature")
    prev_ts = st.session_state.get("last_warn_time")

    current_sig = {
        "status_mode": status_mode,
        "raw_status": raw_status_l,
        "media_remaining": media_remaining,
    }

    now_ts = time.time()
    COOLDOWN_MINUTES = 30
    cooldown_seconds = COOLDOWN_MINUTES * 60

    if status_mode in critical_states:
        sig_changed = prev_sig != current_sig
        cooldown_over = prev_ts is None or (now_ts - prev_ts) > cooldown_seconds

        if sig_changed or cooldown_over:
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
            if status_mode in title_map:
                push = (title_map[status_mode], msg_map[status_mode], "warning")

            st.session_state.last_warn_signature = current_sig
            st.session_state.last_warn_time = now_ts
    else:
        if prev_sig is not None and prev_sig.get("status_mode") == "error":
            push = ("✅ Störung behoben", "Drucker läuft wieder.", "white_check_mark")
        
        st.session_state.last_warn_signature = None
        st.session_state.last_warn_time = None

    st.session_state.last_warn_status = status_mode

    return status_mode, display_text, display_color, push, minutes_diff


def maybe_play_sound(status_mode: str, sound_enabled: bool):
    """
    Spielt bei kritischen Zuständen einen kurzen Ton ab (HTML audio-Element).
    """
    if not sound_enabled or not ALERT_SOUND_URL:
        return

    prev = st.session_state.get("last_sound_status")
    critical_states_with_sound = ["error", "cover_open", "low_paper"]

    if status_mode in critical_states_with_sound and prev != status_mode:
        st.session_state["last_sound_status"] = status_mode
        st.markdown(
            f"""
            <audio autoplay>
                <source src="{ALERT_SOUND_URL}" type="audio/ogg">
            </audio>
            """,
            unsafe_allow_html=True,
        )
    elif status_mode not in critical_states_with_sound and prev is not None:
        st.session_state["last_sound_status"] = None
