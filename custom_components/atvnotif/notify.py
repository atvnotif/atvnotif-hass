from __future__ import annotations
import logging
from typing import Any

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    BaseNotificationService,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, CONF_IP_ADDRESS, CONF_PORT, CONF_PAIRING_CODE

try:
    from atvnotif import ATVNotifier
except ImportError:
    from .atvnotif import ATVNotifier

_LOGGER = logging.getLogger(__name__)

async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> ATVNotifNotificationService | None:
    """Get the Android TV Notifier notification service."""
    if discovery_info is None:
        return None

    ip_address = discovery_info.get(CONF_IP_ADDRESS)
    port = discovery_info.get(CONF_PORT, 7878)
    pairing_code = discovery_info.get(CONF_PAIRING_CODE)

    if not ip_address or not pairing_code:
        _LOGGER.error("Missing IP address or pairing code in discovery info")
        return None

    notifier = ATVNotifier(ip_address, pairing_code, port=port)
    return ATVNotifNotificationService(notifier)

class ATVNotifNotificationService(BaseNotificationService):
    """Notification service for Android TV Notifier."""

    def __init__(self, notifier: ATVNotifier) -> None:
        """Initialize the service."""
        self._notifier = notifier

    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message to the TV."""
        title = kwargs.get(ATTR_TITLE)
        data = kwargs.get(ATTR_DATA) or {}

        duration = data.get("duration", 5)
        position = data.get("position", 0)
        priority = data.get("priority", 1)
        sender = data.get("sender", "Home Assistant")
        bg_color = data.get("bg_color")
        title_color = data.get("title_color")
        msg_color = data.get("msg_color")
        title_size = data.get("title_size")
        msg_size = data.get("msg_size")
        icon = data.get("icon")
        small_icon = data.get("small_icon")
        big_image = data.get("big_image")
        interact = data.get("interact", False)
        notif_sound = data.get("notif_sound", True)
        wakeup = data.get("wakeup", True)

        try:
            await self._notifier.async_notify(
                message=message,
                title=title,
                sender=sender,
                duration=duration,
                position=position,
                priority=priority,
                bg_color=bg_color,
                title_color=title_color,
                msg_color=msg_color,
                title_size=title_size,
                msg_size=msg_size,
                icon=icon,
                small_icon=small_icon,
                big_image=big_image,
                interact=interact,
                notif_sound=notif_sound,
                wakeup=wakeup,
            )
        except Exception as err:
            _LOGGER.error("Failed to send notification to Android TV: %s", err)
