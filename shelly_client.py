# shelly_client.py
import requests
import json
import time
from typing import Dict, Any, Optional

class ShellyClient:
    def __init__(self, cloud_url: str, auth_key: str, device_id: str):
        # Wir bereinigen die URL: Kein Port 6022, kein /jrpc
        # Ziel: https://shelly-233-eu.shelly.cloud
        clean_url = cloud_url.strip().rstrip("/")
        if ":6022" in clean_url:
            clean_url = clean_url.split(":6022")[0]
        if "/jrpc" in clean_url:
            clean_url = clean_url.replace("/jrpc", "")
            
        self.base_url = clean_url
        self.auth_key = auth_key.strip()
        self.device_id = device_id.strip()
        self.timeout = 10 

    def _send_cloud_request(self, method: str, params: Dict[str, Any] = None) -> Optional[Dict]:
        """
        Sendet einen Request an die offizielle Cloud API (/device/rpc).
        Diese erwartet Form-Data, kein reines JSON-RPC im Body!
        """
        if params is None:
            params = {}
            
        # Der Cloud-Endpunkt für Gen2+ Geräte
        endpoint = f"{self.base_url}/device/rpc"
        
        # Die Cloud API erwartet POST Form-Data Parameter
        payload = {
            "auth_key": self.auth_key,
            "id": self.device_id,
            "method": method,
            "params": json.dumps(params) # Params müssen als JSON-String übergeben werden
        }
        
        try:
            # Wichtig: Kein json=payload nutzen, sondern data=payload (Form Data)
            response = requests.post(endpoint, data=payload, timeout=self.timeout)
            
            if response.status_code != 200:
                print(f"Shelly Cloud HTTP Error {response.status_code}: {response.text}")
                return None
                
            data = response.json()
            
            # Die Antwort enthält meistens direkt die Daten oder ein wrapper objekt
            # Struktur: { "ison": true, ... } oder { "data": { ... } }
            if "data" in data:
                return data["data"]
            return data

        except requests.exceptions.RequestException as e:
            print(f"Shelly Connection Error: {e}")
            return None

    def get_status(self) -> Dict[str, Any]:
        """
        Holt den Status via Shelly.GetStatus
        """
        return self._send_cloud_request("Shelly.GetStatus") or {}

    def set_switch(self, switch_id: int, turn_on: bool) -> bool:
        """
        Schaltet Switch via Switch.Set
        """
        params = {
            "id": switch_id,
            "on": turn_on
        }
        resp = self._send_cloud_request("Switch.Set", params)
        # Wenn wir eine Antwort bekommen, war es meist erfolgreich
        return resp is not None
