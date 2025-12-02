import time
import uuid
import hashlib
import requests
import json

class AqaraClient:
    def __init__(self, app_id, key_id, app_secret, region="ger"):
        self.app_id = app_id
        self.key_id = key_id
        self.app_secret = app_secret
        # Base URL abhängig von der Region (ger = Europa)
        self.base_url = f"https://open-{region}.aqara.com/v3.0/open/api"

    def _generate_headers(self, access_token=None):
        """Erstellt die nötige Signatur für Aqara"""
        nonce = str(uuid.uuid4().hex)
        timestamp = str(int(time.time() * 1000))
        
        # Signatur-Formel von Aqara V3
        sign_str = f"Appid={self.app_id}&Keyid={self.key_id}&Nonce={nonce}&Time={timestamp}{self.app_secret}"
        sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest().lower()

        headers = {
            "Content-Type": "application/json",
            "Appid": self.app_id,
            "Keyid": self.key_id,
            "Nonce": nonce,
            "Time": timestamp,
            "Sign": sign,
            "Lang": "de"
        }
        
        if access_token:
            headers["Accesstoken"] = access_token
            
        return headers

    def get_device_value(self, access_token, device_id, resource_name="temperature"):
        """
        Liest Sensorwerte aus.
        resource_name für Temp-Sensor meist: 'temperature' oder 'humidity'
        """
        url = f"{self.base_url}/resource/query"
        headers = self._generate_headers(access_token)
        
        payload = {
            "resources": [
                {
                    "subjectId": device_id,
                    "resourceId": resource_name
                }
            ]
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            data = response.json()
            
            # Prüfen ob API Success meldet (code 0)
            if data.get("code") == 0 and data.get("result"):
                # Wert extrahieren
                value = data["result"][0]["value"]
                return value
            else:
                return f"Fehler: {data.get('message', 'Unbekannt')}"
        except Exception as e:
            return f"Verbindungsfehler: {str(e)}"

    def switch_socket(self, access_token, device_id, turn_on: bool):
        """
        Schaltet eine Steckdose
        turn_on: True (AN) oder False (AUS)
        """
        url = f"{self.base_url}/resource/update"
        headers = self._generate_headers(access_token)
        
        # Aqara Smart Plugs nutzen meist '4.1.85' (toggle) oder einfach 'toggle'
        # Als Value oft '1' für an, '0' für aus. Das kann variieren je nach Modell!
        state_value = "1" if turn_on else "0"
        
        payload = {
            "resources": [
                {
                    "subjectId": device_id,
                    "resourceId": "toggle", # Falls das nicht geht, '4.1.85' versuchen
                    "value": state_value
                }
            ]
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            return response.json()
        except Exception as e:
            return {"code": -1, "message": str(e)}

