import base64
import logging
import os
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import (
    DOMAIN,
    CONF_IP_ADDRESS,
    CONF_PORT,
    CONF_PAIRING_CODE,
    CONF_ENABLE_APP_LAUNCHER,
    CONF_ENABLE_NOTIFY_ENTITY,
)

try:
    from atvnotif import ATVNotifier, discover_devices, decode_qr_image
except ImportError:
    from .atvnotif import ATVNotifier
    from .atvnotif.discover import discover_devices
    from .atvnotif.qr import decode_qr_image
_LOGGER = logging.getLogger(__name__)


def _parse_color(val):
    """Helper to convert list [R, G, B] to signed ARGB 32-bit integer."""
    if val is None:
        return None
    if isinstance(val, (list, tuple)) and len(val) == 3:
        r, g, b = val
        argb = 4278190080 + (r << 16) + (g << 8) + b
        if argb >= 2147483648:
            argb -= 4294967296
        return argb
    return val


def _get_platforms(entry: ConfigEntry) -> list:
    """Return the list of platforms to load based on entry options."""
    opts = entry.options
    platforms = []
    if opts.get(CONF_ENABLE_NOTIFY_ENTITY, True):
        platforms.append(Platform.NOTIFY)
    if opts.get(CONF_ENABLE_APP_LAUNCHER, True):
        platforms.append(Platform.SELECT)
    return platforms


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Android TV Notifier from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Register custom open_app service (once only)
    if not hass.services.has_service(DOMAIN, "open_app"):
        def get_notifier(host=None, device_id=None, entity_id=None):
            if not hass.data[DOMAIN]:
                raise ValueError("No TV configured")
            config_data = None
            if host:
                for entry_data in hass.data[DOMAIN].values():
                    if entry_data[CONF_IP_ADDRESS] == host:
                        config_data = entry_data
                        break
            elif device_id:
                if isinstance(device_id, (list, tuple)):
                    device_id = device_id[0] if device_id else None
                if device_id:
                    device_reg = dr.async_get(hass)
                    device = device_reg.async_get(device_id)
                    if device:
                        entry_id = next(iter(device.config_entries))
                        config_data = hass.data[DOMAIN].get(entry_id)
            elif entity_id:
                if isinstance(entity_id, (list, tuple)):
                    entity_id = entity_id[0] if entity_id else None
                if entity_id:
                    from homeassistant.helpers import entity_registry as er
                    ent_reg = er.async_get(hass)
                    entity_entry = ent_reg.async_get(entity_id)
                    if entity_entry:
                        entry_id = entity_entry.config_entry_id
                        config_data = hass.data[DOMAIN].get(entry_id)
            if not config_data:
                config_data = next(iter(hass.data[DOMAIN].values()))
            return ATVNotifier(
                config_data[CONF_IP_ADDRESS],
                config_data[CONF_PAIRING_CODE],
                config_data.get(CONF_PORT, 7878),
            )

        async def handle_open_app(call):
            host = call.data.get("host")
            device_id = call.data.get("device_id")
            package_name = call.data["package_name"]
            try:
                notifier = get_notifier(host, device_id)
                await notifier.async_open_app(package_name)
            except Exception as err:
                _LOGGER.error("Failed to open app %s: %s", package_name, err)

        hass.services.async_register(
            DOMAIN,
            "open_app",
            handle_open_app,
            schema=vol.Schema({
                vol.Optional("host"): vol.Maybe(str),
                vol.Optional("device_id"): vol.Maybe(str),
                vol.Required("package_name"): str,
            })
        )

    if not hass.services.has_service(DOMAIN, "notify"):
        async def handle_notify(call):
            host = call.data.get("host")
            device_id = call.data.get("device_id")
            try:
                notifier = get_notifier(host, device_id)
                duration = call.data.get("duration")
                if duration is None:
                    duration = 15
                position = call.data.get("position")
                if position is None:
                    position = 0
                priority = call.data.get("priority")
                if priority is None:
                    priority = 1
                sender = call.data.get("sender")
                interact = call.data.get("interact")
                if interact is None:
                    interact = False
                notif_sound = call.data.get("notif_sound")
                if notif_sound is None:
                    notif_sound = True
                wakeup = call.data.get("wakeup")
                if wakeup is None:
                    wakeup = False

                await notifier.async_notify(
                    message=call.data["message"],
                    title=call.data.get("title"),
                    sender=sender,
                    duration=duration,
                    position=position,
                    priority=priority,
                    bg_color=_parse_color(call.data.get("bg_color")),
                    title_color=_parse_color(call.data.get("title_color")),
                    msg_color=_parse_color(call.data.get("msg_color")),
                    title_size=call.data.get("title_size"),
                    msg_size=call.data.get("msg_size"),
                    icon=call.data.get("icon"),
                    small_icon=call.data.get("small_icon"),
                    big_image=call.data.get("big_image"),
                    interact=interact,
                    notif_sound=notif_sound,
                    wakeup=wakeup,
                )
            except Exception as err:
                _LOGGER.error("Failed to send notification: %s", err)

        hass.services.async_register(
            DOMAIN,
            "notify",
            handle_notify,
            schema=vol.Schema({
                vol.Optional("host"): vol.Maybe(str),
                vol.Optional("device_id"): vol.Maybe(str),
                vol.Required("message"): str,
                vol.Optional("title"): vol.Maybe(str),
                vol.Optional("sender"): vol.Maybe(str),
                vol.Optional("duration", default=15): vol.Maybe(vol.All(vol.Coerce(int), vol.Range(min=1, max=300))),
                vol.Optional("position", default=0): vol.Maybe(vol.All(vol.Coerce(int), vol.Range(min=0, max=3))),
                vol.Optional("priority", default=1): vol.Maybe(vol.All(vol.Coerce(int), vol.Range(min=0, max=2))),
                vol.Optional("bg_color"): vol.Maybe(vol.Any(int, list)),
                vol.Optional("title_color"): vol.Maybe(vol.Any(int, list)),
                vol.Optional("msg_color"): vol.Maybe(vol.Any(int, list)),
                vol.Optional("title_size"): vol.Maybe(vol.Coerce(float)),
                vol.Optional("msg_size"): vol.Maybe(vol.Coerce(float)),
                vol.Optional("icon"): vol.Maybe(str),
                vol.Optional("small_icon"): vol.Maybe(str),
                vol.Optional("big_image"): vol.Maybe(str),
                vol.Optional("interact", default=False): vol.Maybe(bool),
                vol.Optional("notif_sound", default=True): vol.Maybe(bool),
                vol.Optional("wakeup", default=False): vol.Maybe(bool),
            })
        )

    # Register custom info service (once only)
    if not hass.services.has_service(DOMAIN, "info"):
        async def handle_info(call):
            host = call.data.get("host")
            device_id = call.data.get("device_id")
            entity_id = call.data.get("entity_id")
            try:
                notifier = get_notifier(host, device_id, entity_id)
                name = await notifier.async_get_info()
                return {"name": name}
            except Exception as err:
                raise HomeAssistantError(f"Failed to get device info: {err}") from err

        hass.services.async_register(
            DOMAIN,
            "info",
            handle_info,
            schema=vol.Schema({
                vol.Optional("host"): vol.Maybe(str),
                vol.Optional("device_id"): vol.Maybe(str),
                vol.Optional("entity_id"): vol.Maybe(vol.Any(str, [str])),
            }),
            supports_response=SupportsResponse.ONLY,
        )

    # Register custom apps service (once only)
    if not hass.services.has_service(DOMAIN, "apps"):
        async def handle_apps(call):
            host = call.data.get("host")
            device_id = call.data.get("device_id")
            entity_id = call.data.get("entity_id")
            try:
                notifier = get_notifier(host, device_id, entity_id)
                apps = await notifier.async_get_apps()
                mapped_apps = []
                for app in apps:
                    mapped_apps.append({
                        "name": app.get("n"),
                        "package": app.get("p"),
                    })
                return {"apps": mapped_apps}
            except Exception as err:
                raise HomeAssistantError(f"Failed to get apps: {err}") from err

        hass.services.async_register(
            DOMAIN,
            "apps",
            handle_apps,
            schema=vol.Schema({
                vol.Optional("host"): vol.Maybe(str),
                vol.Optional("device_id"): vol.Maybe(str),
                vol.Optional("entity_id"): vol.Maybe(vol.Any(str, [str])),
            }),
            supports_response=SupportsResponse.ONLY,
        )

    # Register custom discover service (once only)
    if not hass.services.has_service(DOMAIN, "discover"):
        async def handle_discover(call):
            timeout = call.data.get("timeout")
            if timeout is None:
                timeout = 6.0
            try:
                devices = await hass.async_add_executor_job(discover_devices, timeout)
                return {"devices": devices}
            except Exception as err:
                raise HomeAssistantError(f"Failed to run discovery: {err}") from err

        hass.services.async_register(
            DOMAIN,
            "discover",
            handle_discover,
            schema=vol.Schema({
                vol.Optional("timeout", default=6.0): vol.Maybe(vol.Coerce(float)),
                vol.Optional("entity_id"): vol.Maybe(vol.Any(str, [str])),
            }),
            supports_response=SupportsResponse.ONLY,
        )

    # Register custom qr service (once only)
    if not hass.services.has_service(DOMAIN, "qr"):
        async def handle_qr(call):
            image_str = call.data["image"].strip()
            
            if image_str.startswith(("http://", "https://")):
                img_input = image_str
            elif image_str.startswith("data:") and "base64," in image_str:
                try:
                    base64_data = image_str.split("base64,")[1]
                    img_input = base64.b64decode(base64_data)
                except Exception as err:
                    raise HomeAssistantError(f"Failed to decode base64 data: {err}") from err
            elif image_str.startswith(("/", "./", "../")) or os.path.exists(image_str):
                img_input = image_str
            else:
                # Try decoding as raw base64
                try:
                    cleaned_str = "".join(image_str.split())
                    img_input = base64.b64decode(cleaned_str, validate=True)
                except Exception:
                    # Fallback to treating it as a local path
                    img_input = image_str
            
            try:
                result = await hass.async_add_executor_job(decode_qr_image, img_input)
                return result
            except Exception as err:
                raise HomeAssistantError(f"Failed to decode QR image: {err}") from err

        hass.services.async_register(
            DOMAIN,
            "qr",
            handle_qr,
            schema=vol.Schema({
                vol.Required("image"): str,
                vol.Optional("entity_id"): vol.Maybe(vol.Any(str, [str])),
            }),
            supports_response=SupportsResponse.ONLY,
        )

    platforms = _get_platforms(entry)
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    platforms = _get_platforms(entry)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
