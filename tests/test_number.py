"""Tests for number entity write operations and validation."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from homeassistant.exceptions import HomeAssistantError

from custom_components.deye_modbus.number import DeyeDefinitionNumber
from custom_components.deye_modbus.definition_loader import DefinitionItem


class TestNumberValidation:
    """Test input validation for number entities."""

    def setup_method(self):
        """Set up test fixtures."""
        self.coordinator = Mock()
        self.coordinator.data = {}
        self.coordinator.hass = Mock()
        self.coordinator.hass.data = {
            "deye_modbus": {
                "test_entry": {
                    "client": AsyncMock()
                }
            }
        }

    def test_to_raw_basic_scaling(self):
        """Test basic scale conversion."""
        definition = DefinitionItem(
            key="test_number",
            name="Test Number",
            platform="number",
            registers=[0x0100],
            scale=0.1,
            range_min=0,
            range_max=100,
        )

        from homeassistant.components.number import NumberEntityDescription
        desc = NumberEntityDescription(key="test_number", name="Test Number")

        entity = DeyeDefinitionNumber(
            coordinator=self.coordinator,
            description=desc,
            entry_id="test_entry",
            definition=definition,
            device_info={},
        )

        # Test: value 10.5 with scale 0.1 should become 105
        result = entity._to_raw(10.5)
        assert result == 105

    def test_to_raw_list_scaling(self):
        """Test list-based scale conversion."""
        definition = DefinitionItem(
            key="test_number",
            name="Test Number",
            platform="number",
            registers=[0x0100],
            scale=[1, 10],  # Factor of 0.1
            range_min=0,
            range_max=100,
        )

        from homeassistant.components.number import NumberEntityDescription
        desc = NumberEntityDescription(key="test_number", name="Test Number")

        entity = DeyeDefinitionNumber(
            coordinator=self.coordinator,
            description=desc,
            entry_id="test_entry",
            definition=definition,
            device_info={},
        )

        # Test: value 10 with scale [1,10] should become 100
        result = entity._to_raw(10.0)
        assert result == 100

    def test_to_raw_range_validation_min(self):
        """Test that values below minimum are rejected."""
        definition = DefinitionItem(
            key="test_number",
            name="Test Number",
            platform="number",
            registers=[0x0100],
            scale=1,
            range_min=10,
            range_max=100,
        )

        from homeassistant.components.number import NumberEntityDescription
        desc = NumberEntityDescription(key="test_number", name="Test Number")

        entity = DeyeDefinitionNumber(
            coordinator=self.coordinator,
            description=desc,
            entry_id="test_entry",
            definition=definition,
            device_info={},
        )

        # Test: value below minimum should raise error
        with pytest.raises(HomeAssistantError, match="below minimum"):
            entity._to_raw(5)

    def test_to_raw_range_validation_max(self):
        """Test that values above maximum are rejected."""
        definition = DefinitionItem(
            key="test_number",
            name="Test Number",
            platform="number",
            registers=[0x0100],
            scale=1,
            range_min=0,
            range_max=100,
        )

        from homeassistant.components.number import NumberEntityDescription
        desc = NumberEntityDescription(key="test_number", name="Test Number")

        entity = DeyeDefinitionNumber(
            coordinator=self.coordinator,
            description=desc,
            entry_id="test_entry",
            definition=definition,
            device_info={},
        )

        # Test: value above maximum should raise error
        with pytest.raises(HomeAssistantError, match="above maximum"):
            entity._to_raw(150)

    def test_to_raw_register_bounds_check(self):
        """Test that converted values fit in 16-bit register."""
        definition = DefinitionItem(
            key="test_number",
            name="Test Number",
            platform="number",
            registers=[0x0100],
            scale=0.001,  # Will cause very large raw values
            range_min=0,
            range_max=100000,
        )

        from homeassistant.components.number import NumberEntityDescription
        desc = NumberEntityDescription(key="test_number", name="Test Number")

        entity = DeyeDefinitionNumber(
            coordinator=self.coordinator,
            description=desc,
            entry_id="test_entry",
            definition=definition,
            device_info={},
        )

        # Test: value that converts to >65535 should raise error
        with pytest.raises(HomeAssistantError, match="out of valid register range"):
            entity._to_raw(100000)

    def test_to_raw_invalid_value(self):
        """Test that non-numeric values are rejected."""
        definition = DefinitionItem(
            key="test_number",
            name="Test Number",
            platform="number",
            registers=[0x0100],
            scale=1,
            range_min=0,
            range_max=100,
        )

        from homeassistant.components.number import NumberEntityDescription
        desc = NumberEntityDescription(key="test_number", name="Test Number")

        entity = DeyeDefinitionNumber(
            coordinator=self.coordinator,
            description=desc,
            entry_id="test_entry",
            definition=definition,
            device_info={},
        )

        # Test: invalid value should raise error
        with pytest.raises(HomeAssistantError, match="Invalid number value"):
            entity._to_raw("not a number")


class TestNumberWriteVerification:
    """Test write verification for number entities."""

    @pytest.mark.asyncio
    async def test_write_verification_success(self):
        """Test successful write with verification."""
        coordinator = Mock()
        coordinator.data = {}
        coordinator.async_request_refresh = AsyncMock()

        client = AsyncMock()
        client.async_write_register = AsyncMock()

        # Mock successful read-back
        read_result = Mock()
        read_result.isError = Mock(return_value=False)
        read_result.registers = [100]  # Expected value
        client.async_read_holding_registers = AsyncMock(return_value=read_result)

        coordinator.hass = Mock()
        coordinator.hass.data = {
            "deye_modbus": {
                "test_entry": {
                    "client": client
                }
            }
        }

        definition = DefinitionItem(
            key="battery_max_charging_current",  # Whitelisted key
            name="Battery Max Charging Current",
            platform="number",
            registers=[0x0100],
            scale=1,
            range_min=0,
            range_max=200,
        )

        from homeassistant.components.number import NumberEntityDescription
        desc = NumberEntityDescription(
            key="battery_max_charging_current",
            name="Battery Max Charging Current"
        )

        entity = DeyeDefinitionNumber(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry",
            definition=definition,
            device_info={},
        )

        # Test: write should succeed and verification should pass
        await entity.async_set_native_value(100)

        client.async_write_register.assert_called_once_with(0x0100, 100)
        client.async_read_holding_registers.assert_called_once_with(0x0100, 1)
        coordinator.async_request_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_verification_failure(self):
        """Test write verification detects mismatched values."""
        coordinator = Mock()
        coordinator.data = {}
        coordinator.async_request_refresh = AsyncMock()

        client = AsyncMock()
        client.async_write_register = AsyncMock()

        # Mock read-back with different value
        read_result = Mock()
        read_result.isError = Mock(return_value=False)
        read_result.registers = [50]  # Different from written value
        client.async_read_holding_registers = AsyncMock(return_value=read_result)

        coordinator.hass = Mock()
        coordinator.hass.data = {
            "deye_modbus": {
                "test_entry": {
                    "client": client
                }
            }
        }

        definition = DefinitionItem(
            key="battery_max_charging_current",
            name="Battery Max Charging Current",
            platform="number",
            registers=[0x0100],
            scale=1,
            range_min=0,
            range_max=200,
        )

        from homeassistant.components.number import NumberEntityDescription
        desc = NumberEntityDescription(
            key="battery_max_charging_current",
            name="Battery Max Charging Current"
        )

        entity = DeyeDefinitionNumber(
            coordinator=coordinator,
            description=desc,
            entry_id="test_entry",
            definition=definition,
            device_info={},
        )

        # Test: write should fail verification
        with pytest.raises(HomeAssistantError, match="Write verification failed"):
            await entity.async_set_native_value(100)
