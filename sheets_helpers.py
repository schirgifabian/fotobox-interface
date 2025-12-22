# sheets_helpers.py

import datetime
import pandas as pd
import gspread
import streamlit as st
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound


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
    Settings-Worksheet holen oder bei Bedarf erstellen.
    """
    sh = get_spreadsheet(sheet_id)
    try:
        return sh.worksheet("Settings")
    except WorksheetNotFound:
        ws = sh.add_worksheet(title="Settings", rows=100, cols=3)
        ws.append_row(["Key", "Value", "UpdatedAt"])
        return ws


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


@st.cache_data(ttl=30)  # 30 Sekunden Cache für Event-Ansicht
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

def get_printers_config(master_sheet_id: str):
    """
    Lädt die Fotobox-Konfiguration aus dem Tab 'Printers'.
    Gibt ein Dictionary zurück, das genau so aufgebaut ist wie das alte PRINTERS dict.
    """
    try:
        sh = get_spreadsheet(master_sheet_id)
        # Versuche das Worksheet 'Printers' zu finden
        try:
            ws = sh.worksheet("Printers")
        except WorksheetNotFound:
            # Falls nicht existiert, erstellen wir es mit Headern
            ws = sh.add_worksheet(title="Printers", rows=50, cols=15)
            ws.append_row([
                "Name", "Key", "SheetId", "WarningThreshold", 
                "DefaultMaxPrints", "CostPerRoll", "MediaFactor", 
                "HasAdmin", "HasAqara", "HasDsr"
            ])
            return {}

        records = ws.get_all_records()
        printers_dict = {}

        for row in records:
            name = row.get("Name")
            if not name: 
                continue
                
            # Daten normalisieren und Typen konvertieren
            printers_dict[name] = {
                "key": str(row.get("Key", "standard")),
                "sheet_id": str(row.get("SheetId", "")), # WICHTIG: SheetID kommt jetzt hierher
                "warning_threshold": int(row.get("WarningThreshold") or 20),
                "default_max_prints": int(row.get("DefaultMaxPrints") or 400),
                "cost_per_roll_eur": float(str(row.get("CostPerRoll", 0)).replace(",", ".")),
                "media_factor": int(row.get("MediaFactor") or 1),
                "has_admin": str(row.get("HasAdmin", "TRUE")).upper() == "TRUE",
                "has_aqara": str(row.get("HasAqara", "FALSE")).upper() == "TRUE",
                "has_dsr": str(row.get("HasDsr", "FALSE")).upper() == "TRUE",
            }
            
        return printers_dict
    except Exception as e:
        st.error(f"Fehler beim Laden der Drucker-Konfig: {e}")
        return {}

def add_new_printer(master_sheet_id: str, printer_data: dict):
    """
    Fügt eine neue Fotobox in den Tab 'Printers' ein.
    """
    try:
        sh = get_spreadsheet(master_sheet_id)
        ws = sh.worksheet("Printers")
        
        row = [
            printer_data["Name"],
            printer_data["Key"],
            printer_data["SheetId"],
            printer_data["WarningThreshold"],
            printer_data["DefaultMaxPrints"],
            printer_data["CostPerRoll"],
            printer_data["MediaFactor"],
            printer_data["HasAdmin"],
            printer_data["HasAqara"],
            printer_data["HasDsr"]
        ]
        ws.append_row(row)
        # Cache löschen, damit der neue Drucker sofort sichtbar ist
        get_printers_config.clear() # Falls du @st.cache_data nutzt (empfohlen)
        st.toast("Fotobox erfolgreich gespeichert!", icon="✅")
    except Exception as e:
        st.error(f"Fehler beim Speichern: {e}")
