# shelly_client.py
import requests
import time
from typing import Dict, Any, Optional

class ShellyClient:
    def __init__(self, cloud_url: str, auth_key: str, device_id: str):
        # URL Bereinigung: Wir wollen https://shelly-233-eu.shelly.cloud ohne Ports/Pfade
        self.base_url = cloud_url.strip().rstrip("/")
        if ":6022" in self.base_url:
            self.base_url = self.base_url.split(":6022")[0]
        if "/jrpc" in self.base_url:
            self.base_url = self.base_url.replace("/jrpc", "")
            
        self.auth_key = auth_key.strip()
        self.device_id = device_id.strip()
        self.timeout = 10 

    def _post(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict]:
        """Hilfsfunktion für Requests"""
        url = f"{self.base_url}{endpoint}"
        
        # Standard Parameter für alle Cloud Calls
        data = {
            "auth_key": self.auth_key,
            "id": self.device_id
        }
        data.update(params)
        
        try:
            # Wichtig: data=... sendet Form-Data (kein JSON Body), das will die Cloud
            response = requests.post(url, data=data, timeout=self.timeout)
            
            if response.status_code == 200:
                json_resp = response.json()
                if json_resp.get("isok") == True:
                    return json_resp.get("data", {})
                else:
                    print(f"Shelly API Error: {json_resp.get('errors')}")
            elif response.status_code == 401:
                print("Shelly Auth Error (401): Check Key or Rate Limit!")
            else:
                print(f"Shelly HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"Shelly Connection Error: {e}")
            
        return None

    def get_status(self) -> Dict[str, Any]:
        """
        Holt den Status via /device/status.
        Das ist viel stabiler als RPC, da es den Cache der Cloud nutzt.
        """
        # Wir holen den Cloud-Status. Für Gen4 Geräte packt die Cloud
        # den echten Gerätestatus in das Feld "device_status".
        data = self._post("/device/status", {})
        
        if not data:
            return {}
            
        # Prüfen ob Gerät online ist
        if not data.get("online", False):
            # Optional: Man könnte hier leere Daten zurückgeben, 
            # aber wir geben zurück was wir haben (cached values)
            pass

        # Gen2/3/4 Status versteckt sich oft hier:
        if "device_status" in data:
            return data["device_status"]
            
        return data

    def set_switch(self, switch_id: int, turn_on: bool) -> bool:
        """
        Schaltet via /device/relay/control.
        Das ist der 'Legacy Wrapper', der aber auch für Gen4 funktioniert 
        und einfacher ist als RPC.
        """
        params = {
            "channel": switch_id,
            "turn": "on" if turn_on else "off"
        }
        
        # Sende Befehl
        res = self._post("/device/relay/control", params)
        return res is not None
