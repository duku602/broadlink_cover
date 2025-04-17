import asyncio
import time
import logging

from homeassistant.components.cover import CoverEntity
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (
    CoverEntityFeature.OPEN
    | CoverEntityFeature.CLOSE
    | CoverEntityFeature.STOP
    | CoverEntityFeature.SET_POSITION
)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the cover from a config entry."""
    data = config_entry.data

    name = data["name"]
    remote_entity_id = data["remote_entity_id"]
    commands = {
        "device": data["device"],
        "open": data["open"],
        "stop": data["stop"],
        "close": data["close"],
    }
    open_time = data.get("open_time", 15)
    close_time = data.get("close_time", 15)

    cover = BroadlinkRFTimeCover(
        hass, name, remote_entity_id, commands, open_time, close_time, config_entry.entry_id
    )

    async_add_entities([cover])


class BroadlinkRFTimeCover(CoverEntity, RestoreEntity):
    """Representation of a Broadlink RF cover."""

    def __init__(self, hass, name, remote_entity_id, commands, open_time, close_time, entry_id):
        """Initialize the cover entity."""
        self._hass = hass
        self._name = name
        self._remote_entity_id = remote_entity_id
        self._commands = commands
        self._open_time = open_time
        self._close_time = close_time
        self._entry_id = entry_id

        self._position = 0  # 0 = closed, 100 = fully open
        self._is_moving = False
        self._last_direction = None
        self._move_task = None

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID for the cover (combines entry_id and device name)."""
        return f"{self._entry_id}_{self._commands['device'].lower()}"

    @property
    def supported_features(self):
        """Return the features supported by the cover."""
        return SUPPORT_FLAGS

    @property
    def is_closed(self):
        """Return True if the cover is closed."""
        return self._position == 0

    @property
    def current_cover_position(self):
        """Return the current position of the cover (0-100)."""
        return round(self._position)

    async def async_added_to_hass(self):
        """Restore previous state and position on startup."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state != "unknown":
                try:
                    self._position = int(last_state.attributes.get("current_position", 0))
                except (ValueError, TypeError):
                    self._position = 0

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self._move_cover("open", 100)

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self._move_cover("close", 0)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover movement."""
        if self._move_task:
            self._move_task.cancel()
            self._move_task = None

        await self._send_code("stop")
        self._is_moving = False
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs):
        """Set the position of the cover."""
        position = kwargs.get("position", self._position)
        direction = "open" if position > self._position else "close"
        await self._move_cover(direction, position)

    async def _move_cover(self, direction, target_position):
        """Move the cover to the target position."""
        await self._send_code(direction)
        self._is_moving = True
        self._last_direction = direction

        if self._move_task:
            self._move_task.cancel()

        duration = self._calculate_duration(direction, target_position)
        self._move_task = self._hass.loop.create_task(
            self._timed_move(direction, duration, target_position)
        )

    def _calculate_duration(self, direction, target_position):
        """Calculate the duration for the cover to reach the target position."""
        if direction == "open":
            distance = target_position - self._position
            return (distance / 100) * self._open_time
        else:
            distance = self._position - target_position
            return (distance / 100) * self._close_time

    async def _timed_move(self, direction, duration, target_position):
        """Move the cover over a specified duration."""
        start_time = time.time()
        try:
            await asyncio.sleep(duration)
            self._position = target_position
        except asyncio.CancelledError:
            elapsed = time.time() - start_time
            delta = (
                elapsed / self._open_time * 100
                if direction == "open"
                else elapsed / self._close_time * 100
            )
            if direction == "open":
                self._position = min(100, self._position + delta)
            else:
                self._position = max(0, self._position - delta)
        finally:
            await self._send_code("stop")
            self._is_moving = False
            self.async_write_ha_state()

    async def _send_code(self, command_key):
        """Send the RF code to the Broadlink device."""
        device_name = self._commands.get("device")
        command_name = self._commands.get(command_key)

        if not device_name or not command_name:
            _LOGGER.warning(f"Missing device or command '{command_key}' in {self._name}")
            return

        await self._hass.services.async_call(
            "remote",
            "send_command",
            {
                "entity_id": self._remote_entity_id,
                "device": device_name,
                "command": command_name,
            },
            blocking=True,
        )

