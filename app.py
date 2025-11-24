import streamlit as st
import gspread
import pandas as pd
from datetime import datetime

# --- SEITE KONFIGURIEREN ---
st.set_page_config(
    page_title="Citizen CX-02 Monitor",
    page_icon="🖨️",
    layout="centered"
)

# --- CSS FÜR BESSERE OPTIK ---
st.markdown("""
    <style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNKTION ZUM LADEN DER DATEN ---
def load_data():
    try:
        # 1. Zugangsdaten aus den Streamlit Secrets holen
        # Der Name in den eckigen Klammern muss exakt dem in den Secrets entsprechen: [gcp_service_account]
        credentials_dict = st.secrets["gcp_service_account"]
        
        # 2. Verbindung zu Google Sheets herstellen
        gc = gspread.service_account_from_dict(credentials_dict)
        
        # 3. Das Google Sheet öffnen
        # ACHTUNG: "DruckerStatus" muss exakt so heißen wie dein Google Sheet oben links
        sh = gc.open("DruckerStatus")
        
        # 4. Erstes Tabellenblatt wählen
        worksheet = sh.sheet1
        
        # 5. Alle Daten holen und in ein Pandas DataFrame umwandeln
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        return df, None
        
    except Exception as e:
        return None, str(e)

# --- HAUPTPROGRAMM ---
st.title("🖨️ Citizen CX-02 Status")

if st.button('🔄 Aktualisieren'):
    st.rerun()

# Daten laden
df, error = load_data()

if error:
    st.error(f"⚠️ Verbindung fehlgeschlagen! Fehlerdetails:\n\n{error}")
    st.info("Tipp: Prüfe, ob du das Sheet mit der 'client_email' aus den Secrets geteilt hast und ob der Name 'DruckerStatus' stimmt.")

elif df is not None and not df.empty:
    # Wir nehmen die letzte Zeile, da dies der neuste Eintrag ist
    latest_entry = df.iloc[-1]
    
    # Daten auslesen (Namen müssen mit deinen Spaltenüberschriften im Sheet übereinstimmen)
    # Falls deine Spalten anders heißen, pass das hier an:
    timestamp = latest_entry.get('Timestamp', 'Unbekannt')
    status = latest_entry.get('Status', 'Unbekannt')
    paper = latest_entry.get('Paper_Status', 'Unbekannt')
    # Falls du Restbilder mitloggst:
    remaining = latest_entry.get('Media_Remaining', '-') 

    # --- ANZEIGE ---
    
    # Status Farbe bestimmen
    status_color = "🟢" if "Ready" in str(status) or "Bereit" in str(status) else "🔴"
    if "Printing" in str(status): status_color = "🟡"

    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(label="Drucker Status", value=f"{status_color} {status}")
    
    with col2:
        st.metric(label="Papier Status", value=f"📄 {paper}")

    # Zusätzliche Infos
    st.divider()
    c1, c2 = st.columns(2)
    c1.write(f"**Letztes Update:** {timestamp}")
    if remaining != '-':
        c2.write(f"**Verbleibende Bilder:** {remaining}")

    # Historie anzeigen (optional, ausklappbar)
    with st.expander("Verlauf anzeigen (Letzte 10 Einträge)"):
        st.dataframe(df.tail(10).sort_index(ascending=False))

else:
    st.warning("Verbindung steht, aber das Google Sheet ist leer.")
