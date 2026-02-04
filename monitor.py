# monitor.py
import time
import datetime
import toml
import requests
import json
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
    """Lädt die Konfiguration aus den Streamlit Secrets."""
    return toml.load(SECRETS_PATH)

def get_gspread_client(secrets):
    """Initialisiert den Google Sheets Client."""
    creds_info = secrets["gcp_service_account"]
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    return gspread.authorize(creds)

def send_ntfy(topic, title, message, tags="warning"):
    """Sendet eine Push-Benachrichtigung via ntfy.sh."""
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

def get_printer_settings_full(gc, sheet_id):
    """Holt alle Einstellungen (inkl. Shelly Cloud Parameter) aus dem Google Sheet."""
    default_res = {
        "ntfy_active": True, 
        "maintenance_mode": False, 
        "shelly_cloud_url": "https://shelly-api-eu.shelly.cloud:6022/jrpc",
        "shelly_auth_key": None,
        "shelly_device_id": None,
        "shelly_config": {}
    }
    if not sheet_id: return default_res
    
    try:
        sh = gc.open_by_key(sheet_id)
        try:
            ws = sh.worksheet("Settings")
        except:
            return default_res
            
        records = ws.get_all_records()
        res = default_res.copy()
        
        for row in records:
            k = row.get("Key")
            v_raw = row.get("Value")
            v = str(v_raw).strip()
            
            if k == "ntfy_active":
                res["ntfy_active"] = v.lower() in ["true", "1", "yes", "on"]
            elif k == "maintenance_mode":
                res["maintenance_mode"] = v.lower() in ["true", "1", "yes", "on"]
            elif k == "shelly_cloud_url":
                res["shelly_cloud_url"] = v
            elif k == "shelly_auth_key":
                res["shelly_auth_key"] = v
            elif k == "shelly_device_id":
                res["shelly_device_id"] = v
            elif k == "shelly_config":
                try:
                    res["shelly_config"] = json.loads(v)
                except:
                    pass
                
        return res
    except Exception as e:
        print(f"Warnung: Konnte Settings nicht lesen: {e}")
        return default_res

def check_shelly_health(cloud_url, auth_key, device_id, shelly_config, topic, printer_name, memory):
    """Prüft den Stromverbrauch via Shelly Cloud API auf Hardware-Defekte."""
    if not auth_key or not device_id or not shelly_config: return memory

    try:
        if not cloud_url or not cloud_url.startswith("http"): 
            cloud_url = "https://shelly-api-eu.shelly.cloud:6022/jrpc"
            
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "Shelly.Call",
            "params": {
                "auth": auth_key,
                "id": device_id,
                "method": "Shelly.GetStatus"
            }
        }
        
        resp = requests.post(cloud_url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
        json_resp = resp.json()
        
        data = {}
        if "result" in json_resp and "data" in json_resp["result"]:
            data = json_resp["result"]["data"]
        else:
            data = json_resp.get("result", {})
            
    except Exception as e:
        print(f"Shelly Check Fail ({printer_name}): {e}")
        return memory

    for idx_str, cfg in shelly_config.items():
        if not cfg.get("check_power", False):
            continue
            
        name = cfg.get("name", f"Socket {idx_str}")
        min_w = cfg.get("standby_min")
        
        switch_key = f"switch:{idx_str}"
        switch_data = data.get(switch_key, {})
        is_on = switch_data.get("output", False)
        power = switch_data.get("apower", 0.0)
        
        mem_key = f"shelly_alert_{printer_name}_{idx_str}"
        
        # Alarm-Logik: Gerät ist eingeschaltet, verbraucht aber zu wenig Strom
        if is_on and min_w is not None and power < min_w:
            if not memory.get(mem_key, False):
                msg = f"{name} verbraucht nur {power:.1f}W (Erwartet: >{min_w}W). Defekt?"
                send_ntfy(topic, f"⚠️ Hardware Check: {name}", msg, "electric_plug")
                memory[mem_key] = True
        else:
            if memory.get(mem_key, False):
                memory[mem_key] = False
                
    return memory

def fetch_last_row_optimized(ws):
    """Liest nur die letzte Zeile des Worksheets aus (optimiert)."""
    timestamps = ws.col_values(1)
    num_rows = len(timestamps)
    if num_rows < 2: return {}
    headers = ws.row_values(1)
    last_values = ws.row_values(num_rows)
    if len(last_values) < len(headers):
        last_values += [""] * (len(headers) - len(last_values))
    return dict(zip(headers, last_values))

def main():
    print("Starte Fotobox Monitor Daemon (Shelly Cloud)...")
    secrets = load_secrets()
    gc = get_gspread_client(secrets)
    state_memory = {}
    shelly_memory = {} 

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
                
                time.sleep(1) # API-Schonung

                # 1. Settings laden
                settings = get_printer_settings_full(gc, sheet_id)
                push_active = settings["ntfy_active"]
                maint_active = settings["maintenance_mode"]
                
                if maint_active:
                    if key in state_memory: del state_memory[key]
                    continue 

                # 2. Shelly Cloud Hardware Check
                if settings["shelly_auth_key"] and settings["shelly_device_id"] and push_active:
                    shelly_memory = check_shelly_health(
                        settings["shelly_cloud_url"], settings["shelly_auth_key"], 
                        settings["shelly_device_id"], settings["shelly_config"], 
                        topic, name, shelly_memory
                    )

                # 3. Drucker Status Check
                try:
                    sh = gc.open_by_key(sheet_id)
                    data = fetch_last_row_optimized(sh.sheet1)
                    if not data: continue
                    
                    raw_status = str(data.get("Status", "")).lower()
                    media_val = int(data.get("MediaRemaining", 0)) * factor
                except Exception:
                    continue

                current_status = "ready"
                msg = ""
                tag = ""

                # Status-Evaluierung
                if any(x in raw_status for x in ["error", "jam", "end", "fehlt", "störung"]):
                    current_status = "error"
                    msg = f"Störung: {raw_status}"
                    tag = "rotating_light"
                elif media_val < 0:
                    current_status = "offline"
                    msg = f"Drucker nicht verbunden (Status: {media_val})"
                    tag = "electric_plug"
                elif media_val <= threshold:
                    current_status = "low_paper"
                    msg = f"Wenig Papier: {media_val} (<{threshold})!"
                    tag = "warning"
                
                # Push-Logik mit Cooldown
                mem = state_memory.get(key, {"last_status": "init", "last_push_time": 0})
                now = time.time()
                
                if current_status in ["error", "low_paper", "offline"]:
                    is_new = mem["last_status"] != current_status
                    is_cd_over = (now - mem["last_push_time"]) > (30 * 60) # 30 Min Cooldown

                    if is_new or is_cd_over:
                        if push_active:
                            send_ntfy(topic, f"{name}: {current_status.upper()}", msg, tag)
                            mem["last_push_time"] = now
                
                elif current_status == "ready" and mem["last_status"] in ["error", "offline"]:
                     if push_active:
                        send_ntfy(topic, f"{name}: OK", "Drucker ist wieder bereit.", "white_check_mark")

                mem["last_status"] = current_status
                state_memory[key] = mem
                
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("Monitor gestoppt.")
            break
        except Exception as e:
            print(f"Globaler Loop Fehler: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
