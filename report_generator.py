# report_generator.py
import datetime
import io
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from fpdf import FPDF
import streamlit as st

class PDFReport(FPDF):
    def header(self):
        # Logo oder Titel oben
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Fotobox Event Report', 0, 1, 'C')
        self.set_draw_color(200, 200, 200)
        self.line(10, 25, 200, 25) # Horizontale Linie
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Seite {self.page_no()} | Generiert durch Fotobox-Interface', 0, 0, 'C')

def create_usage_chart(df: pd.DataFrame, media_factor: int = 1) -> io.BytesIO:
    """
    Erstellt ein Matplotlib-Diagramm (Verbrauch über Zeit) 
    und gibt es als Byte-Buffer zurück.
    """
    # 1. Daten vorbereiten
    if df.empty or "Timestamp" not in df.columns or "MediaRemaining" not in df.columns:
        return None

    df_chart = df.copy()
    # Sicherstellen, dass Timestamp datetime ist
    df_chart["Timestamp"] = pd.to_datetime(df_chart["Timestamp"], errors="coerce")
    df_chart = df_chart.dropna(subset=["Timestamp", "MediaRemaining"])
    df_chart = df_chart.sort_values("Timestamp")
    
    # Echte Bildanzahl berechnen
    df_chart["PrintsRemaining"] = df_chart["MediaRemaining"] * media_factor
    
    # Zeit und Werte extrahieren
    x = df_chart["Timestamp"].values
    y = df_chart["PrintsRemaining"].values
    
    if len(x) < 2:
        return None

    # 2. Plot erstellen
    plt.style.use('bmh') # Hübscherer Style
    fig, ax = plt.subplots(figsize=(10, 5))
    
    # Hauptlinie (Verlauf)
    ax.plot(x, y, label='Papierbestand', color='#2563EB', linewidth=2, marker='o', markersize=3)
    
    # 3. Trendlinie (Lineare Regression) hinzufügen
    # Konvertiere Timestamps in numerische Werte für die Berechnung
    x_num = mdates.date2num(df_chart["Timestamp"])
    
    # Fit (Polynom 1. Grades = Gerade)
    z = np.polyfit(x_num, y, 1)
    p = np.poly1d(z)
    
    # Trendlinie plotten
    ax.plot(x, p(x_num), "r--", alpha=0.6, linewidth=1, label='Trend (Verbrauch)')

    # 4. Formatierung
    ax.set_title("Papierverbrauch über Zeit", fontsize=12, pad=10)
    ax.set_ylabel("Verbleibende Bilder")
    ax.set_xlabel("Uhrzeit")
    
    # X-Achse schön formatieren (Stunden:Minuten)
    myFmt = mdates.DateFormatter('%H:%M')
    ax.xaxis.set_major_formatter(myFmt)
    fig.autofmt_xdate()
    
    ax.legend()
    ax.grid(True, which='both', linestyle='--', alpha=0.5)

    # 5. Speichern in Buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig) # Memory Leak verhindern
    
    return buf

def generate_event_pdf(
    df: pd.DataFrame, 
    printer_name: str, 
    stats: dict, 
    prints_since_reset: int,
    cost_info: str,
    media_factor: int = 1 # Neu: media_factor durchreichen
) -> bytes:
    """Erstellt ein erweitertes PDF mit Diagramm"""
    
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # --- 1. Metadaten Block ---
    now_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(40, 8, "Drucker:", 0, 0)
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 8, printer_name, 0, 1)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(40, 8, "Zeitpunkt:", 0, 0)
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 8, now_str, 0, 1)
    pdf.ln(5)
    
    # --- 2. Key Metrics (Karten-Optik via Rahmen) ---
    pdf.set_fill_color(245, 247, 250)
    pdf.rect(10, pdf.get_y(), 190, 35, 'F')
    pdf.set_y(pdf.get_y() + 5)
    
    # Wir bauen 2 Spalten
    start_y = pdf.get_y()
    left_margin = 15
    
    # Spalte 1
    pdf.set_font("Arial", 'B', 10)
    pdf.set_xy(left_margin, start_y)
    pdf.cell(80, 6, "GEDRUCKTE FOTOS (Gesamt)", 0, 1)
    pdf.set_font("Arial", 'B', 16)
    pdf.set_text_color(37, 99, 235) # Blau
    pdf.set_xy(left_margin, start_y + 7)
    pdf.cell(80, 8, str(prints_since_reset), 0, 1)
    
    # Spalte 2
    pdf.set_text_color(0)
    pdf.set_font("Arial", 'B', 10)
    pdf.set_xy(100, start_y)
    pdf.cell(80, 6, "GESCHÄTZTE KOSTEN", 0, 1)
    pdf.set_font("Arial", 'B', 16)
    pdf.set_text_color(5, 150, 105) # Grün
    pdf.set_xy(100, start_y + 7)
    pdf.cell(80, 8, cost_info, 0, 1)
    
    # Zweite Zeile Metrics
    pdf.set_text_color(100)
    pdf.set_font("Arial", '', 10)
    
    ppm = stats.get("ppm_overall")
    ppm_str = f"{ppm * 60:.1f}" if ppm else "-"
    
    duration = stats.get("duration_min", 0)
    h = int(duration // 60)
    m = int(duration % 60)
    
    pdf.set_xy(left_margin, start_y + 18)
    pdf.cell(80, 6, f"Durchschnitt: {ppm_str} Bilder/Std", 0, 1)
    
    pdf.set_xy(100, start_y + 18)
    pdf.cell(80, 6, f"Aktive Laufzeit: {h} Std {m} Min", 0, 1)
    
    pdf.ln(15) # Aus dem grauen Kasten raus
    pdf.set_text_color(0)

    # --- 3. Diagramm Einfügen ---
    chart_buffer = create_usage_chart(df, media_factor)
    if chart_buffer:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Verlauf & Analyse", 0, 1)
        
        # HIER IST DER FIX 1: type='png' hinzufügen
        pdf.image(chart_buffer, x=10, w=190, type='png') 
        
        pdf.ln(5)
    
    # --- 4. Tabelle (Letzte Logs) ---
    pdf.add_page() # Tabelle auf neuer Seite starten, falls Chart groß ist
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Detaillierte Log-Einträge (Auszug)", 0, 1)
    
    pdf.set_font("Courier", 'B', 9)
    pdf.set_fill_color(230, 230, 230)
    # Header
    pdf.cell(45, 8, "Zeitstempel", 1, 0, 'C', 1)
    pdf.cell(30, 8, "Rest", 1, 0, 'C', 1)
    pdf.cell(115, 8, "Status Meldung", 1, 1, 'L', 1)
    
    pdf.set_font("Courier", '', 8)
    
    if not df.empty:
        # Sortieren, neueste oben, max 40 Einträge für PDF
        df_print = df.copy()
        if "Timestamp" in df_print.columns:
             df_print = df_print.sort_values("Timestamp", ascending=False)
        
        df_print = df_print.head(40) 

        for i, row in df_print.iterrows():
            ts = str(row.get("Timestamp", ""))[-19:]
            
            # Media berechnen
            try:
                raw_media = int(row.get("MediaRemaining", 0))
                media_val = str(raw_media * media_factor)
            except:
                media_val = str(row.get("MediaRemaining", ""))
                
            status = str(row.get("Status", ""))[:65]
            
            # Encoding Fix
            status = status.encode('latin-1', 'replace').decode('latin-1')
            
            pdf.cell(45, 6, ts, 1)
            pdf.cell(30, 6, media_val, 1, 0, 'C')
            pdf.cell(115, 6, status, 1, 1)

    # HIER IST DER FIX 2: .encode('latin-1') entfernt und in bytes() gewrappt
    return bytes(pdf.output(dest='S'))
