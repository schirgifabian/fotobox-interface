# report_generator.py
import datetime
import pandas as pd
from fpdf import FPDF
import streamlit as st

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Fotobox Event Report', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Seite {self.page_no()}', 0, 0, 'C')

def generate_event_pdf(
    df: pd.DataFrame, 
    printer_name: str, 
    stats: dict, 
    prints_since_reset: int,
    cost_info: str
) -> bytes:
    """Erstellt ein PDF Byte-Objekt für den Download"""
    
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # 1. Metadaten
    now_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    pdf.cell(0, 10, f"Drucker: {printer_name}", ln=True)
    pdf.cell(0, 10, f"Bericht erstellt am: {now_str}", ln=True)
    pdf.ln(10)
    
    # 2. Statistiken
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Zusammenfassung:", ln=True)
    pdf.set_font("Arial", size=12)
    
    pdf.cell(0, 8, f"- Gedruckte Fotos (seit Reset): {prints_since_reset}", ln=True)
    pdf.cell(0, 8, f"- Geschätzte Kosten: {cost_info}", ln=True)
    
    duration = stats.get("duration_min", 0)
    h = int(duration // 60)
    m = int(duration % 60)
    pdf.cell(0, 8, f"- Aktive Laufzeit (Log): {h} Std {m} Min", ln=True)
    
    ppm = stats.get("ppm_overall")
    ppm_str = f"{ppm * 60:.1f}" if ppm else "-"
    pdf.cell(0, 8, f"- Durchsatz (Session): {ppm_str} Bilder/Std", ln=True)
    
    pdf.ln(10)
    
    # 3. Zeitverlauf (Letzte Logs)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Letzte 20 Log-Einträge:", ln=True)
    pdf.set_font("Courier", size=8) # Monospace für Tabelle
    
    # Kopfzeile
    pdf.cell(45, 6, "Zeitstempel", 1)
    pdf.cell(30, 6, "Papier", 1)
    pdf.cell(100, 6, "Status", 1)
    pdf.ln()
    
    # Datenzeilen
    if not df.empty:
        df_print = df.tail(20).copy()
        # Sortieren, neueste oben
        if "Timestamp" in df_print.columns:
             df_print = df_print.sort_values("Timestamp", ascending=False)
             
        for _, row in df_print.iterrows():
            ts = str(row.get("Timestamp", ""))[-19:] # Abschneiden falls zu lang
            media = str(row.get("MediaRemaining", ""))
            status = str(row.get("Status", ""))[:50] # Status kürzen
            
            # UTF-8 Encoding Fix für FPDF (simple approach)
            status = status.encode('latin-1', 'replace').decode('latin-1')
            
            pdf.cell(45, 6, ts, 1)
            pdf.cell(30, 6, media, 1)
            pdf.cell(100, 6, status, 1)
            pdf.ln()

    # Output als String (latin-1 encoding für FPDF notwendig oft)
    return pdf.output(dest='S').encode('latin-1')
