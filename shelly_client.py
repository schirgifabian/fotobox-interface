# shelly_client.py
import requests
import time
from typing import Dict, Any, Optional

class ShellyClient:
    def __init__(self, cloud_url: str, auth_key: str, device_id: str):
        self.cloud_url = cloud_url
        self.auth_key = auth_key
        self.device_id = device_id
        # Timeout etwas höher, da Cloud-Calls länger dauern können als lokale
        self.timeout = 10 

    def _send_cloud_command(self, device_method: str, device_params: Dict[str, Any] = None) -> Optional[Dict]:
        """
        Sendet einen Befehl an die Shelly Cloud, die ihn an das Gerät weiterleitet.
        Wir nutzen die 'Shelly.Call' Methode der Cloud API.
        """
        if device_params is None:
            device_params = {}
            
        # Der Payload für die Cloud. 
        # Wir rufen 'Shelly.Call' auf der Cloud auf, um eine Methode AUF dem Gerät auszuführen.
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
            # Wichtig: Headers setzen, sonst mag die API das manchmal nicht
            headers = {"Content-Type": "application/json"}
            response = requests.post(self.cloud_url, json=payload, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            # Fehlerprüfung Cloud-Level
            if "error" in data:
                print(f"Shelly Cloud API Error: {data['error']}")
                return None
                
            # Das eigentliche Ergebnis vom Gerät steckt in result -> data
            # Struktur Cloud Antwort: { "result": { "data": { ...Geräteantwort... } } }
            if "result" in data and "data" in data["result"]:
                return data["result"]["data"]
            
            return data.get("result", {})

        except requests.exceptions.RequestException as e:
            print(f"Shelly Cloud Connection Error: {e}")
            return None

    def get_status(self) -> Dict[str, Any]:
        """
        Holt den Status aller 4 Switches inklusive Power-Meter.
        """
        # Wir rufen 'Shelly.GetStatus' auf dem Gerät auf
        return self._send_cloud_command("Shelly.GetStatus") or {}

    def set_switch(self, switch_id: int, turn_on: bool) -> bool:
        """Schaltet eine einzelne Dose an oder aus."""
        params = {
            "id": switch_id,
            "on": turn_on
        }
        # Wir rufen 'Switch.Set' auf dem Gerät auf
        resp = self._send_cloud_command("Switch.Set", params)
        return resp is not None
