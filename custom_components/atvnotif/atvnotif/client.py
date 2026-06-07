import os
import json
import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class ATVNotifier:
    """Client class to communicate and send encrypted notifications to Android TV Notifier."""

    def __init__(self, host: str, pairing_code: str, port: int = 7878):
        self.host = host
        self.port = port
        self.pairing_code = pairing_code
        self.key = self._derive_key(pairing_code)

    def _derive_key(self, pairing_code: str) -> bytes:
        """Derives the 32-byte AES key from the pairing code by reversing and repeating it."""
        cleaned = pairing_code.replace("-", "")
        reversed_code = cleaned[::-1]
        padded = (reversed_code * 32)[:32]
        return padded.encode("utf-8")

    def encrypt_payload(self, data: dict) -> bytes:
        """Encrypts the JSON payload using AES-256-GCM with a random 12-byte IV."""
        json_payload = json.dumps(data)
        return self.encrypt_raw_string(json_payload)

    def encrypt_raw_string(self, text: str) -> bytes:
        """Encrypts a raw string using AES-256-GCM with a random 12-byte IV."""
        aesgcm = AESGCM(self.key)
        iv = os.urandom(12)
        ciphertext = aesgcm.encrypt(iv, text.encode("utf-8"), None)
        return iv + ciphertext

    def decrypt_payload(self, encrypted_data: bytes) -> str:
        """Decrypts a response payload using AES-256-GCM."""
        if len(encrypted_data) < 28:
            raise ValueError("Encrypted data too short")
        iv = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        aesgcm = AESGCM(self.key)
        decrypted = aesgcm.decrypt(iv, ciphertext, None)
        return decrypted.decode("utf-8")

    async def async_get_apps(self) -> list[dict]:
        """Retrieves a list of installed apps on the TV.

        Returns a list of dicts: [{"n": "App Name", "p": "com.package.name"}, ...]
        """
        url = f"http://{self.host}:{self.port}/apps"
        encrypted_body = self.encrypt_payload({})
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                content=encrypted_body,
                headers={"Content-Type": "application/octet-stream"},
                timeout=10.0,
            )
            response.raise_for_status()
            decrypted_resp = self.decrypt_payload(response.content)
            return json.loads(decrypted_resp)

    async def async_get_info(self) -> str:
        """Retrieves TV info (usually the device name)."""
        url = f"http://{self.host}:{self.port}/info"
        encrypted_body = self.encrypt_payload({})
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                content=encrypted_body,
                headers={"Content-Type": "application/octet-stream"},
                timeout=10.0,
            )
            response.raise_for_status()
            return response.text

    async def async_open_app(self, package_name: str) -> bool:
        """Opens an application on the TV by package name."""
        url = f"http://{self.host}:{self.port}/open"
        encrypted_body = self.encrypt_raw_string(package_name)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                content=encrypted_body,
                headers={"Content-Type": "application/octet-stream"},
                timeout=10.0,
            )
            response.raise_for_status()
            return response.text.strip().lower() == "true"


    async def async_notify(
        self,
        message: str,
        title: str = None,
        sender: str = "Home Assistant",
        duration: int = 5,
        position: int = 0,
        priority: int = 1,
        bg_color: int = None,
        title_color: int = None,
        msg_color: int = None,
        title_size: float = None,
        msg_size: float = None,
        icon: str = None,
        small_icon: str = None,
        big_image: str = None,
        interact: bool = False,
        notif_sound: bool = True,
        wakeup: bool = True,
    ) -> httpx.Response:
        """Sends an encrypted notification payload asynchronously to the TV."""
        payload = {
            "msg": message,
            "src": sender,
            "duration": duration,
            "position": position,
            "prio": priority,
            "interact": interact,
            "notifSound": notif_sound,
            "wakeup": wakeup,
        }
        if title:
            payload["title"] = title
        if bg_color is not None:
            payload["bgColor"] = bg_color
        if title_color is not None:
            payload["titleColor"] = title_color
        if msg_color is not None:
            payload["msgColor"] = msg_color
        if title_size is not None:
            payload["titleSize"] = title_size
        if msg_size is not None:
            payload["msgSize"] = msg_size
        if icon:
            payload["icon"] = icon
        if small_icon:
            payload["smallIcon"] = small_icon
        if big_image:
            payload["bigImg"] = big_image

        encrypted_body = self.encrypt_payload(payload)
        url = f"http://{self.host}:{self.port}/notify"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                content=encrypted_body,
                headers={"Content-Type": "application/octet-stream"},
                timeout=10.0,
            )
            response.raise_for_status()
            return response
