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
            # .strip() entfernt versehentliche Leerzeichen beim Laden
            self.app_id: str = str(st.secrets["aqara"]["app_id"]).strip()
            self.key_id: str = str(st.secrets["aqara"]["key_id"]).strip()
            self.app_secret: str = str(st.secrets["aqara"]["app_secret"]).strip()
        except KeyError as e:
            st.error(f"Aqara Secrets fehlen: {e}")
            raise e
        
        self.root_url = "https://open-ger.aqara.com/v3.0/open"
        self.tokens: Dict[str, str] = self._load_tokens()
        
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
            # WICHTIG: API erwartet oft 'Accesstoken' (Case sensitive signature check)
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
        for i in range(retries):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=10)
                if 500 <= response.status_code < 600:
                    raise requests.exceptions.RequestException(f"Server Error {response.status_code}")
                return response.json()
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                wait_time = 2 ** i 
                print(f"Request Error ({e}). Retry in {wait_time}s...")
                time.sleep(wait_time)
        return {"code": -1, "message": "Max retries exceeded"}

    def _refresh_token(self) -> bool:
        print("🔄 Refresh Token...")
        current_refresh = self.tokens.get("refresh_token")
        if not current_refresh:
            return False

        url = f"{self.root_url}/api"
        headers = self._generate_headers(access_token=None)
        payload = {
            "intent": "config.auth.refreshToken",
            "data": {"refreshToken": current_refresh}
        }
        data = self._request_with_retry(url, headers, payload)
        
        if data.get("code") == 0:
            try:
                res = data.get("result")
                if isinstance(res, list) and res: res = res[0]
                new_acc = res.get("accessToken")
                new_ref = res.get("refreshToken")
                if new_acc and new_ref:
                    self._save_tokens(new_acc, new_ref)
                    return True
            except Exception:
                pass
        return False

    def _post_request(self, endpoint: str, payload: Dict) -> Dict[str, Any]:
        url = f"{self.root_url}{endpoint}"
        acc_token = self.tokens.get("access_token")
        
        if not acc_token:
            if self._refresh_token(): acc_token = self.tokens.get("access_token")
            else: return {"code": 108, "message": "No token available"}

        headers = self._generate_headers(acc_token)
        data = self._request_with_retry(url, headers, payload)

        if data.get("code") == 108: # Token expired
            if self._refresh_token():
                acc_token = self.tokens.get("access_token")
                headers = self._generate_headers(acc_token)
                data = self._request_with_retry(url, headers, payload)
        
        return data

    def get_socket_state(self, device_id: str, resource_id: str = "4.1.85") -> Tuple[str, Dict]:
        device_id = device_id.strip() # Safety trim
        payload = {
            "intent": "query.resource.value",
            "data": {
                "resources": [{"subjectId": device_id, "resourceId": resource_id}]
            }
        }
        data = self._post_request("/api", payload)
        
        val = None
        try:
            res = data.get("result", [])
            if res and isinstance(res, list): val = res[0].get("value")
        except Exception: pass
            
        if val is None: return "unknown", data

        # Aqara sendet Strings "1"/"0"
        value_str = str(val).lower()
        if value_str in ("1", "true", "on"): return "on", data
        if value_str in ("0", "false", "off"): return "off", data
            
        return "unknown", data

    def switch_socket(self, device_id: str, turn_on: bool, resource_id: str = "4.1.85", mode: str = "state") -> Dict:
        # Wert MUSS ein String sein ("0" oder "1"), genau wie im Debugger
        value = "2" if mode == "toggle" else ("1" if turn_on else "0")
        device_id = device_id.strip() # Wichtig: Leerzeichen entfernen
        
        # Standard V3 Struktur
        payload = {
            "intent": "write.resource.device",
            "data": [
                {
                    "subjectId": device_id,
                    "resources": [
                        {
                            "resourceId": resource_id,
                            "value": value
                        }
                    ]
                }
            ]
        }
        
        print(f"Sende an Aqara: {json.dumps(payload)}") # Debug Log im Terminal
        return self._post_request("/api", payload)
