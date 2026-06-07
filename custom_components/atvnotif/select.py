"""Select entity for launching apps on Android TV Notifier."""
from __future__ import annotations

import logging
from typing import Final

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_IP_ADDRESS, CONF_PORT, CONF_PAIRING_CODE, DEFAULT_PORT

try:
    from atvnotif import ATVNotifier
except ImportError:
    from .atvnotif import ATVNotifier

_LOGGER = logging.getLogger(__name__)

PLACEHOLDER: Final = "— Select an app —"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the app launcher select entity."""
    config = entry.data
    notifier = ATVNotifier(
        config[CONF_IP_ADDRESS],
        config[CONF_PAIRING_CODE],
        config.get(CONF_PORT, DEFAULT_PORT),
    )
    async_add_entities([ATVAppLauncherSelect(entry, notifier)], update_before_add=True)


class ATVAppLauncherSelect(SelectEntity):
    """Select entity listing all installed apps on the Android TV.

    Displays human-readable app names; internally maps them to package names for
    launch.  Extra state attributes expose info returned by /info (device name,
    model, etc.) as well as the count of installed apps.
    """

    _attr_has_entity_name = True
    _attr_name = "Launch App"
    _attr_icon = "mdi:television-play"

    def __init__(self, entry: ConfigEntry, notifier: ATVNotifier) -> None:
        self._entry = entry
        self._notifier = notifier
        self._attr_unique_id = f"{entry.entry_id}_app_launcher"
        self._attr_options = [PLACEHOLDER]
        self._attr_current_option = PLACEHOLDER
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Smart Projects",
            model="Android TV Notifier",
            sw_version=entry.data.get("app_version"),
            configuration_url=f"http://{entry.data[CONF_IP_ADDRESS]}:{entry.data.get(CONF_PORT, DEFAULT_PORT)}",
        )
        # Internal map: display name → package name
        self._app_map: dict[str, str] = {}
        # Extra attributes from /info
        self._tv_info: dict = {}

    @property
    def extra_state_attributes(self) -> dict:
        """Return TV info + app count as extra attributes."""
        attrs = dict(self._tv_info)
        attrs["app_count"] = len(self._app_map)
        return attrs

    async def async_update(self) -> None:
        """Fetch app list and TV info from the device."""
        # --- /info ---
        try:
            raw_info = await self._notifier.async_get_info()
            # /info returns a plain string: the device name
            self._tv_info = {"tv_name": raw_info.strip()}
        except Exception as err:
            _LOGGER.warning("Could not fetch /info from TV: %s", err)

        # --- /apps ---
        try:
            apps: list[dict] = await self._notifier.async_get_apps()
            if apps:
                # Build name→package map; deduplicate display names
                app_map: dict[str, str] = {}
                for app in apps:
                    display = app.get("n") or app.get("p", "")
                    package = app.get("p", "")
                    if display and package:
                        # If two apps share a display name, append package suffix
                        key = display
                        if key in app_map and app_map[key] != package:
                            key = f"{display} ({package})"
                        app_map[key] = package
                self._app_map = dict(sorted(app_map.items()))
                self._attr_options = [PLACEHOLDER] + list(self._app_map.keys())
            else:
                self._attr_options = [PLACEHOLDER]
        except Exception as err:
            _LOGGER.warning("Could not fetch app list from TV: %s", err)
            # Keep existing options so the entity stays usable

    async def async_select_option(self, option: str) -> None:
        """Launch the selected app on the TV."""
        if option == PLACEHOLDER:
            return
        package = self._app_map.get(option)
        if not package:
            _LOGGER.error("No package found for app '%s'", option)
            return
        try:
            await self._notifier.async_open_app(package)
            _LOGGER.debug("Launched %s (%s) on %s", option, package, self._notifier.host)
        except Exception as err:
            _LOGGER.error("Failed to launch app %s: %s", package, err)
        # Reset back to placeholder after launching
        self._attr_current_option = PLACEHOLDER
        self.async_write_ha_state()
