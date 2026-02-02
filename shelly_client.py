# shelly_client.py
import requests
from typing import Dict, Any, Optional

class ShellyClient:
    def __init__(self, cloud_url: str, auth_key: str, device_id: str):
        self.base_url = cloud_url.strip().rstrip("/")
        # URL Bereinigung
        if ":6022" in self.base_url:
            self.base_url = self.base_url.split(":6022")[0]
        if "/jrpc" in self.base_url:
            self.base_url = self.base_url.replace("/jrpc", "")
        if "/device" in self.base_url:
            self.base_url = self.base_url.split("/device")[0]
            
        self.auth_key = auth_key.strip()
        self.device_id = device_id.strip()
        
        # PERFORMANCE: Timeout auf 2.0 Sekunden reduziert!
        # Wenn Shelly Cloud länger braucht, ist sie eh zu langsam für UI.
        self.timeout = 2.0 

    def _post(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict]:
        """
        Hilfsfunktion für Requests an die Standard Cloud API.
        Fail-Fast Strategie: Kein Retry, kurzes Timeout.
        """
        url = f"{self.base_url}{endpoint}"
        
        data = {
            "auth_key": self.auth_key,
            "id": self.device_id
        }
        data.update(params)
        
        try:
            # Sendet Form-Data
            response = requests.post(url, data=data, timeout=self.timeout)
            
            if response.status_code == 200:
                try:
                    json_resp = response.json()
                    if json_resp.get("isok") == True:
                        return json_resp.get("data", {})
                    # Keine Fehler-Prints mehr im UI-Thread, das verlangsamt nur
                    return None
                except ValueError:
                    return None
            return None
            
        except Exception:
            # Silent Fail für Performance
            return None

    def get_status(self) -> Dict[str, Any]:
        data = self._post("/device/status", {})
        if not data: return {}
            
        # Normalisierung
        source_data = data
        if "device_status" in data:
            source_data = data["device_status"]
            
        found_switches = False
        normalized = {}
        for k, v in source_data.items():
            if k.startswith("switch:"):
                normalized[k] = v
                found_switches = True
                
        if found_switches: return normalized
        return source_data

    def set_switch(self, switch_id: int, turn_on: bool) -> bool:
        params = {
            "channel": switch_id,
            "turn": "on" if turn_on else "off"
        }
        res = self._post("/device/relay/control", params)
        return res is not None
