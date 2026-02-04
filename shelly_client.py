import requests
import json
from typing import Dict, Any, Optional

class ShellyClient:
    def __init__(self, cloud_url: str, auth_key: str, default_device_id: str):
        # Basis-URL bereinigen
        self.base_url = cloud_url.strip().rstrip("/")
        if ":6022" in self.base_url:
            self.base_url = self.base_url.split(":6022")[0]
        if "/jrpc" in self.base_url:
            self.base_url = self.base_url.replace("/jrpc", "")
        if "/device" in self.base_url:
            self.base_url = self.base_url.split("/device")[0]
            
        self.auth_key = auth_key.strip()
        self.default_device_id = default_device_id.strip()
        self.timeout = 7.0

    def _post(self, endpoint: str, params: Dict[str, Any], override_device_id: str = None) -> Optional[Dict]:
        url = f"{self.base_url}{endpoint}"
        target_id = override_device_id if override_device_id else self.default_device_id
        
        # Payload Grundstruktur
        payload = {
            "auth_key": self.auth_key,
            "id": target_id
        }
        payload.update(params)
        
        try:
            # WICHTIG: RPC Endpunkte benötigen JSON, andere Form-Data
            if "/rpc" in endpoint:
                # Wir stellen sicher, dass 'params' innerhalb von RPC ein echtes Objekt ist, kein String
                if "params" in payload and isinstance(payload["params"], str):
                    try:
                        payload["params"] = json.loads(payload["params"])
                    except:
                        pass
                response = requests.post(url, json=payload, timeout=self.timeout)
            else:
                response = requests.post(url, data=payload, timeout=self.timeout)

            if response.status_code == 200:
                json_resp = response.json()
                if json_resp.get("isok"):
                    return json_resp.get("data", {})
            return None
        except Exception as e:
            print(f"Shelly API Fehler: {e}")
            return None

    def get_status(self, specific_device_id: str = None) -> Dict[str, Any]:
        """Holt den Status über den klassischen Endpunkt."""
        data = self._post("/device/status", {}, override_device_id=specific_device_id)
        if not data: 
            return {"_is_online": False}
            
        is_online = data.get("online", False)
        source_data = data.get("device_status", data)
        
        normalized = {"_is_online": is_online}
        # Extrahiere Schalter- und Systemdaten
        for k, v in source_data.items():
            if k.startswith("switch:") or k.startswith("sys") or k.startswith("input:"):
                normalized[k] = v
        return normalized

    def set_switch(self, channel: int, turn_on: bool, specific_device_id: str = None) -> bool:
        """Schaltet das Relais (Gen1/Gen2 kompatibel)."""
        params = {"channel": channel, "turn": "on" if turn_on else "off"}
        return self._post("/device/relay/control", params, override_device_id=specific_device_id) is not None

    def set_rgb_color(self, red: int, green: int, blue: int, brightness: int = 100, specific_device_id: str = None) -> bool:
        """
        Setzt die Farbe des LED-Rings (Shelly Plus Plug S) via RPC.
        """
        rpc_params = {
            "config": {
                "leds": {
                    "mode": "switch",
                    "colors": {
                        "switch:0": {
                            "on": {"rgb": [red, green, blue], "brightness": brightness},
                            "off": {"rgb": [red, green, blue], "brightness": brightness}
                        }
                    }
                }
            }
        }
        
        # RPC Payload für Gen2 Cloud API
        params = {
            "method": "PLUG_UI.SetConfig",
            "params": rpc_params  # Hier als Dictionary übergeben
        }
        return self._post("/device/rpc", params, override_device_id=specific_device_id) is not None
