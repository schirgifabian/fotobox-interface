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
        # 1. Config aus secrets laden
        try:
            self.app_id = st.secrets["aqara"]["app_id"]
            self.key_id = st.secrets["aqara"]["key_id"]
            self.app_secret = st.secrets["aqara"]["app_secret"]
        except KeyError as e:
            st.error(f"Aqara Secrets fehlen: {e}. Bitte in .streamlit/secrets.toml prüfen.")
            raise e
        
        self.root_url = "https://open-ger.aqara.com/v3.0/open"
        
        # 2. Token laden
        self.tokens = self._load_tokens()
        
        # 3. WICHTIG: Wenn keine Tokens da sind, initial einen neuen holen!
        if not self.tokens.get("access_token"):
            print("⚠️ Keine Tokens gefunden. Versuche initialen Login...")
            self._get_new_token()

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
        try:
            with open(TOKEN_FILE, "w") as f:
                json.dump(self.tokens, f)
        except Exception as e:
            print(f"Fehler beim Speichern der Tokens: {e}")

    def _generate_headers(self, access_token=None):
        nonce = uuid.uuid4().hex
        timestamp = str(int(time.time() * 1000))

        # Signatur Parameter
        sign_params = {
            "Appid": self.app_id,
            "Keyid": self.key_id,
            "Nonce": nonce,
            "Time": timestamp,
        }
        if access_token:
            sign_params["Accesstoken"] = access_token

        # Sortieren und String bauen
        sign_str = "&".join(f"{k}={sign_params[k]}" for k in sorted(sign_params.keys()))
        # Secret direkt anhängen (ohne &)
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

    def _get_new_token(self):
        """Holt einen komplett neuen Token (nicht Refresh)"""
        url = f"{self.root_url}/auth/token"
        headers = self._generate_headers(access_token=None)
        # Intent 0 = Get token for data query & control
        payload = {"intent": 0} 
        
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=10)
            data = r.json()
            if data["code"] == 0:
                print("✅ Neuer Token erfolgreich empfangen.")
                new_acc = data["result"]["accessToken"]
                new_ref = data["result"]["refreshToken"]
                self._save_tokens(new_acc, new_ref)
                return True
            else:
                print(f"❌ Fehler beim Token-Holen: {data}")
                return False
        except Exception as e:
            print(f"Exception bei _get_new_token: {e}")
            return False

    def _refresh_token(self):
        url = f"{self.root_url}/auth/refreshToken"
        current_refresh = self.tokens.get("refresh_token")
        
        if not current_refresh:
            # Wenn wir keinen Refresh Token haben, versuchen wir einen komplett neuen zu holen
            return self._get_new_token()

        headers = self._generate_headers(access_token=None)
        payload = {"refreshToken": current_refresh}
        
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=10)
            data = r.json()
            if data["code"] == 0:
                self._save_tokens(data["result"]["accessToken"], data["result"]["refreshToken"])
                return True
            # Falls Refresh fehlschlägt (z.B. zu alt), versuchen wir neuen Token
            print("Refresh fehlgeschlagen, versuche neuen Token...")
            return self._get_new_token()
        except Exception as e:
            print(f"Refresh Error: {e}")
            return False

    def _post_request(self, endpoint, payload):
        url = f"{self.root_url}{endpoint}"
        
        # Sicherstellen, dass wir einen Token haben
        if not self.tokens.get("access_token"):
            self._get_new_token()

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
            print("🔄 Token abgelaufen (Code 108). Refresh...")
            if self._refresh_token():
                # Refresh hat geklappt -> Versuch 2
                acc_token = self.tokens.get("access_token")
                headers = self._generate_headers(acc_token)
                try:
                    response = requests.post(url, headers=headers, json=payload, timeout=5)
                    data = response.json()
                except Exception as e:
                    return {"code": -1, "message": str(e)}
        
        return data

    def get_socket_state(self, device_id, resource_id="4.1.85"):
        payload = {
            "resources": [{"subjectId": device_id, "resourceId": resource_id}]
        }
        
        data = self._post_request("/api/resource/query", payload)
        
        # Debugging Info in Console
        if data.get("code") != 0:
            print(f"Aqara Error: {data}")
            return "unknown", data

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
        if mode == "toggle":
            value = "2"
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
