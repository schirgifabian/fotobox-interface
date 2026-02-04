# shelly_client.py
import requests
from typing import Dict, Any, Optional

class ShellyClient:
    def __init__(self, cloud_url: str, auth_key: str, default_device_id: str):
        self.base_url = cloud_url.strip().rstrip("/")
        # URL Bereinigung für verschiedene API Endpoints
        if ":6022" in self.base_url:
            self.base_url = self.base_url.split(":6022")[0]
        if "/jrpc" in self.base_url:
            self.base_url = self.base_url.replace("/jrpc", "")
        if "/device" in self.base_url:
            self.base_url = self.base_url.split("/device")[0]
            
        self.auth_key = auth_key.strip()
        self.default_device_id = default_device_id.strip()
        self.timeout = 3.0 # Etwas erhöht für Stabilität

    def _post(self, endpoint: str, params: Dict[str, Any], override_device_id: str = None) -> Optional[Dict]:
        url = f"{self.base_url}{endpoint}"
        target_id = override_device_id if override_device_id else self.default_device_id
        
        data = {
            "auth_key": self.auth_key,
            "id": target_id
        }
        data.update(params)
        
        try:
            response = requests.post(url, data=data, timeout=self.timeout)
            if response.status_code == 200:
                try:
                    json_resp = response.json()
                    if json_resp.get("isok") == True:
                        return json_resp.get("data", {})
                    return None
                except ValueError:
                    return None
            return None
        except Exception:
            return None

    def get_status(self, specific_device_id: str = None) -> Dict[str, Any]:
        """
        Holt Status + Online Info.
        """
        data = self._post("/device/status", {}, override_device_id=specific_device_id)
        if not data: 
            return {"_is_online": False} # API Fehler -> Als Offline werten
            
        # WICHTIG: Prüfen ob Gerät online ist
        is_online = data.get("online", False)
        
        source_data = data.get("device_status", data)
            
        normalized = {"_is_online": is_online}
        
        # Nur relevante Switch-Daten übernehmen
        found_switches = False
        for k, v in source_data.items():
            if k.startswith("switch:") or k.startswith("sys"):
                normalized[k] = v
                found_switches = True
                
        # Wenn wir Switches gefunden haben, geben wir diese zurück + Online Status
        # Wenn nicht, geben wir die Rohdaten zurück + Online Status
        if found_switches:
            return normalized
            
        source_data["_is_online"] = is_online
        return source_data

    def set_switch(self, channel: int, turn_on: bool, specific_device_id: str = None) -> bool:
        params = {
            "channel": channel,
            "turn": "on" if turn_on else "off"
        }
        res = self._post("/device/relay/control", params, override_device_id=specific_device_id)
        return res is not None
