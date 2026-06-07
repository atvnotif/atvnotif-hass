import voluptuous as vol
import httpx
import logging
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_IP_ADDRESS,
    CONF_PORT,
    CONF_PAIRING_CODE,
    DEFAULT_PORT,
    CONF_ENABLE_APP_LAUNCHER,
    CONF_ENABLE_NOTIFY_ENTITY,
)
try:
    from .atvnotif.discover import decode_base58_uuid
    from .atvnotif.qr import decode_qr_image
except ImportError:
    from atvnotif.discover import decode_base58_uuid
    from atvnotif.qr import decode_qr_image

_LOGGER = logging.getLogger(__name__)

class ATVNotifConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Android TV Notifier."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return ATVNotifOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            qr_url = user_input.get("qr_url")
            
            # If QR URL is provided, try to fetch and decode it
            if qr_url:
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(qr_url, timeout=10.0)
                        response.raise_for_status()
                        img_bytes = response.content
                    
                    # Run decoding in a thread pool to avoid blocking the event loop
                    qr_data = await self.hass.async_add_executor_job(
                        decode_qr_image, img_bytes
                    )
                    
                    if qr_data and qr_data.get("pairing_code"):
                        ip = qr_data.get("ip") or user_input.get(CONF_IP_ADDRESS)
                        port = qr_data.get("p") or user_input.get(CONF_PORT) or DEFAULT_PORT
                        pairing_code = qr_data.get("pairing_code")
                        name = qr_data.get("n") or "Android TV"
                        
                        if not ip:
                            errors["base"] = "missing_ip"
                        else:
                            return self.async_create_entry(
                                title=f"{name} ({ip})",
                                data={
                                    CONF_IP_ADDRESS: ip,
                                    CONF_PORT: int(port),
                                    CONF_PAIRING_CODE: pairing_code,
                                },
                            )
                    else:
                        errors["base"] = "qr_decode_failed"
                except Exception as err:
                    _LOGGER.error("Failed to decode QR URL %s: %s", qr_url, err)
                    errors["base"] = "qr_decode_failed"
            else:
                # Standard manual setup
                if not user_input[CONF_IP_ADDRESS]:
                    errors["base"] = "invalid_host"
                elif not user_input[CONF_PAIRING_CODE]:
                    errors["base"] = "invalid_pairing_code"
                else:
                    return self.async_create_entry(
                        title=f"Android TV Notifier ({user_input[CONF_IP_ADDRESS]})",
                        data={
                            CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
                            CONF_PORT: user_input[CONF_PORT],
                            CONF_PAIRING_CODE: user_input[CONF_PAIRING_CODE],
                        },
                    )

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_IP_ADDRESS): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(CONF_PAIRING_CODE): str,
                vol.Optional("qr_url"): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_zeroconf(self, discovery_info):
        """Handle zeroconf discovery."""
        await self.async_set_unique_id(discovery_info.hostname)
        self._abort_if_unique_id_configured()

        self.discovered_ip = discovery_info.host
        self.discovered_port = discovery_info.port or DEFAULT_PORT
        self.discovered_name = discovery_info.properties.get("n", "Android TV")
        self.discovered_app_version = discovery_info.properties.get("v")

        # Try to extract the base58 pairing key from mDNS attributes
        base58_code = discovery_info.properties.get("i")
        self.discovered_pairing_code = None
        if base58_code:
            try:
                self.discovered_pairing_code = decode_base58_uuid(base58_code)
            except Exception:
                pass

        self.context["title_placeholders"] = {"name": self.discovered_name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input=None):
        """Confirm discovery and ask for the pairing code."""
        errors = {}

        if user_input is not None:
            pairing_code = user_input.get(CONF_PAIRING_CODE)
            if not pairing_code:
                errors["base"] = "invalid_pairing_code"
            else:
                return self.async_create_entry(
                    title=f"{self.discovered_name} ({self.discovered_ip})",
                    data={
                        CONF_IP_ADDRESS: self.discovered_ip,
                        CONF_PORT: self.discovered_port,
                        CONF_PAIRING_CODE: pairing_code,
                        "app_version": self.discovered_app_version,
                    },
                )

        schema = vol.Schema({
            vol.Required(
                CONF_PAIRING_CODE, 
                default=self.discovered_pairing_code or ""
            ): str
        })

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=schema,
            description_placeholders={"name": self.discovered_name},
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        """Allow the user to edit IP, port, and pairing code of an existing entry."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        errors = {}

        if user_input is not None:
            ip = user_input.get(CONF_IP_ADDRESS, "").strip()
            pairing_code = user_input.get(CONF_PAIRING_CODE, "").strip()
            port = user_input.get(CONF_PORT, DEFAULT_PORT)

            if not ip:
                errors["base"] = "invalid_host"
            elif not pairing_code:
                errors["base"] = "invalid_pairing_code"
            else:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        CONF_IP_ADDRESS: ip,
                        CONF_PORT: port,
                        CONF_PAIRING_CODE: pairing_code,
                    },
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        current = entry.data if entry else {}
        schema = vol.Schema({
            vol.Required(CONF_IP_ADDRESS, default=current.get(CONF_IP_ADDRESS, "")): str,
            vol.Required(CONF_PORT, default=current.get(CONF_PORT, DEFAULT_PORT)): int,
            vol.Required(CONF_PAIRING_CODE, default=current.get(CONF_PAIRING_CODE, "")): str,
        })

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
        )


class ATVNotifOptionsFlow(config_entries.OptionsFlow):
    """Options flow to toggle optional features (app launcher, notify entity)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the integration options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        opts = self.config_entry.options
        schema = vol.Schema({
            vol.Required(
                CONF_ENABLE_NOTIFY_ENTITY,
                default=opts.get(CONF_ENABLE_NOTIFY_ENTITY, True),
            ): bool,
            vol.Required(
                CONF_ENABLE_APP_LAUNCHER,
                default=opts.get(CONF_ENABLE_APP_LAUNCHER, True),
            ): bool,
        })

        return self.async_show_form(step_id="init", data_schema=schema)
