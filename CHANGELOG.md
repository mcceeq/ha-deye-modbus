# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Added 32 new diagnostic sensors** for comprehensive inverter monitoring
  - **Phase 1 (High Priority)**: Battery Status, Grid/Generator Relay Status, Load/Inverter Output Frequencies
  - **Phase 2 (Medium Priority)**: RCD Leakage Current, Output Power metrics (Apparent/Active/Reactive), Load Currents L1/L2, AC Couple metrics, Generator metrics
  - **Phase 3 (Advanced)**: Grid voltage/frequency limits, Power Factor/Active/Reactive Power adjustments, CT Ratio, Grid Peak Shaving Power, Inverter Work Mode, Total Energy metrics (Buy/Sell/Load), BMS Connect State
  - All sensors marked as `entity_category: diagnostic` for easier organization
  - Enables advanced monitoring and troubleshooting capabilities
  - Based on comprehensive review of Modbus protocol V118 documentation

### Fixed

#### Critical Bug Fixes (Phase 1)

- **Fixed missing `timedelta` import** causing NameError when setting custom scan intervals
  - Added `from datetime import timedelta` to `__init__.py`
  - Resolves crash when users configure non-default scan intervals in options flow

- **Fixed unreachable code in datetime decoder** (`__init__.py:417-420`)
  - Removed incorrect indentation that prevented datetime validation from executing
  - Datetime decoding now properly validates parsed values before returning
  - Fixes potential crashes from invalid datetime values

- **Added error handling for YAML definition file parsing**
  - Added try/except around `yaml.safe_load()` in `definition_loader.py`
  - Catches `yaml.YAMLError` and `OSError` with descriptive error messages
  - Integration setup now fails gracefully with clear error when definition file is malformed
  - Prevents silent failures and provides actionable error messages to users

- **Fixed blocking I/O in configuration flow**
  - Converted `_battery_mode_options()` to `_battery_mode_options_sync()`
  - All 4 call sites now use `hass.async_add_executor_job()` to prevent event loop blocking
  - Configuration UI no longer freezes Home Assistant during setup
  - Affects both initial setup and options flow for RTU and TCP connections

- **Added comprehensive bounds checking for register writes** (`number.py`)
  - Validates user input against `range_min` and `range_max` from definitions before writing
  - Ensures converted raw values fit within 16-bit register range (0-65535)
  - Prevents potentially dangerous out-of-bounds writes to inverter registers
  - Provides clear error messages when validation fails

#### Write Verification (Addresses Random Value Changes)

- **Added read-after-write verification for all writable entities**
  - Number entities (`number.py`): Verifies written value matches expected raw value
  - Select entities (`select.py`): Verifies written value with mask-aware checking
  - Time entities (`time.py`): Verifies written time value in HHMM format
  - Immediately detects if inverter rejects or modifies written values
  - Raises `HomeAssistantError` if verification fails, alerting user to issues
  - Helps diagnose random value changes (e.g., ToU SOC jumping between 100 and 15)
  - Debug logging confirms successful writes with "Write verification OK" messages

### Security

- **Input validation:** Number entities now validate all writes against defined ranges and register limits to prevent out-of-range values from being sent to the inverter
- **Write verification:** All register writes are now verified by reading back the value, preventing silent write failures

### Changed

- Improved error messages for invalid configuration and malformed definition files
- Better async/await patterns in configuration flow to prevent UI blocking

#### Code Quality & Safety (Phase 3)

- **Enhanced error handling across all writable entities**
  - Added proper `HomeAssistantError` re-raising in select entities to preserve validation failures
  - Improved exception specificity in sensor parsing (ValueError, TypeError instead of bare Exception)
  - Added debug logging for failed numeric conversions in sensor entities
  - Consistent error handling patterns across number, select, and time entities

- **Added comprehensive type hints to all platform files**
  - Added `DataUpdateCoordinator[dict[str, Any]]` type hints to all entity `__init__` methods
  - Improved IDE support and type safety across sensor, number, select, time, datetime, and switch platforms
  - Better code maintainability with explicit coordinator typing

- **Improved logging infrastructure**
  - Added missing logger to sensor.py for better debugging
  - Consistent logging patterns across all platform files
  - Debug-level logging for non-critical parsing failures

### Technical Debt

- **Eliminated code duplication across platform files** (Phase 2 - Fix 6)
  - Created shared `device_info.py` module with device info utility functions
  - Removed 200+ lines of duplicated code from 6 platform files
  - Functions extracted: `build_base_device()`, `build_device_for_group()`, `build_base_name()`, `build_config_url()`
  - Updated all platform files to use shared module: `sensor.py`, `number.py`, `select.py`, `switch.py`, `time.py`, `datetime.py`
  - Improves maintainability - device info logic now in single location
- Removed dead code from datetime decoding logic
- Improved type safety with explicit imports

### Documentation

#### Testing & Quality Assurance (Phase 4)

- **Added comprehensive unit test suite**
  - Created `tests/` directory with pytest configuration
  - Added `test_number.py` - Tests for number entity validation and write verification
  - Added `test_select.py` - Tests for select entity masked writes and verification
  - Added `conftest.py` - Shared test fixtures for coordinators and Modbus clients
  - Tests cover: input validation, scale conversion, range checking, write verification, masked writes
  - Includes both sync and async test patterns
  - Ready for CI/CD integration

- **Created comprehensive documentation**
  - Added `docs/WRITE_VERIFICATION.md` - Complete guide to write verification feature
    - Explains why verification is needed (detecting inverter rejections/modifications)
    - Documents verification flow for number, select, and time entities
    - Covers masked write verification for registers with multiple settings
    - Explains error handling and logging levels
    - Provides debugging guidance for write failures
  - Added `docs/TROUBLESHOOTING.md` - Extensive troubleshooting guide
    - Common issues and solutions organized by symptom
    - Connection, configuration, and write operation debugging
    - Log message interpretation and debugging techniques
    - Manual Modbus testing instructions
    - Diagnostic sensor usage guide
    - Bug reporting guidelines
  - Added `tests/README.md` - Testing documentation
    - How to run tests (all, specific files, specific tests)
    - Test coverage overview
    - Writing new tests guide
    - Best practices and common patterns
    - CI/CD integration examples

- **Improved developer experience**
  - Clear test structure with descriptive names and docstrings
  - Mock fixtures for easy test development
  - Comprehensive code examples in documentation
  - Ready for community contributions

---

## Previous Releases

### Added
- Initial release of Deye Modbus integration for Home Assistant
- Support for Deye hybrid inverters via Modbus RTU (serial) and TCP connections
- Definition-driven entity creation from YAML files
- Battery control mode filtering for lead-acid vs lithium configurations
- Read-only sensors for voltages, currents, power, temperatures, and energy
- Writable number entities for Time of Use (ToU) program controls
- Select entities for operational mode selection
- Time entities for ToU program scheduling
- DateTime entities for timestamp readings
- Switch entities for status monitoring
- Optimized polling with fast (2s) and slow (5s) intervals
- Device grouping by parameter category
- Configuration flow with RTU and TCP setup wizards
- Options flow for reconfiguration
