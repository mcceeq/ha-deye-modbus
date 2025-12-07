"""Tests for select entity write operations with masking."""

import pytest
from unittest.mock import Mock, AsyncMock
from homeassistant.exceptions import HomeAssistantError

from custom_components.deye_modbus.select import DeyeDefinitionSelect
from custom_components.deye_modbus.definition_loader import DefinitionItem


class TestSelectMaskedWrites:
    """Test masked write operations for select entities."""

    @pytest.mark.asyncio
    async def test_masked_write_preserves_other_bits(self):
        """Test that masked writes preserve unmasked bits."""
        coordinator = Mock()
        coordinator.data = {}
        coordinator.async_request_refresh = AsyncMock()

        client = AsyncMock()

        # Mock current register value: 0b11110000 (240)
        current_read = Mock()
        current_read.isError = Mock(return_value=False)
        current_read.registers = [0b11110000]

        # Mock verification read
        verify_read = Mock()
        verify_read.isError = Mock(return_value=False)
        verify_read.registers = [0b11110011]  # Expected after masked write

        client.async_read_holding_registers = AsyncMock(side_effect=[current_read, verify_read])
        client.async_write_register = AsyncMock()

        coordinator.hass = Mock()
        coordinator.hass.data = {
            "deye_modbus": {
                "test_entry": {
                    "client": client
                }
            }
        }

        definition = DefinitionItem(
            key="program_1_charging",  # Whitelisted key
            name="Program 1 Charging",
            platform="select",
            registers=[0x0100],
            mask=0b00001111,  # Only modify lower 4 bits
            lookup={0: "Disabled", 3: "Enabled"},
        )

        from homeassistant.components.select import SelectEntityDescription
        desc = SelectEntityDescription(
            key="program_1_charging",
            name="Program 1 Charging",
            options=["Disabled", "Enabled"]
        )

        entity = DeyeDefinitionSelect(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry",
            definition=definition,
            device_info={},
        )

        # Test: writing value 3 with mask 0x0F should preserve upper bits
        await entity.async_select_option("Enabled")

        # Verify: should write 0b11110011 (preserving upper 4 bits, setting lower to 0011)
        client.async_write_register.assert_called_once_with(0x0100, 0b11110011)

    @pytest.mark.asyncio
    async def test_masked_write_verification(self):
        """Test that masked write verification only checks masked bits."""
        coordinator = Mock()
        coordinator.data = {}
        coordinator.async_request_refresh = AsyncMock()

        client = AsyncMock()

        # Mock current register value
        current_read = Mock()
        current_read.isError = Mock(return_value=False)
        current_read.registers = [0b11110000]

        # Mock verification read - upper bits different, but masked bits match
        verify_read = Mock()
        verify_read.isError = Mock(return_value=False)
        verify_read.registers = [0b10100011]  # Different upper bits, but lower 4 bits = 0011

        client.async_read_holding_registers = AsyncMock(side_effect=[current_read, verify_read])
        client.async_write_register = AsyncMock()

        coordinator.hass = Mock()
        coordinator.hass.data = {
            "deye_modbus": {
                "test_entry": {
                    "client": client
                }
            }
        }

        definition = DefinitionItem(
            key="program_1_charging",
            name="Program 1 Charging",
            platform="select",
            registers=[0x0100],
            mask=0b00001111,  # Only verify lower 4 bits
            lookup={0: "Disabled", 3: "Enabled"},
        )

        from homeassistant.components.select import SelectEntityDescription
        desc = SelectEntityDescription(
            key="program_1_charging",
            name="Program 1 Charging",
            options=["Disabled", "Enabled"]
        )

        entity = DeyeDefinitionSelect(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry",
            definition=definition,
            device_info={},
        )

        # Test: verification should pass even though upper bits differ
        await entity.async_select_option("Enabled")
        coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_unmasked_write_verification_failure(self):
        """Test that unmasked writes detect value mismatches."""
        coordinator = Mock()
        coordinator.data = {}
        coordinator.async_request_refresh = AsyncMock()

        client = AsyncMock()
        client.async_write_register = AsyncMock()

        # Mock verification read with wrong value
        verify_read = Mock()
        verify_read.isError = Mock(return_value=False)
        verify_read.registers = [0]  # Wrong value

        client.async_read_holding_registers = AsyncMock(return_value=verify_read)

        coordinator.hass = Mock()
        coordinator.hass.data = {
            "deye_modbus": {
                "test_entry": {
                    "client": client
                }
            }
        }

        definition = DefinitionItem(
            key="time_of_use",  # Whitelisted key
            name="Time of Use",
            platform="select",
            registers=[0x0100],
            mask=None,  # No mask - full register write
            lookup={0: "Disabled", 1: "Enabled"},
        )

        from homeassistant.components.select import SelectEntityDescription
        desc = SelectEntityDescription(
            key="time_of_use",
            name="Time of Use",
            options=["Disabled", "Enabled"]
        )

        entity = DeyeDefinitionSelect(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry",
            definition=definition,
            device_info={},
        )

        # Test: verification should fail
        with pytest.raises(HomeAssistantError, match="Write verification failed"):
            await entity.async_select_option("Enabled")

    def test_invalid_option_rejected(self):
        """Test that invalid options are rejected."""
        coordinator = Mock()
        coordinator.data = {}

        definition = DefinitionItem(
            key="time_of_use",
            name="Time of Use",
            platform="select",
            registers=[0x0100],
            lookup={0: "Disabled", 1: "Enabled"},
        )

        from homeassistant.components.select import SelectEntityDescription
        desc = SelectEntityDescription(
            key="time_of_use",
            name="Time of Use",
            options=["Disabled", "Enabled"]
        )

        entity = DeyeDefinitionSelect(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry",
            definition=definition,
            device_info={},
        )

        # Test: invalid option should raise error
        with pytest.raises(HomeAssistantError, match="Invalid option"):
            import asyncio
            asyncio.run(entity.async_select_option("InvalidOption"))
