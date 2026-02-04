# shelly_client.py
import requests
from typing import Dict, Any, Optional

class ShellyClient:
    def __init__(self, cloud_url: str, auth_key: str, default_device_id: str):
        # Bereinigung der URL: Wir nutzen primär den rpc endpoint für modernere Gen2/Gen3 Shellys
        self.base_url = cloud_url.strip().rstrip("/")
        if "/jrpc" in self.base_url: self.base_url = self.base_url.replace("/jrpc", "")
        
        self.auth_key = auth_key.strip()
        self.default_device_id = default_device_id.strip()
        self.timeout = 5.0 # Höherer Timeout für Cloud-Latenz

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
                json_resp = response.json()
                if json_resp.get("isok"):
                    return json_resp.get("data", {})
            return None
        except Exception:
            return None

    def get_status(self, specific_device_id: str = None) -> Dict[str, Any]:
        """Holt Status und extrahiert Online-Status sowie Switch-Metriken."""
        data = self._post("/device/status", {}, override_device_id=specific_device_id)
        
        # Grundstruktur für Offline-Geräte
        result = {"_is_online": False}
        if not data:
            return result
            
        is_online = data.get("online", False)
        result["_is_online"] = is_online
        
        # Extrahiere Switch-Daten (apower, output)
        device_status = data.get("device_status", {})
        for k, v in device_status.items():
            if k.startswith("switch:") or k.startswith("input:"):
                result[k] = v
        
        return result

    def set_switch(self, channel: int, turn_on: bool, specific_device_id: str = None) -> bool:
        params = {"channel": channel, "turn": "on" if turn_on else "off"}
        res = self._post("/device/relay/control", params, override_device_id=specific_device_id)
        return res is not None
