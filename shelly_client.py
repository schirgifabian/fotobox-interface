# shelly_client.py
import requests
from typing import Dict, Any, Optional

class ShellyClient:
    def __init__(self, cloud_url: str, auth_key: str, device_id: str):
        # URL Bereinigung: Wir wollen https://shelly-233-eu.shelly.cloud ohne Ports/Pfade
        self.base_url = cloud_url.strip().rstrip("/")
        # Falls User noch alte Ports drin hat, rauswerfen
        if ":6022" in self.base_url:
            self.base_url = self.base_url.split(":6022")[0]
        if "/jrpc" in self.base_url:
            self.base_url = self.base_url.replace("/jrpc", "")
        if "/device" in self.base_url:
            self.base_url = self.base_url.split("/device")[0]
            
        self.auth_key = auth_key.strip()
        self.device_id = device_id.strip()
        
        # PERFORMANCE: Kurzes Timeout für UI-Responsiveness (max 4 Sekunden warten)
        self.timeout = 4 

    def _post(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict]:
        """
        Hilfsfunktion für Requests an die Standard Cloud API.
        OPTIMIERT: Kein Retry-Loop, kein Sleep, Fail-Fast Strategie.
        """
        url = f"{self.base_url}{endpoint}"
        
        data = {
            "auth_key": self.auth_key,
            "id": self.device_id
        }
        data.update(params)
        
        try:
            # Wichtig: data=... sendet Form-Data (kein JSON Body), das will die Cloud
            response = requests.post(url, data=data, timeout=self.timeout)
            
            if response.status_code == 200:
                try:
                    json_resp = response.json()
                    if json_resp.get("isok") == True:
                        return json_resp.get("data", {})
                    else:
                        print(f"Shelly API Error: {json_resp.get('errors')}")
                        return None
                except ValueError:
                        print(f"Shelly API Fehler: Kein JSON erhalten")
                        return None
            else:
                print(f"Shelly HTTP {response.status_code}: {response.text}")
                return None
            
        except Exception as e:
            # Nur kurzes Print, kein Retry, kein UI-Freeze
            print(f"Shelly Connection Error: {e}")
            return None

    def get_status(self) -> Dict[str, Any]:
        """
        Holt den Status via /device/status.
        """
        data = self._post("/device/status", {})
        
        if not data:
            return {}
            
        # --- DATEN NORMALISIERUNG ---
        normalized = {}
        
        # Fall A: Gen2/3/4 Status versteckt sich in "device_status"
        source_data = data
        if "device_status" in data:
            source_data = data["device_status"]
            
        # Versuche Gen4 Struktur zu finden (switch:0)
        found_switches = False
        for k, v in source_data.items():
            if k.startswith("switch:"):
                normalized[k] = v
                found_switches = True
                
        if found_switches:
            return normalized
            
        # Fallback
        return source_data

    def set_switch(self, switch_id: int, turn_on: bool) -> bool:
        """
        Schaltet via /device/relay/control.
        """
        params = {
            "channel": switch_id,
            "turn": "on" if turn_on else "off"
        }
        
        res = self._post("/device/relay/control", params)
        return res is not None
