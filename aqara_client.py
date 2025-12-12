import time
import uuid
import hashlib
import requests
import json
import os
import streamlit as st

TOKEN_FILE = "tokens.json"

class AqaraClient:
    def __init__(self):
        # 1. Wir laden die statischen Configs direkt hier aus den Secrets
        self.app_id = st.secrets["aqara"]["app_id"]
        self.key_id = st.secrets["aqara"]["key_id"]
        self.app_secret = st.secrets["aqara"]["app_secret"]
        
        # Basis URL (ohne /api am Ende, damit wir auch /auth erreichen)
        self.root_url = "https://open-ger.aqara.com/v3.0/open"
        
        # 2. Wir laden das Token-File beim Start
        self.tokens = self._load_tokens()

    def _load_tokens(self):
        if not os.path.exists(TOKEN_FILE):
            return {}
        try:
            with open(TOKEN_FILE, "r") as f:
                return json.load(f)
        except:
            return {}

    def _save_tokens(self, access_token, refresh_token):
        self.tokens["access_token"] = access_token
        self.tokens["refresh_token"] = refresh_token
        with open(TOKEN_FILE, "w") as f:
            json.dump(self.tokens, f)

    def _generate_headers(self, access_token=None):
        nonce = uuid.uuid4().hex
        timestamp = str(int(time.time() * 1000))

        # --- Signatur Erstellung (Deine bestehende Logik) ---
        sign_params = {
            "Appid": self.app_id,
            "Keyid": self.key_id,
            "Nonce": nonce,
            "Time": timestamp,
        }
        if access_token:
            sign_params["Accesstoken"] = access_token

        sign_str = "&".join(f"{k}={sign_params[k]}" for k in sorted(sign_params.keys()))
        sign_str += self.app_secret
        sign = hashlib.md5(sign_str.lower().encode("utf-8")).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "Appid": self.app_id,
            "Keyid": self.key_id,
            "Nonce": nonce,
            "Time": timestamp,
            "Sign": sign,
            "Lang": "de",
        }
        if access_token:
            headers["Accesstoken"] = access_token
        return headers

    def _refresh_token(self):
        url = f"{self.root_url}/auth/refreshToken"
        current_refresh = self.tokens.get("refresh_token")
        
        if not current_refresh:
            return False

        headers = self._generate_headers(access_token=None)
        payload = {"refreshToken": current_refresh}
        
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=10)
            data = r.json()
            if data["code"] == 0:
                # Neues Token speichern
                new_acc = data["result"]["accessToken"]
                new_ref = data["result"]["refreshToken"]
                self._save_tokens(new_acc, new_ref)
                return True
            return False
        except Exception as e:
            print(f"Refresh Error: {e}")
            return False

    def _post_request(self, endpoint, payload):
        """Intelligente Sendemethode mit Retry"""
        url = f"{self.root_url}{endpoint}"
        
        # Versuch 1
        acc_token = self.tokens.get("access_token")
        headers = self._generate_headers(acc_token)
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            data = response.json()
        except Exception as e:
            return {"code": -1, "message": str(e)}

        # Fehler 108: Token Expired -> Wir versuchen einen Refresh
        if data.get("code") == 108:
            print("⚠️ Token abgelaufen (Code 108). Versuche Refresh...")
            if self._refresh_token():
                # Refresh hat geklappt -> Token neu laden und Versuch 2
                acc_token = self.tokens.get("access_token")
                headers = self._generate_headers(acc_token)
                try:
                    response = requests.post(url, headers=headers, json=payload, timeout=5)
                    data = response.json()
                except Exception as e:
                    return {"code": -1, "message": str(e)}
            else:
                return {"code": -1, "message": "Token Refresh fehlgeschlagen. Bitte manuell prüfen."}
        
        return data

    def get_socket_state(self, device_id, resource_id="4.1.85"):
        # Access Token wird jetzt intern gehandhabt -> Parameter entfernt
        payload = {
            "resources": [{"subjectId": device_id, "resourceId": resource_id}]
        }
        
        # Aufruf über den intelligenten Wrapper
        data = self._post_request("/api/resource/query", payload)
        
        if data.get("code") != 0:
            return "unknown", data

        # Ergebnis parsen (wie in deiner alten Logik)
        val = None
        try:
            result_list = data.get("result", [])
            if result_list and len(result_list) > 0:
                val = result_list[0].get("value")
        except:
            pass
            
        if val is None:
            return "unknown", data

        # Wert normalisieren
        value_str = str(val).lower()
        if value_str in ("1", "true", "on"):
            return "on", data
        if value_str in ("0", "false", "off"):
            return "off", data
            
        return "unknown", data

    def switch_socket(self, device_id, turn_on: bool, resource_id="4.1.85", mode="state"):
        # Access Token wird jetzt intern gehandhabt -> Parameter entfernt
        
        # Toggle Logik aus deinem alten Skript übernommen
        if mode == "toggle":
            value = "2" # Manche Plugs nutzen Toggle Logik
        else:
            value = "1" if turn_on else "0"

        payload = {
            "resources": [
                {
                    "subjectId": device_id,
                    "resourceId": resource_id,
                    "value": value
                }
            ]
        }
        
        return self._post_request("/api/resource/update", payload)
