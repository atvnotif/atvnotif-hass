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
    """A select entity listing all installed apps on the Android TV."""

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
        )

    async def async_update(self) -> None:
        """Fetch the current app list from the TV."""
        try:
            apps: list[str] = await self._notifier.async_get_apps()
            if apps:
                self._attr_options = [PLACEHOLDER] + sorted(apps)
            else:
                self._attr_options = [PLACEHOLDER]
        except Exception as err:
            _LOGGER.warning("Could not fetch app list from TV: %s", err)
            # Keep existing options so the entity stays usable

    async def async_select_option(self, option: str) -> None:
        """Launch the selected app on the TV."""
        if option == PLACEHOLDER:
            return
        try:
            await self._notifier.async_open_app(option)
            _LOGGER.debug("Launched app %s on %s", option, self._notifier.host)
        except Exception as err:
            _LOGGER.error("Failed to launch app %s: %s", option, err)
        # Reset back to placeholder after launching
        self._attr_current_option = PLACEHOLDER
        self.async_write_ha_state()
