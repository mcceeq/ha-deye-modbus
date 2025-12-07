# Deye Modbus Integration Tests

## Overview

This directory contains unit tests for the Deye Modbus Home Assistant integration, focusing on critical functionality like write operations, validation, and verification.

## Running Tests

### Prerequisites

```bash
# Install pytest and dependencies
pip install pytest pytest-asyncio pytest-cov

# Install Home Assistant core (for types and exceptions)
pip install homeassistant
```

### Run All Tests

```bash
# From repository root
pytest tests/

# With coverage report
pytest tests/ --cov=custom_components/deye_modbus --cov-report=html

# Verbose output
pytest tests/ -v
```

### Run Specific Test Files

```bash
# Number entity tests only
pytest tests/test_number.py -v

# Select entity tests only
pytest tests/test_select.py -v
```

### Run Specific Tests

```bash
# Run a specific test function
pytest tests/test_number.py::TestNumberValidation::test_to_raw_basic_scaling -v

# Run all tests in a class
pytest tests/test_number.py::TestNumberValidation -v
```

## Test Coverage

### Current Coverage

| Module | Coverage Focus |
|--------|----------------|
| `test_number.py` | Number entity validation and write verification |
| `test_select.py` | Select entity masked writes and verification |

### Test Scenarios

#### Number Entity Tests (`test_number.py`)

**Validation Tests:**
- Basic scale conversion (single factor)
- List-based scale conversion (fraction)
- Minimum range validation
- Maximum range validation
- Register bounds checking (0-65535)
- Invalid value rejection

**Write Verification Tests:**
- Successful write with verification
- Verification failure detection

#### Select Entity Tests (`test_select.py`)

**Masked Write Tests:**
- Preserving unmasked bits during writes
- Masked write verification (only checking masked bits)
- Unmasked write verification
- Invalid option rejection

## Test Structure

### Fixtures (`conftest.py`)

Common test fixtures available to all tests:

- `mock_coordinator` - Mock DataUpdateCoordinator
- `mock_modbus_client` - Mock Modbus client with async methods

### Test Classes

Tests are organized into classes by functionality:

```python
class TestNumberValidation:
    """Test input validation for number entities."""

    def test_to_raw_basic_scaling(self):
        """Test basic scale conversion."""
        # Test implementation
```

### Async Tests

Async tests use `pytest-asyncio`:

```python
@pytest.mark.asyncio
async def test_write_verification_success(self):
    """Test successful write with verification."""
    # Test implementation with await
```

## Writing New Tests

### Basic Test Template

```python
def test_feature_name(self):
    """Test description."""
    # Arrange - Set up test data
    entity = create_test_entity(...)

    # Act - Perform the operation
    result = entity.do_something()

    # Assert - Verify the result
    assert result == expected_value
```

### Async Test Template

```python
@pytest.mark.asyncio
async def test_async_feature(self):
    """Test async operation."""
    # Arrange
    entity = create_test_entity(...)

    # Act
    result = await entity.async_do_something()

    # Assert
    assert result == expected_value
```

### Mocking External Dependencies

```python
from unittest.mock import Mock, AsyncMock

# Mock synchronous method
client = Mock()
client.read_register = Mock(return_value=100)

# Mock async method
client = AsyncMock()
client.async_read = AsyncMock(return_value=100)

# Mock with side effects
client.async_read = AsyncMock(side_effect=[100, 200, 300])
```

## Best Practices

### Test Naming

- Use descriptive names: `test_to_raw_range_validation_min`
- Follow pattern: `test_<what>_<condition>_<expected>`
- Use class names to group related tests

### Test Organization

- One assertion per test (when possible)
- Test both success and failure paths
- Test edge cases (min, max, zero, negative)
- Test invalid inputs

### Mocking

- Mock external dependencies (Modbus client, coordinator)
- Don't mock the code under test
- Use realistic mock data
- Verify mock calls when relevant

### Documentation

- Every test should have a docstring
- Explain WHAT is being tested, not HOW
- Document complex test setups

## Common Patterns

### Testing Value Conversion

```python
def test_value_conversion(self):
    """Test value is correctly converted."""
    definition = create_definition(scale=0.1)
    entity = create_entity(definition)

    result = entity._to_raw(10.5)

    assert result == 105  # 10.5 / 0.1
```

### Testing Validation Errors

```python
def test_invalid_value_rejected(self):
    """Test invalid values raise HomeAssistantError."""
    entity = create_entity(range_min=0, range_max=100)

    with pytest.raises(HomeAssistantError, match="below minimum"):
        entity._to_raw(-10)
```

### Testing Async Operations

```python
@pytest.mark.asyncio
async def test_async_write(self):
    """Test async write operation."""
    client = AsyncMock()
    client.async_write_register = AsyncMock()

    entity = create_entity(client=client)
    await entity.async_set_native_value(100)

    client.async_write_register.assert_called_once_with(0x0100, 100)
```

## Continuous Integration

These tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r requirements_test.txt
      - run: pytest tests/ --cov --cov-report=xml
      - uses: codecov/codecov-action@v2
```

## Future Test Coverage

### Planned Test Additions

- **Decoder tests** - Test datetime, BCD, and scale decoders
- **Time entity tests** - Test time write operations
- **Integration tests** - Test full setup flow
- **Config flow tests** - Test configuration UI
- **Binary sensor tests** - Test status parsing

### Test Metrics Goals

- **Line coverage**: >80%
- **Branch coverage**: >70%
- **Critical path coverage**: 100%

## Debugging Tests

### Run with Debug Output

```bash
# Show print statements
pytest tests/ -s

# Show local variables on failure
pytest tests/ -l

# Drop into debugger on failure
pytest tests/ --pdb
```

### Common Issues

**Import Errors**
- Ensure `custom_components` is in PYTHONPATH
- Check `conftest.py` path manipulation

**Async Errors**
- Use `@pytest.mark.asyncio` decorator
- Install `pytest-asyncio`
- Use `AsyncMock` for async methods

**Mock Not Called**
- Verify mock is passed to code under test
- Check if code is actually calling the method
- Use `mock.assert_called()` to debug

## Contributing Tests

When adding new features:

1. Write tests FIRST (TDD approach)
2. Ensure tests fail without the feature
3. Implement the feature
4. Verify tests pass
5. Add edge case tests
6. Update this README if needed

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock guide](https://docs.python.org/3/library/unittest.mock.html)
- [Home Assistant testing](https://developers.home-assistant.io/docs/development_testing)
