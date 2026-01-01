# monitor.py
import time
import datetime
import toml
import requests
import gspread
from google.oauth2.service_account import Credentials

# --- KONFIGURATION ---
SECRETS_PATH = ".streamlit/secrets.toml"
CHECK_INTERVAL = 60  # Alle 60 Sekunden prüfen

PRINTERS = {
    "die Fotobox": {
        "key": "standard",
        "warning_threshold": 40,
        "media_factor": 1,
    },
    "Weinkellerei": {
        "key": "Weinkellerei",
        "warning_threshold": 30,
        "media_factor": 0.5,
    },
}

def load_secrets():
    return toml.load(SECRETS_PATH)

def get_gspread_client(secrets):
    creds_info = secrets["gcp_service_account"]
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    return gspread.authorize(creds)

def send_ntfy(topic, title, message, tags="warning"):
    if not topic: return
    try:
        headers = {
            "Title": title.encode("latin-1", "ignore").decode("latin-1"),
            "Tags": tags,
            "Priority": "high" if tags == "rotating_light" else "default"
        }
        requests.post(f"https://ntfy.sh/{topic}", data=message.encode("utf-8"), headers=headers, timeout=5)
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Push gesendet: {title}")
    except Exception as e:
        print(f"Push Error: {e}")

def get_printer_settings(gc, sheet_id):
    """
    Liest Push-Status (ntfy_active) UND Wartungsmodus (maintenance_mode) aus.
    """
    default_push = True
    default_maint = False
    
    if not sheet_id: return default_push, default_maint
    
    try:
        sh = gc.open_by_key(sheet_id)
        try:
            # Wir versuchen, das Settings Sheet zu holen
            ws = sh.worksheet("Settings")
        except:
            # Falls es noch nicht existiert, Defaults nutzen
            return default_push, default_maint
            
        records = ws.get_all_records()
        
        push_active = default_push
        maintenance_active = default_maint
        
        for row in records:
            k = row.get("Key")
            # Sicherstellen, dass wir Strings vergleichen, egal was Gspread liefert
            v_raw = row.get("Value")
            v = str(v_raw).lower().strip()
            
            if k == "ntfy_active":
                # Prüft auf "true", "1", "yes" oder echtes True
                push_active = v in ["true", "1", "yes", "on"]
            elif k == "maintenance_mode":
                maintenance_active = v in ["true", "1", "yes", "on"]
                
        return push_active, maintenance_active
        
    except Exception as e:
        print(f"Warnung: Konnte Settings nicht lesen (Sheet ID {sheet_id}): {e}")
        return default_push, default_maint

def fetch_last_row_optimized(ws):
    """
    Hole nur Header und die allerletzte Zeile, statt das ganze Sheet.
    Das spart massiv Bandbreite und CPU.
    """
    # [cite_start]1. Nur Spalte A (Timestamp) holen, um die Anzahl der Zeilen zu kennen [cite: 1]
    # Das ist viel schneller als get_all_values()
    timestamps = ws.col_values(1)
    num_rows = len(timestamps)
    
    if num_rows < 2:
        return {}

    # 2. Header holen (Zeile 1)
    headers = ws.row_values(1)
    
    # 3. Letzte Zeile holen (Zeile num_rows)
    last_values = ws.row_values(num_rows)
    
    # Falls die letzte Zeile weniger Spalten hat als der Header (leere Zellen am Ende), auffüllen
    if len(last_values) < len(headers):
        last_values += [""] * (len(headers) - len(last_values))
        
    return dict(zip(headers, last_values))

def main():
    print("Starte Fotobox Monitor Daemon (Optimiert)...")
    secrets = load_secrets()
    gc = get_gspread_client(secrets)
    state_memory = {}

    while True:
        try:
            printer_secrets = secrets.get("printers", {})

            for name, cfg in PRINTERS.items():
                key = cfg["key"]
                p_sec = printer_secrets.get(key, {})
                sheet_id = p_sec.get("sheet_id")
                topic = p_sec.get("ntfy_topic")
                threshold = cfg.get("warning_threshold", 20)
                factor = cfg.get("media_factor", 1)

                if not sheet_id or not topic: 
                    continue

                # Kurze Pause zwischen den Druckern, um API Rate Limits zu schonen
                time.sleep(1)

                # 1. Einstellungen prüfen
                push_active, maintenance_active = get_printer_settings(gc, sheet_id)

                # Wenn Wartungsmodus aktiv -> überspringen
                if maintenance_active:
                    if key in state_memory: 
                        del state_memory[key]
                    continue 

                # 2. Daten holen (OPTIMIERT)
                try:
                    sh = gc.open_by_key(sheet_id)
                    ws = sh.sheet1
                    
                    # Hier benutzen wir die neue Funktion
                    data = fetch_last_row_optimized(ws)
                    
                    if not data:
                        continue
                        
                except Exception as e:
                    print(f"Fehler beim Datenabruf für '{name}': {e}")
                    continue

                # 3. Status prüfen
                try:
                    raw_status = str(data.get("Status", "")).lower()
                    media_val = int(data.get("MediaRemaining", 0)) * factor
                except Exception:
                    # Falls Daten korrupt sind (z.B. Header da, aber leer)
                    continue

                current_status = "ready"
                msg = ""
                tag = ""
                
                # Logik: Fehler oder Wenig Papier
                if any(x in raw_status for x in ["error", "jam", "end", "fehlt", "störung"]):
                    current_status = "error"
                    msg = f"Störung: {raw_status}"
                    tag = "rotating_light"
                elif media_val <= threshold:
                    current_status = "low_paper"
                    msg = f"Wenig Papier: {media_val} (<{threshold})!"
                    tag = "warning"
                
                # 4. Push Senden
                mem = state_memory.get(key, {"last_status": "init", "last_push_time": 0})
                now = time.time()
                
                # Push senden, wenn Status kritisch (Error/Low Paper)
                if current_status in ["error", "low_paper"]:
                    is_new = mem["last_status"] != current_status
                    # Cooldown von 30 Minuten für wiederholte Warnungen
                    is_cd_over = (now - mem["last_push_time"]) > (30 * 60)

                    if is_new or is_cd_over:
                        if push_active:
                            send_ntfy(topic, f"{name}: {current_status.upper()}", msg, tag)
                            mem["last_push_time"] = now
                            print(f"-> Warnung für {name} gesendet.")
                        else:
                            print(f"-> Push für '{name}' unterdrückt (Einstellung aus).")
                
                # Entwarnung senden, wenn Fehler behoben wurde
                elif current_status == "ready" and mem["last_status"] == "error":
                     if push_active:
                        send_ntfy(topic, f"{name}: OK", "Störung behoben.", "white_check_mark")
                        print(f"-> Entwarnung für {name} gesendet.")

                mem["last_status"] = current_status
                state_memory[key] = mem
                
            # Warten bis zum nächsten Zyklus
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("Monitor gestoppt.")
            break
        except Exception as e:
            print(f"Globaler Loop Fehler: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
