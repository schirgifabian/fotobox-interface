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
            # Wenn wir keine Schreibrechte haben (APIError 403), Fehler loggen
            print(f"Konnte Settings-Sheet nicht erstellen (Rechte fehlen?): {e}")
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


@st.cache_data(ttl=600)  # 10 Minuten Cache für Admin / Historie (High TTL)
def get_data_admin(sheet_id: str):
    try:
        ws = get_spreadsheet(sheet_id).sheet1
        return pd.DataFrame(ws.get_all_records())
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=15)  # 15 Sekunden Cache für Event-Ansicht / Screensaver
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

# --- NEUE PERFORMANCE FUNKTION ---
def fetch_latest_status_only(sheet_id: str):
    """
    Liest NUR die allerletzte Zeile aus dem Sheet.
    Umgeht get_all_records() und ist extrem schnell.
    """
    try:
        ws = get_spreadsheet(sheet_id).sheet1
        
        # Metadata Trick: col_values(1) ist meist sehr schnell gecached bei Google
        col_a = ws.col_values(1)
        num_rows = len(col_a)
        
        if num_rows < 2:
            return None # Nur Header oder leer
            
        # Wir holen nur den Bereich der letzten Zeile (z.B. A500:F500)
        # Annahme: Spalten A bis F reichen (Timestamp, MediaRemaining, Status...)
        raw_vals = ws.get_values(f"A{num_rows}:Z{num_rows}")
        
        if not raw_vals:
            return None
            
        row = raw_vals[0]
        
        # Mapping basierend auf Standard-Struktur
        # Falls Header variieren, müsste man Zeile 1 cachen. 
        # Hier gehen wir von Standard Indizes aus:
        # A=Timestamp, B=MediaRemaining, C=Status (Beispiel)
        # Sicherer: Wir suchen im Code nach Key-Names, daher mappen wir hier generisch
        # Da wir im Interface "Status" und "MediaRemaining" brauchen, müssen wir wissen wo die stehen.
        # Fallback: Wir nutzen get_data_event wenn wir sicher sein wollen, aber für Fleet Overview reicht Speed.
        
        # Um es robust zu machen, holen wir Header EINMALIG (gecached in gspread)
        # und mappen dann.
        headers = ws.row_values(1)
        
        # Zip Header und Row zu Dict
        if len(row) < len(headers):
             # Padding falls leere Zellen am Ende
             row += [""] * (len(headers) - len(row))
             
        return dict(zip(headers, row))
        
    except Exception as e:
        # Fallback auf langsamen Weg, falls Fast-Path crasht
        return None

def fetch_single_status(sheet_id: str, printer_key: str, media_factor: int):
    """
    Hilfsfunktion für den Thread-Worker: Lädt Daten für EINE Box
    """
    if not sheet_id:
        return printer_key, None

    try:
        # HIER DIE ÄNDERUNG: Nutze den Fast-Reader statt get_data_event
        # Das spart Zeit beim Parsen von Tausenden Zeilen
        last_data = fetch_latest_status_only(sheet_id)
        
        if not last_data:
            # Fallback falls Fast-Read fehlschlägt (z.B. leeres Blatt)
            df = get_data_event(sheet_id)
            if df.empty:
                return printer_key, None
            last_data = df.iloc[-1].to_dict()

        # Daten extrahieren
        raw_status = str(last_data.get("Status", "")).lower()
        timestamp = str(last_data.get("Timestamp", ""))[-8:] # Nur Uhrzeit
        
        try:
            media_val = int(last_data.get("MediaRemaining", 0)) * media_factor
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
        return printer_key, None

def get_fleet_data_parallel(printers_config: dict, secrets_printers: dict) -> dict:
    """
    Lädt alle Fotobox-Statuswerte PARALLEL.
    """
    results = {}
    
    # ThreadPoolExecutor erstellt einen Pool von Worker-Threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_printer = {}
        
        for name, cfg in printers_config.items():
            key = cfg["key"]
            s_id = secrets_printers.get(key, {}).get("sheet_id")
            media_factor = cfg.get("media_factor", 1)
            
            future = executor.submit(fetch_single_status, s_id, name, media_factor)
            future_to_printer[future] = name

        for future in concurrent.futures.as_completed(future_to_printer):
            printer_name = future_to_printer[future]
            try:
                key_check, data = future.result()
                results[printer_name] = data
            except Exception:
                results[printer_name] = None
                
    return results
