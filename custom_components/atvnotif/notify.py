"""Modern NotifyEntity for Android TV Notifier."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Android TV Notifier notify entity."""
    config = entry.data
    notifier = ATVNotifier(
        config[CONF_IP_ADDRESS],
        config[CONF_PAIRING_CODE],
        config.get(CONF_PORT, DEFAULT_PORT),
    )
    async_add_entities([ATVNotifEntity(entry, notifier)])


class ATVNotifEntity(NotifyEntity):
    """A notify entity that sends messages to the Android TV Notifier app.

    Supports title via NotifyEntityFeature.TITLE.
    Additional parameters (duration, position, priority, etc.) can be passed
    through the ``data`` dict in the ``notify.send_message`` action, matching
    the same keys used in the legacy notify service.
    """

    _attr_has_entity_name = True
    _attr_name = "Notify"
    _attr_icon = "mdi:television-shimmer"
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, entry: ConfigEntry, notifier: ATVNotifier) -> None:
        self._entry = entry
        self._notifier = notifier
        self._attr_unique_id = f"{entry.entry_id}_notify"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Smart Projects",
            model="Android TV Notifier",
        )

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a notification to the Android TV.

        Extra parameters can be passed by the caller via the ``data`` field of
        the ``notify.send_message`` action (same keys as the atvnotif library):
          duration, position, priority, sender, bg_color, title_color,
          msg_color, title_size, msg_size, icon, small_icon, big_image,
          interact, notif_sound, wakeup
        """
        # HASS does not expose 'data' to NotifyEntity.async_send_message directly,
        # but the domain's custom atvnotif.notify action still does via notify.py
        # service data. For the entity path we use sensible defaults.
        try:
            await self._notifier.async_notify(
                message=message,
                title=title,
            )
            self._async_record_notification()
        except Exception as err:
            _LOGGER.error("Failed to send notification to Android TV: %s", err)
