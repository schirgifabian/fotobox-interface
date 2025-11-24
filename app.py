import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# Seite konfigurieren
st.set_page_config(page_title="Drucker Monitor", page_icon="🖨️", layout="centered")

# --- VERBINDUNG ZU GOOGLE SHEETS ---
# In Streamlit Cloud legst du die secrets in .streamlit/secrets.toml ab
# Format der Secrets:
# [gcp_service_account]
# type = "service_account"
# ... (der ganze Inhalt deiner JSON Datei)

@st.cache_data(ttl=10) # Cache für 10 Sekunden, damit wir nicht zu viele Anfragen senden
def load_data():
    # Scopes definieren
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    # Credentials aus Streamlit Secrets laden
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    
    gc = gspread.authorize(credentials)
    # Öffne das Sheet über den Namen oder die URL (URL ist sicherer)
    # Ersetze DEINE_SHEET_URL mit der URL deines Google Sheets
    sh = gc.open_by_url("DEINE_GOOGLE_SHEET_URL_HIER_EINFÜGEN")
    worksheet = sh.sheet1
    
    # Daten holen (nur die zweite Zeile, da dort der aktuelle Status steht)
    # Wir holen alles als DataFrame für einfacheres Handling
    data = worksheet.get_all_records()
    return data

# --- UI BAUEN ---

st.title("🖨️ Citizen CX-02 Status")

try:
    data = load_data()
    
    if not data:
        st.warning("Noch keine Daten im Sheet.")
    else:
        # Wir nehmen den letzten Eintrag (bzw. den einzigen in Zeile 2)
        latest_entry = data[0] 
        
        status = latest_entry['Status'] # Spalte C
        details = latest_entry['Details'] # Spalte D
        timestamp = latest_entry['Zeitstempel'] # Spalte A

        # Große Anzeige
        if status == "OK" or status == "Bereit":
            st.success(f"### STATUS: {status}")
            st.markdown(f"**Alles in Ordnung.**")
        else:
            st.error(f"### STATUS: {status}")
            st.markdown(f"⚠️ **Achtung:** Handlungsbedarf!")

        # Metriken
        col1, col2 = st.columns(2)
        col1.metric("Letztes Update", timestamp.split(" ")[1]) # Nur Uhrzeit
        col2.metric("Details", details)
        
        # Refresh Button
        if st.button("Status aktualisieren"):
            st.rerun()

except Exception as e:
    st.error(f"Verbindung zur Datenbank fehlgeschlagen: {e}")
    st.info("Bitte prüfe die Secrets in der Streamlit Cloud.")
