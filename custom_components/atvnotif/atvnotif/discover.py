import time
import uuid
import logging

_LOGGER = logging.getLogger(__name__)

def decode_base58_uuid(s: str) -> str:
    """Decodes a Base58 string into a standard UUID string."""
    alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    try:
        num = 0
        for char in s:
            num = num * 58 + alphabet.index(char)
        val = num.to_bytes(16, 'big')
        return str(uuid.UUID(bytes=val))
    except Exception as e:
        _LOGGER.debug("Failed to decode base58 UUID from %s: %s", s, e)
        return None

def discover_devices(timeout: float = 5.0) -> list[dict]:
    """Scans the network for ATV Notifier devices using zeroconf.
    
    Returns a list of dicts, e.g.:
    [
        {
            "name": "Vodafone Vodafone TV 3",
            "host": "192.168.2.104",
            "port": 7878,
            "pairing_code": "60ce69b0-ced7-4872-ba77-66f8dcaf8ba4"
        }
    ]
    """
    try:
        from zeroconf import Zeroconf, ServiceBrowser
    except ImportError:
        _LOGGER.warning("zeroconf library is not installed. Discovery is disabled.")
        return []

    found_devices = []

    class ATVNotifListener:
        def remove_service(self, zc, type_, name):
            pass

        def update_service(self, zc, type_, name):
            pass

        def add_service(self, zc, type_, name):
            info = zc.get_service_info(type_, name)
            if not info:
                return
            
            # Resolve properties
            props = {}
            for k, v in info.properties.items():
                try:
                    # Zeroconf keys/values might be bytes
                    key_str = k.decode("utf-8") if isinstance(k, bytes) else str(k)
                    val_str = v.decode("utf-8") if isinstance(v, bytes) else str(v)
                    props[key_str] = val_str
                except Exception:
                    pass

            name_attr = props.get("n", info.server.split(".")[0])
            base58_uuid = props.get("i")
            pairing_code = decode_base58_uuid(base58_uuid) if base58_uuid else None

            # Get host address
            host = None
            if info.addresses:
                import socket
                # Convert first address to string
                host = socket.inet_ntoa(info.addresses[0])

            if host:
                found_devices.append({
                    "name": name_attr,
                    "host": host,
                    "port": info.port or 7878,
                    "pairing_code": pairing_code
                })

    zc = Zeroconf()
    listener = ATVNotifListener()
    browser = ServiceBrowser(zc, "_atvnotif._tcp.local.", listener)
    
    time.sleep(timeout)
    zc.close()

    return found_devices
