# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Security

- **Input validation:** Number entities now validate all writes against defined ranges and register limits to prevent out-of-range values from being sent to the inverter

### Changed

- Improved error messages for invalid configuration and malformed definition files
- Better async/await patterns in configuration flow to prevent UI blocking

### Technical Debt

- Removed dead code from datetime decoding logic
- Improved type safety with explicit imports

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
