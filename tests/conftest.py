"""Pytest configuration and fixtures for Deye Modbus tests."""

import pytest
import sys
from pathlib import Path

# Add custom_components to path for imports
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator for testing."""
    from unittest.mock import Mock, AsyncMock

    coordinator = Mock()
    coordinator.data = {}
    coordinator.async_request_refresh = AsyncMock()
    coordinator.hass = Mock()
    return coordinator


@pytest.fixture
def mock_modbus_client():
    """Create a mock Modbus client for testing."""
    from unittest.mock import AsyncMock, Mock

    client = AsyncMock()
    client.async_write_register = AsyncMock()
    client.async_read_holding_registers = AsyncMock()
    return client
