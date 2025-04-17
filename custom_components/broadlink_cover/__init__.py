from .const import DOMAIN

async def async_setup_entry(hass, entry):
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    hass.async_create_task(
        hass.helpers.discovery.async_load_platform(
            "cover", DOMAIN, entry.data, entry
        )
    )
    return True

async def async_unload_entry(hass, entry):
    # Optional cleanup if needed
    return True

