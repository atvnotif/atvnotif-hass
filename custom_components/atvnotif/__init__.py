import logging
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, CONF_IP_ADDRESS, CONF_PORT, CONF_PAIRING_CODE

try:
    from atvnotif import ATVNotifier
except ImportError:
    from .atvnotif import ATVNotifier

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.NOTIFY, Platform.SELECT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Android TV Notifier from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Register custom service calls if not already registered
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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

