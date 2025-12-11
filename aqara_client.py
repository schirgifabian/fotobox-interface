# aqara_client.py

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
        self.base_url = f"https://open-{region}.aqara.com/v3.0/open/api"

    def _generate_headers(self, access_token=None):
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

    def _query_resource_value(self, access_token, device_id, resource_ids):
        if isinstance(resource_ids, str):
            resource_ids = [resource_ids]

        url = self.base_url
        headers = self._generate_headers(access_token)

        payload = {
            "intent": "query.resource.value",
            "data": {
                "resources": [
                    {
                        "subjectId": device_id,
                        "resourceIds": resource_ids,
                    }
                ]
            },
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            return response.json()
        except Exception as e:
            return {"code": -1, "message": str(e)}

    def get_socket_state(self, access_token, device_id, resource_id="4.1.85"):
        data = self._query_resource_value(access_token, device_id, resource_id)

        if data.get("code") != 0:
            return "unknown", data

        result = data.get("result")
        value = None

        if isinstance(result, list):
            for item in result:
                if item.get("resourceId") == resource_id and "value" in item:
                    value = item["value"]
                    break
        elif isinstance(result, dict):
            for item in result.get("data", []):
                if item.get("resourceId") == resource_id and "value" in item:
                    value = item["value"]
                    break
                for r in item.get("resources", []):
                    if r.get("resourceId") == resource_id and "value" in r:
                        value = r["value"]
                        break

        if value is None:
            return "unknown", data

        value_str = str(value).lower()
        if value_str in ("1", "true", "on"):
            return "on", data
        if value_str in ("0", "false", "off"):
            return "off", data

        return "unknown", data

    def switch_socket(
        self,
        access_token,
        device_id,
        turn_on: bool,
        resource_id="4.1.85",
        mode: str = "state",
    ):
        url = self.base_url
        headers = self._generate_headers(access_token)

        if mode == "toggle":
            value = "2"
        else:
            value = "1" if turn_on else "0"

        payload = {
            "intent": "write.resource.device",
            "data": [
                {
                    "subjectId": device_id,
                    "resources": [
                        {
                            "resourceId": resource_id,
                            "value": value,
                        }
                    ],
                }
            ],
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            return response.json()
        except Exception as e:
            return {"code": -1, "message": str(e)}
