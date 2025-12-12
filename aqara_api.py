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
        # 1. Config direkt aus secrets holen
        self.app_id = st.secrets["aqara"]["app_id"]
        self.key_id = st.secrets["aqara"]["key_id"]
        self.app_secret = st.secrets["aqara"]["app_secret"]
        # Basis URL
        self.root_url = "https://open-ger.aqara.com/v3.0/open"
        
        # 2. Token laden (oder leere Struktur wenn neue Datei)
        self.tokens = self._load_tokens()

    def _load_tokens(self):
        if not os.path.exists(TOKEN_FILE):
            # Falls Datei fehlt, leeres Gerüst
            return {"access_token": "", "refresh_token": ""}
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
        nonce = str(uuid.uuid4().hex)
        timestamp = str(int(time.time() * 1000))
        
        sign_parts = []
        if access_token:
            sign_parts.append(f"AccessToken={access_token}")
        
        sign_parts.append(f"AppId={self.app_id}")
        sign_parts.append(f"KeyId={self.key_id}")
        sign_parts.append(f"Nonce={nonce}")
        sign_parts.append(f"Time={timestamp}")
        
        raw_str = "&".join(sign_parts) + self.app_secret
        sign = hashlib.md5(raw_str.encode('utf-8')).hexdigest().lower()

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

    def _refresh_token(self):
        url = f"{self.root_url}/auth/refreshToken"
        current_refresh = self.tokens.get("refresh_token")
        
        if not current_refresh:
            print("❌ Kein Refresh Token vorhanden!")
            return False

        headers = self._generate_headers(access_token=None)
        payload = {"refreshToken": current_refresh}
        
        try:
            r = requests.post(url, headers=headers, json=payload)
            data = r.json()
            if data["code"] == 0:
                self._save_tokens(data["result"]["accessToken"], data["result"]["refreshToken"])
                return True
            return False
        except:
            return False

    def _post_request(self, endpoint, payload):
        """Wrapper für Auto-Refresh"""
        url = f"{self.root_url}{endpoint}"
        
        # Try 1
        headers = self._generate_headers(self.tokens.get("access_token"))
        try:
            response = requests.post(url, headers=headers, json=payload)
            data = response.json()
        except Exception as e:
            return {"code": -1, "message": str(e)}

        # Fehler 108 -> Token erneuern
        if data.get("code") == 108:
            print("🔄 Token Refresh...")
            if self._refresh_token():
                # Try 2
                headers = self._generate_headers(self.tokens.get("access_token"))
                response = requests.post(url, headers=headers, json=payload)
                data = response.json()
        
        return data

    # --- METHODEN FÜR DEINE APP.PY ---

    def get_socket_state(self, device_id, resource_id="4.1.85"):
        # Achtung: Kein access_token Parameter mehr nötig!
        payload = {
            "resources": [{"subjectId": device_id, "resourceId": resource_id}]
        }
        data = self._post_request("/api/resource/query", payload)
        
        state = "unknown"
        if data.get("code") == 0 and data.get("result"):
            val = data["result"][0]["value"]
            if val == "1": state = "on"
            elif val == "0": state = "off"
            
        return state, data

    def switch_socket(self, device_id, turn_on: bool, resource_id="4.1.85", mode="state"):
        # Achtung: Kein access_token Parameter mehr nötig!
        val = "1" if turn_on else "0"
        payload = {
            "resources": [{"subjectId": device_id, "resourceId": resource_id, "value": val}]
        }
        return self._post_request("/api/resource/update", payload)
