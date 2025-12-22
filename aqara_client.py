import time
import uuid
import hashlib
import requests
import json
import os
import streamlit as st
from typing import Optional, Dict, Tuple, Any

TOKEN_FILE = "tokens.json"

class AqaraClient:
    def __init__(self) -> None:
        try:
            self.app_id: str = st.secrets["aqara"]["app_id"]
            self.key_id: str = st.secrets["aqara"]["key_id"]
            self.app_secret: str = st.secrets["aqara"]["app_secret"]
        except KeyError as e:
            st.error(f"Aqara Secrets fehlen: {e}")
            raise e
        
        self.root_url = "https://open-ger.aqara.com/v3.0/open"
        self.tokens: Dict[str, str] = self._load_tokens()
        
        if not self.tokens.get("access_token"):
            print("⚠️ Keine Tokens gefunden. Versuche initialen Login...")
            self._get_new_token()

    def _load_tokens(self) -> Dict[str, str]:
        if not os.path.exists(TOKEN_FILE):
            return {}
        try:
            with open(TOKEN_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_tokens(self, access_token: str, refresh_token: str) -> None:
        self.tokens["access_token"] = access_token
        self.tokens["refresh_token"] = refresh_token
        try:
            with open(TOKEN_FILE, "w") as f:
                json.dump(self.tokens, f)
        except Exception as e:
            print(f"Fehler beim Speichern der Tokens: {e}")

    def _generate_headers(self, access_token: Optional[str] = None) -> Dict[str, str]:
        nonce = uuid.uuid4().hex
        timestamp = str(int(time.time() * 1000))
        
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

    def _request_with_retry(self, url: str, headers: Dict, payload: Dict, retries: int = 3) -> Dict[str, Any]:
        """Hilfsfunktion: Führt Request mit Exponential Backoff aus (3.B)"""
        for i in range(retries):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=5)
                # Bei 5xx Server Errors auch retryen, sonst json decoden
                if 500 <= response.status_code < 600:
                    raise requests.exceptions.RequestException(f"Server Error {response.status_code}")
                return response.json()
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                wait_time = 2 ** i # 1s, 2s, 4s...
                print(f"Request Error ({e}). Retry in {wait_time}s...")
                time.sleep(wait_time)
        
        return {"code": -1, "message": "Max retries exceeded"}

    def _get_new_token(self) -> bool:
        url = f"{self.root_url}/auth/token"
        headers = self._generate_headers(access_token=None)
        payload = {"intent": 0}
        
        data = self._request_with_retry(url, headers, payload)
        
        if data.get("code") == 0:
            print("✅ Neuer Token erfolgreich empfangen.")
            res = data["result"]
            self._save_tokens(res["accessToken"], res["refreshToken"])
            return True
        else:
            print(f"❌ Fehler beim Token-Holen: {data}")
            return False

    def _refresh_token(self) -> bool:
        url = f"{self.root_url}/auth/refreshToken"
        current_refresh = self.tokens.get("refresh_token")
        
        if not current_refresh:
            return self._get_new_token()

        headers = self._generate_headers(access_token=None)
        payload = {"refreshToken": current_refresh}
        
        data = self._request_with_retry(url, headers, payload)
        
        if data.get("code") == 0:
            res = data["result"]
            self._save_tokens(res["accessToken"], res["refreshToken"])
            return True
        
        print("Refresh fehlgeschlagen, versuche neuen Token...")
        return self._get_new_token()

    def _post_request(self, endpoint: str, payload: Dict) -> Dict[str, Any]:
        url = f"{self.root_url}{endpoint}"
        
        if not self.tokens.get("access_token"):
            self._get_new_token()

        acc_token = self.tokens.get("access_token")
        headers = self._generate_headers(acc_token)
        
        data = self._request_with_retry(url, headers, payload)

        # Fehler 108: Token Expired -> Refresh & Retry
        if data.get("code") == 108:
            print("🔄 Token abgelaufen (Code 108). Refresh...")
            if self._refresh_token():
                acc_token = self.tokens.get("access_token")
                headers = self._generate_headers(acc_token)
                data = self._request_with_retry(url, headers, payload)
        
        return data

    def get_socket_state(self, device_id: str, resource_id: str = "4.1.85") -> Tuple[str, Dict]:
        payload = {
            "resources": [{"subjectId": device_id, "resourceId": resource_id}]
        }
        data = self._post_request("/api/resource/query", payload)
        
        val = None
        try:
            result_list = data.get("result", [])
            if result_list:
                val = result_list[0].get("value")
        except Exception:
            pass
            
        if val is None:
            return "unknown", data

        value_str = str(val).lower()
        if value_str in ("1", "true", "on"):
            return "on", data
        if value_str in ("0", "false", "off"):
            return "off", data
            
        return "unknown", data

    def switch_socket(self, device_id: str, turn_on: bool, resource_id: str = "4.1.85", mode: str = "state") -> Dict:
        value = "2" if mode == "toggle" else ("1" if turn_on else "0")
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
