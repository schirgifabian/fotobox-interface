# shelly_client.py
import requests
from typing import Dict, Any, Optional

class ShellyClient:
    def __init__(self, cloud_url: str, auth_key: str, default_device_id: str):
        self.base_url = cloud_url.strip().rstrip("/")
        # URL Bereinigung
        if ":6022" in self.base_url:
            self.base_url = self.base_url.split(":6022")[0]
        if "/jrpc" in self.base_url:
            self.base_url = self.base_url.replace("/jrpc", "")
        if "/device" in self.base_url:
            self.base_url = self.base_url.split("/device")[0]
            
        self.auth_key = auth_key.strip()
        self.default_device_id = default_device_id.strip()
        
        # Timeout performance optimization
        self.timeout = 2.0 

    def _post(self, endpoint: str, params: Dict[str, Any], override_device_id: str = None) -> Optional[Dict]:
        """
        Sendet Request an Shelly Cloud. 
        Wenn override_device_id gesetzt ist, wird dieses Gerät angesprochen, sonst das Standardgerät.
        """
        url = f"{self.base_url}{endpoint}"
        
        # Wähle die korrekte ID (Plug S oder Power Strip)
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
        """Holt Status. Wenn ID angegeben, dann von spezifischem Gerät."""
        data = self._post("/device/status", {}, override_device_id=specific_device_id)
        if not data: return {}
            
        source_data = data.get("device_status", data)
            
        # Normalisierung: Wir geben nur relevante Switch-Daten zurück
        normalized = {}
        found_switches = False
        
        # Daten flachklopfen für einfachere Verarbeitung
        for k, v in source_data.items():
            if k.startswith("switch:"):
                normalized[k] = v
                found_switches = True
                
        if found_switches: return normalized
        return source_data

    def set_switch(self, channel: int, turn_on: bool, specific_device_id: str = None) -> bool:
        """Schaltet Relay. Wenn ID angegeben, dann auf spezifischem Gerät."""
        params = {
            "channel": channel,
            "turn": "on" if turn_on else "off"
        }
        res = self._post("/device/relay/control", params, override_device_id=specific_device_id)
        return res is not None
