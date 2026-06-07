import base64
import logging
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
        def get_notifier(host=None, device_id=None):
            if not hass.data[DOMAIN]:
                raise ValueError("No TV configured")
            config_data = None
            if host:
                for entry_data in hass.data[DOMAIN].values():
                    if entry_data[CONF_IP_ADDRESS] == host:
                        config_data = entry_data
                        break
            elif device_id:
                device_reg = dr.async_get(hass)
                device = device_reg.async_get(device_id)
                if device:
                    entry_id = next(iter(device.config_entries))
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
                vol.Optional("host"): str,
                vol.Optional("device_id"): str,
                vol.Required("package_name"): str,
            })
        )

    if not hass.services.has_service(DOMAIN, "notify"):
        async def handle_notify(call):
            host = call.data.get("host")
            device_id = call.data.get("device_id")
            try:
                notifier = get_notifier(host, device_id)
                await notifier.async_notify(
                    message=call.data["message"],
                    title=call.data.get("title"),
                    sender=call.data.get("sender", "Home Assistant"),
                    duration=call.data.get("duration", 5),
                    position=call.data.get("position", 0),
                    priority=call.data.get("priority", 1),
                    bg_color=call.data.get("bg_color"),
                    title_color=call.data.get("title_color"),
                    msg_color=call.data.get("msg_color"),
                    title_size=call.data.get("title_size"),
                    msg_size=call.data.get("msg_size"),
                    icon=call.data.get("icon"),
                    small_icon=call.data.get("small_icon"),
                    big_image=call.data.get("big_image"),
                    interact=call.data.get("interact", False),
                    notif_sound=call.data.get("notif_sound", True),
                    wakeup=call.data.get("wakeup", True),
                )
            except Exception as err:
                _LOGGER.error("Failed to send notification: %s", err)

        hass.services.async_register(
            DOMAIN,
            "notify",
            handle_notify,
            schema=vol.Schema({
                vol.Optional("host"): str,
                vol.Optional("device_id"): str,
                vol.Required("message"): str,
                vol.Optional("title"): str,
                vol.Optional("sender", default="Home Assistant"): str,
                vol.Optional("duration", default=5): vol.All(int, vol.Range(min=1, max=300)),
                vol.Optional("position", default=0): vol.All(int, vol.Range(min=0, max=3)),
                vol.Optional("priority", default=1): vol.All(int, vol.Range(min=0, max=2)),
                vol.Optional("bg_color"): int,
                vol.Optional("title_color"): int,
                vol.Optional("msg_color"): int,
                vol.Optional("title_size"): vol.Coerce(float),
                vol.Optional("msg_size"): vol.Coerce(float),
                vol.Optional("icon"): str,
                vol.Optional("small_icon"): str,
                vol.Optional("big_image"): str,
                vol.Optional("interact", default=False): bool,
                vol.Optional("notif_sound", default=True): bool,
                vol.Optional("wakeup", default=True): bool,
            })
        )

    # Register custom info service (once only)
    if not hass.services.has_service(DOMAIN, "info"):
        async def handle_info(call):
            host = call.data.get("host")
            device_id = call.data.get("device_id")
            try:
                notifier = get_notifier(host, device_id)
                name = await notifier.async_get_info()
                return {"name": name}
            except Exception as err:
                raise HomeAssistantError(f"Failed to get device info: {err}") from err

        hass.services.async_register(
            DOMAIN,
            "info",
            handle_info,
            schema=vol.Schema({
                vol.Optional("host"): str,
                vol.Optional("device_id"): str,
            }),
            supports_response=SupportsResponse.ONLY,
        )

    # Register custom apps service (once only)
    if not hass.services.has_service(DOMAIN, "apps"):
        async def handle_apps(call):
            host = call.data.get("host")
            device_id = call.data.get("device_id")
            try:
                notifier = get_notifier(host, device_id)
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
                vol.Optional("host"): str,
                vol.Optional("device_id"): str,
            }),
            supports_response=SupportsResponse.ONLY,
        )

    # Register custom discover service (once only)
    if not hass.services.has_service(DOMAIN, "discover"):
        async def handle_discover(call):
            timeout = call.data.get("timeout", 6.0)
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
                vol.Optional("timeout", default=6.0): vol.Coerce(float),
            }),
            supports_response=SupportsResponse.ONLY,
        )

    # Register custom qr service (once only)
    if not hass.services.has_service(DOMAIN, "qr"):
        async def handle_qr(call):
            image_path = call.data.get("image_path")
            image_url = call.data.get("image_url")
            image_base64 = call.data.get("image_base64")
            
            if image_base64:
                try:
                    img_input = base64.b64decode(image_base64)
                except Exception as err:
                    raise HomeAssistantError(f"Invalid base64 string: {err}") from err
            elif image_url:
                img_input = image_url
            elif image_path:
                img_input = image_path
            else:
                raise HomeAssistantError("One of image_path, image_url, or image_base64 must be provided")
            
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
                vol.Optional("image_path"): str,
                vol.Optional("image_url"): str,
                vol.Optional("image_base64"): str,
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
