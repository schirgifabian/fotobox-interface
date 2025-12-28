# sheets_helpers.py

import datetime
import pandas as pd
import gspread
import streamlit as st
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound
import concurrent.futures


@st.cache_resource
def get_gspread_client():
    """
    gspread-Client nur einmal pro Session erzeugen.
    """
    secrets = st.secrets["gcp_service_account"]
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(secrets, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc


@st.cache_resource
def get_spreadsheet(sheet_id: str):
    """
    Spreadsheet-Objekt cachen – verhindert wiederholte open_by_key()-Calls.
    """
    gc = get_gspread_client()
    return gc.open_by_key(sheet_id)


def get_main_worksheet():
    """
    Main-Worksheet (sheet1) für das in session_state gesetzte sheet_id.
    """
    sheet_id_local = st.session_state.get("sheet_id")
    if not sheet_id_local:
        raise RuntimeError("sheet_id ist nicht im Session State gesetzt.")
    return get_spreadsheet(sheet_id_local).sheet1

def get_settings_ws(sheet_id: str):
    """
    Settings-Worksheet holen. Falls es nicht existiert und wir nicht schreiben dürfen,
    geben wir None zurück oder fangen den Fehler ab.
    """
    sh = get_spreadsheet(sheet_id)
    try:
        return sh.worksheet("Settings")
    except WorksheetNotFound:
        try:
            # Versuche das Blatt anzulegen
            ws = sh.add_worksheet(title="Settings", rows=100, cols=3)
            ws.append_row(["Key", "Value", "UpdatedAt"])
            return ws
        except Exception as e:
            # Wenn wir keine Schreibrechte haben (APIError 403), Fehler loggen, aber nicht crashen
            print(f"Konnte Settings-Sheet nicht erstellen (Rechte fehlen?): {e}")
            # Wir geben ein Dummy-Objekt oder None zurück, damit der Rest nicht crasht
            # (Das erfordert Anpassungen in load_settings, siehe unten)
            raise e

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
        ws = get_spreadsheet(sheet_id).sheet1
        return pd.DataFrame(ws.get_all_records())
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=10)  # 30 Sekunden Cache für Event-Ansicht
def get_data_event(sheet_id: str):
    try:
        ws = get_spreadsheet(sheet_id).sheet1
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
    """
    Löscht die Log-Daten (A2:Z10000) im aktuellen Sheet.
    """
    try:
        ws = get_main_worksheet()
        ws.batch_clear(["A2:Z10000"])
        get_data_admin.clear()
        get_data_event.clear()
        st.toast("Log erfolgreich zurückgesetzt!", icon="♻️")
    except Exception as e:
        st.error(f"Fehler beim Reset: {e}")


def log_reset_event(package_size: int, note: str = ""):
    """
    Loggt Papierwechsel / Reset in einem Meta-Sheet.
    """
    try:
        sheet_id_local = st.session_state.get("sheet_id")
        if not sheet_id_local:
            return
        sh = get_spreadsheet(sheet_id_local)
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

def fetch_single_status(sheet_id: str, printer_key: str, media_factor: int):
    """
    Hilfsfunktion für den Thread-Worker: Lädt Daten für EINE Box
    und gibt ein kleines Status-Dict zurück.
    """
    if not sheet_id:
        return printer_key, None

    try:
        # Hier nutzen wir die gecachte Funktion get_data_event
        df = get_data_event(sheet_id)
        if df.empty:
            return printer_key, None
            
        last = df.iloc[-1]
        
        # Daten extrahieren
        raw_status = str(last.get("Status", "")).lower()
        timestamp = str(last.get("Timestamp", ""))[-8:] # Nur Uhrzeit
        
        try:
            media_val = int(last.get("MediaRemaining", 0)) * media_factor
        except:
            media_val = 0
            
        # Status Logik vereinfacht für Übersicht
        if any(x in raw_status for x in ["error", "jam", "end", "fehlt"]):
            state = "error"
        elif "printing" in raw_status:
            state = "printing"
        else:
            state = "ready"
            
        return printer_key, {
            "state": state,
            "media_str": f"{media_val} Bilder",
            "timestamp": timestamp,
            "raw_status": raw_status
        }
    except Exception as e:
        # Im Fehlerfall nicht abstürzen, sondern None zurückgeben
        return printer_key, None

def get_fleet_data_parallel(printers_config: dict, secrets_printers: dict) -> dict:
    """
    Lädt alle Fotobox-Statuswerte PARALLEL statt nacheinander.
    """
    results = {}
    
    # ThreadPoolExecutor erstellt einen Pool von Worker-Threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_printer = {}
        
        for name, cfg in printers_config.items():
            key = cfg["key"]
            # Sheet ID aus Secrets holen
            s_id = secrets_printers.get(key, {}).get("sheet_id")
            media_factor = cfg.get("media_factor", 1)
            
            # Aufgabe in den Pool werfen (startet sofort im Hintergrund)
            future = executor.submit(fetch_single_status, s_id, name, media_factor)
            future_to_printer[future] = name

        # Warten bis alle fertig sind
        for future in concurrent.futures.as_completed(future_to_printer):
            printer_name = future_to_printer[future]
            try:
                # Ergebnis abholen
                key_check, data = future.result()
                results[printer_name] = data
            except Exception:
                results[printer_name] = None
                
    return results
