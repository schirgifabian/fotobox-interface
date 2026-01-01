# monitor.py
import time
import datetime
import toml
import requests
import pandas as pd
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
            "Tags": tags
        }
        requests.post(f"https://ntfy.sh/{topic}", data=message.encode("utf-8"), headers=headers, timeout=5)
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Push gesendet: {title}")
    except Exception as e:
        print(f"Push Error: {e}")

def get_printer_settings(gc, sheet_id):
    """
    Liest Push-Status (ntfy_active) UND Wartungsmodus (maintenance_mode) aus.
    Rückgabe: (push_active, maintenance_active)
    """
    default_push = True
    default_maint = False
    
    if not sheet_id: return default_push, default_maint
    
    try:
        sh = gc.open_by_key(sheet_id)
        try:
            ws = sh.worksheet("Settings")
        except:
            return default_push, default_maint
            
        records = ws.get_all_records()
        
        push_active = default_push
        maintenance_active = default_maint
        
        for row in records:
            k = row.get("Key")
            v = str(row.get("Value")).lower()
            
            if k == "ntfy_active":
                push_active = (v == "true")
            elif k == "maintenance_mode":
                maintenance_active = (v == "true")
                
        return push_active, maintenance_active
        
    except Exception as e:
        print(f"Fehler Settings: {e}")
        return default_push, default_maint

def main():
    print("Starte Fotobox Monitor Daemon...")
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

                if not sheet_id or not topic: continue

                # 1. Einstellungen prüfen (Push AN? Wartung AN?)
                push_active, maintenance_active = get_printer_settings(gc, sheet_id)

                # Wenn Box im Lager ("Eingelagert" / Wartung) -> Nächster Drucker
                if maintenance_active:
                    # Optional: Speicher resetten, damit beim Wiedereinschalten sofort geprüft wird
                    if key in state_memory: del state_memory[key]
                    continue 

                # 2. Daten holen
                try:
                    sh = gc.open_by_key(sheet_id)
                    ws = sh.sheet1
                    all_values = ws.get_all_values()
                    if len(all_values) < 2: continue
                    data = dict(zip(all_values[0], all_values[-1]))
                except Exception:
                    continue

                # 3. Status prüfen
                try:
                    raw_status = str(data.get("Status", "")).lower()
                    media_val = int(data.get("MediaRemaining", 0)) * factor
                except:
                    continue

                current_status = "ready"
                msg = ""
                tag = ""
                
                if any(x in raw_status for x in ["error", "jam", "end", "fehlt", "störung"]):
                    current_status = "error"
                    msg = f"Störung: {raw_status}"
                    tag = "rotating_light"
                elif media_val <= threshold:
                    current_status = "low_paper"
                    msg = f"Wenig Papier: {media_val} (<{threshold})!"
                    tag = "warning"
                
                # 4. Push Logik
                mem = state_memory.get(key, {"last_status": "init", "last_push_time": 0})
                now = time.time()
                
                if current_status in ["error", "low_paper"]:
                    is_new = mem["last_status"] != current_status
                    is_cd_over = (now - mem["last_push_time"]) > (30 * 60)

                    if is_new or is_cd_over:
                        if push_active:
                            send_ntfy(topic, f"{name}: {current_status.upper()}", msg, tag)
                            mem["last_push_time"] = now
                        else:
                            print(f"Push für '{name}' unterdrückt (App-Schalter aus).")
                
                elif current_status == "ready" and mem["last_status"] == "error":
                     if push_active:
                        send_ntfy(topic, f"{name}: OK", "Störung behoben.", "white_check_mark")

                mem["last_status"] = current_status
                state_memory[key] = mem
                
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error Loop: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
