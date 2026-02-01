# shelly_client.py
import requests
import time
from typing import Dict, Any, Optional

class ShellyClient:
    def __init__(self, cloud_url: str, auth_key: str, device_id: str):
        self.raw_url = cloud_url.strip()
        self.auth_key = auth_key.strip()
        self.device_id = device_id.strip()
        self.timeout = 10 
        
        # URL Zusammenbauen: Sicherstellen, dass Port und Pfad stimmen
        # Falls der User nur "https://shelly-233-eu.shelly.cloud" eingegeben hat:
        if "6022" not in self.raw_url:
            base = self.raw_url.rstrip("/")
            self.endpoint = f"{base}:6022/jrpc"
        else:
            self.endpoint = self.raw_url

    def _send_cloud_command(self, device_method: str, device_params: Dict[str, Any] = None) -> Optional[Dict]:
        """
        Sendet RPC via Cloud (Shelly.Call).
        """
        if device_params is None:
            device_params = {}
            
        payload = {
            "jsonrpc": "2.0",
            "id": int(time.time()),
            "method": "Shelly.Call",
            "params": {
                "auth": self.auth_key,
                "id": self.device_id,
                "method": device_method,
                "params": device_params
            }
        }
        
        try:
            headers = {"Content-Type": "application/json"}
            # DEBUG: Print URL um sicherzugehen
            # print(f"DEBUG: Sende an {self.endpoint}...")
            
            response = requests.post(self.endpoint, json=payload, headers=headers, timeout=self.timeout)
            
            if response.status_code != 200:
                print(f"Shelly Error HTTP {response.status_code}: {response.text}")
                return None
                
            data = response.json()
            
            # Fehlerprüfung in der JSON Antwort
            if "error" in data:
                print(f"Shelly API Error: {data['error']}")
                return None
                
            # Gen 4 Antwortstruktur: result -> data -> { ... }
            if "result" in data:
                res = data["result"]
                # Manchmal ist 'data' direkt im result, manchmal verschachtelt
                if "data" in res:
                    return res["data"]
                return res
            
            return {}

        except requests.exceptions.RequestException as e:
            print(f"Shelly Connection Error: {e}")
            return None

    def get_status(self) -> Dict[str, Any]:
        """
        Holt den Status via Shelly.GetStatus
        """
        return self._send_cloud_command("Shelly.GetStatus") or {}

    def set_switch(self, switch_id: int, turn_on: bool) -> bool:
        """
        Schaltet Switch via Switch.Set
        """
        params = {
            "id": switch_id,
            "on": turn_on
        }
        # Bei Switch.Set antwortet Shelly oft nur mit null (Erfolg), wenn kein Error kommt.
        resp = self._send_cloud_command("Switch.Set", params)
        return resp is not None
