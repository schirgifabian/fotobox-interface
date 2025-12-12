import streamlit as st
import time
import uuid
import hashlib
import requests
import json
import os

# --- KONFIGURATION ---
TOKEN_FILE = "tokens.json"

# --- KLASSE ---
class AqaraClient:
    def __init__(self):
        # Daten aus secrets.toml laden
        self.app_id = st.secrets["aqara"]["app_id"]
        self.key_id = st.secrets["aqara"]["key_id"]
        self.app_secret = st.secrets["aqara"]["app_secret"]
        self.root_url = "https://open-ger.aqara.com/v3.0/open"
        
        # Dynamische Tokens laden
        self.tokens = self._load_tokens()

    def _load_tokens(self):
        if not os.path.exists(TOKEN_FILE):
            st.error(f"❌ Datei '{TOKEN_FILE}' fehlt!")
            return {}
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)

    def _save_tokens(self, access_token, refresh_token):
        self.tokens["access_token"] = access_token
        self.tokens["refresh_token"] = refresh_token
        with open(TOKEN_FILE, "w") as f:
            json.dump(self.tokens, f)

    def _generate_headers(self, access_token=None):
        nonce = str(uuid.uuid4().hex)
        timestamp = str(int(time.time() * 1000))
        
        # Signatur erstellen
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
        """Erneuert das Token automatisch"""
        url = f"{self.root_url}/auth/refreshToken"
        current_refresh = self.tokens.get("refresh_token")
        
        if not current_refresh:
            st.error("Kein Refresh Token gefunden!")
            return False

        headers = self._generate_headers(access_token=None)
        payload = {"refreshToken": current_refresh}
        
        try:
            r = requests.post(url, headers=headers, json=payload)
            data = r.json()
            if data["code"] == 0:
                new_acc = data["result"]["accessToken"]
                new_ref = data["result"]["refreshToken"]
                self._save_tokens(new_acc, new_ref)
                print("♻️ Token erfolgreich erneuert")
                return True
            else:
                st.error(f"Refresh fehlgeschlagen: {data}")
                return False
        except Exception as e:
            st.error(f"Netzwerkfehler: {e}")
            return False

    def send_request(self, endpoint, payload):
        """Sendet Anfrage und kümmert sich um Fehler 108"""
        url = f"{self.root_url}{endpoint}"
        
        # 1. Versuch
        headers = self._generate_headers(self.tokens.get("access_token"))
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        
        # Fehler 108 = Token abgelaufen
        if data.get("code") == 108:
            print("⚠️ Token abgelaufen. Starte Refresh...")
            if self._refresh_token():
                # 2. Versuch mit neuem Token
                headers = self._generate_headers(self.tokens.get("access_token"))
                response = requests.post(url, headers=headers, json=payload)
                data = response.json()
        
        return data

    def toggle_plug(self, turn_on: bool):
        """Steuert deine spezifische Steckdose"""
        val = "1" if turn_on else "0"
        
        # Lade IDs aus secrets
        dev_id = st.secrets["aqara"]["device_id"]
        res_id = st.secrets["aqara"]["resource_id"]

        payload = {
            "resources": [
                {"subjectId": dev_id, "resourceId": res_id, "value": val}
            ]
        }
        res = self.send_request("/api/resource/update", payload)
        return res

# --- STREAMLIT GUI ---
st.title("💡 Aqara Smart Plug Control")

aqara = AqaraClient()

col1, col2 = st.columns(2)

with col1:
    if st.button("Strom AN 🟢"):
        res = aqara.toggle_plug(True)
        if res.get("code") == 0:
            st.success("Steckdose eingeschaltet!")
        else:
            st.error(f"Fehler: {res}")

with col2:
    if st.button("Strom AUS 🔴"):
        res = aqara.toggle_plug(False)
        if res.get("code") == 0:
            st.warning("Steckdose ausgeschaltet!")
        else:
            st.error(f"Fehler: {res}")
