# Troubleshooting Guide

## Common Issues and Solutions

### Integration Won't Load

#### Symptom
Integration fails to load or shows "Failed to set up" error in Home Assistant.

#### Causes and Solutions

**1. Missing `timedelta` import (Fixed in Phase 1)**
- **Error**: `NameError: name 'timedelta' is not defined`
- **Solution**: Ensure you're running the latest version with Phase 1 fixes
- **Check**: Look in `__init__.py` for `from datetime import timedelta`

**2. Malformed YAML definition file**
- **Error**: `yaml.YAMLError` or `Failed to load definitions`
- **Solution**: Validate your YAML syntax
  ```bash
  python3 -c "import yaml; yaml.safe_load(open('custom_components/deye_modbus/definitions/deye_hybrid.yaml'))"
  ```
- **Common issues**:
  - Incorrect indentation (use spaces, not tabs)
  - Missing colons after keys
  - Unquoted special characters

**3. Connection issues**
- **Error**: `ModbusException` or `Connection timeout`
- **Solutions**:
  - **TCP**: Verify inverter IP address and port (usually 502)
  - **RTU**: Check serial port path (e.g., `/dev/ttyUSB0`)
  - **Firewall**: Ensure Modbus port 502 is not blocked
  - **Network**: Verify inverter and Home Assistant are on same network

### Configuration Flow Freezes

#### Symptom
Home Assistant UI becomes unresponsive during integration setup.

#### Cause
Blocking I/O operations in async context (Fixed in Phase 1).

#### Solution
Update to latest version with Phase 1 fixes that use `hass.async_add_executor_job()` for sync operations.

### Write Operations Fail

#### Symptom
Attempting to change a number, select, or time entity results in an error.

#### Common Errors and Solutions

**1. "Writes not implemented for this entity"**
- **Cause**: Entity is not in the writable whitelist
- **Solution**: Only specific entities support writes (ToU controls, battery limits)
- **Check**: See `_WRITABLE_NUMBER_KEYS`, `_WRITABLE_SELECT_KEYS`, `_WRITABLE_TIME_KEYS`

**2. "Value X is below minimum allowed value Y"**
- **Cause**: Input validation rejected the value
- **Solution**: Check entity attributes for `min` and `max` values
- **Example**: Battery SOC must be 0-100%

**3. "Converted value X is out of valid register range (0-65535)"**
- **Cause**: After scaling, value doesn't fit in 16-bit register
- **Solution**: This indicates a configuration error in the definition file
- **Action**: Report as bug with entity name and value attempted

**4. "Write verification failed: wrote X but read back Y"**
- **Cause**: Inverter rejected or modified the written value
- **Solutions**:
  - Check inverter mode/state (some values only writable in certain modes)
  - Verify value doesn't conflict with other settings
  - Try manual Modbus write to confirm inverter behavior
  - See [Write Verification Documentation](WRITE_VERIFICATION.md)

### Sensor Values Incorrect

#### Symptom
Sensor shows wrong value, `None`, or `Unknown`.

#### Causes and Solutions

**1. Decoding issues**
- **Symptom**: Temperature shows `None` instead of value
- **Check logs**: Look for `DEBUG` messages about decode failures
- **Common causes**:
  - BCD encoding issues
  - Wrong register order
  - Incorrect scale factor

**2. Numeric parsing from strings**
- **Symptom**: Sensor shows `None` for string values like "50 Hz"
- **Solution**: Update to latest version with Phase 3 improvements
- **Check**: Enable debug logging to see parsing errors:
  ```
  Failed to parse numeric value from '50 Hz' for grid_frequency: ValueError
  ```

**3. Wrong unit or scale**
- **Symptom**: Value is 10x or 100x too large/small
- **Solution**: Check `scale` parameter in definition file
- **Example**: If voltage shows 2300V instead of 230V, scale should be 0.1

### Entities Missing

#### Symptom
Expected entities don't appear in Home Assistant.

#### Causes and Solutions

**1. Battery mode filtering**
- **Cause**: Some entities are filtered based on battery chemistry
- **Solution**: Check integration options for battery type (Lead Acid vs Lithium)
- **Entities affected**: Battery control modes

**2. Wrong platform**
- **Cause**: Entity defined as wrong type in YAML
- **Solution**: Verify `platform:` matches expected entity type
  - `sensor` - Read-only numeric/text values
  - `binary_sensor` - On/Off states
  - `number` - Numeric inputs (writable subset)
  - `select` - Dropdown selections (writable subset)
  - `time` - Time inputs (writable subset)
  - `switch` - On/Off controls (read-only)
  - `datetime` - Timestamp values (read-only)

**3. Group filtering**
- **Cause**: Entity belongs to disabled group
- **Solution**: Check `group_name` in definition
- **Note**: All groups should be enabled by default

### Diagnostic Sensors

#### Finding Diagnostic Sensors

The integration includes 32 diagnostic sensors added in the latest version:

1. Open Home Assistant
2. Go to **Settings** → **Devices & Services**
3. Click on **Deye Modbus** integration
4. Click on your inverter device
5. Click **Show disabled entities** (diagnostic entities are disabled by default)
6. Enable the sensors you want to monitor

#### Useful Diagnostic Sensors

| Sensor | Purpose | When to Use |
|--------|---------|-------------|
| Battery Status | Shows Standby/Charging/Discharging | Monitoring battery behavior |
| Grid/Generator Relay Status | Shows connection state | Debugging grid/gen switching |
| Inverter Work Mode | Shows operational mode | Understanding inverter state |
| RCD Leakage Current | Safety monitoring | Detecting ground faults |
| BMS Connect State | Battery communication | Debugging battery issues |

### Performance Issues

#### Symptom
Integration causes Home Assistant slowdown or high CPU usage.

#### Causes and Solutions

**1. Too frequent polling**
- **Default**: Fast (2s), Slow (5s)
- **Solution**: Increase intervals in integration options
- **Note**: Longer intervals = less current data

**2. Too many enabled entities**
- **Solution**: Disable unnecessary diagnostic sensors
- **Action**: Keep only entities you actually use

**3. Modbus errors causing retries**
- **Check logs**: Look for repeated Modbus errors
- **Solution**: Fix underlying connection issue

### Error Handling and Logging

#### Understanding Log Levels

The integration uses structured logging:

```yaml
# Enable debug logging in configuration.yaml
logger:
  default: warning
  logs:
    custom_components.deye_modbus: debug
    custom_components.deye_modbus.number: debug
    custom_components.deye_modbus.select: debug
```

#### Log Message Types

| Level | Meaning | Action Required |
|-------|---------|-----------------|
| DEBUG | Informational detail | No action - only for debugging |
| INFO | Normal operation | No action - successful operations |
| WARNING | Non-critical issue | Monitor - may indicate problem |
| ERROR | Failed operation | Action needed - check details |

#### Common Log Messages

**"Write verification OK for X: value Y confirmed"** (DEBUG)
- Meaning: Write succeeded and verified
- Action: None

**"Failed to parse numeric value from 'X' for Y"** (DEBUG)
- Meaning: String value couldn't be converted to number
- Action: Check sensor definition if value should be numeric

**"Failed to verify write for X at register Y"** (WARNING)
- Meaning: Verification read failed, but write may have succeeded
- Action: Check Modbus connection stability

**"Write verification FAILED for X: wrote Y but read back Z"** (ERROR)
- Meaning: Inverter rejected or modified the value
- Action: See [Write Verification Guide](WRITE_VERIFICATION.md)

### Manual Modbus Testing

If you suspect a Modbus communication issue, you can test manually:

#### Using `modbus-cli` (Linux)

```bash
# Install modbus-cli
pip3 install modbus-cli

# Read a register (TCP)
modbus read --address 0x0003 --count 1 192.168.1.100

# Write a register (TCP)
modbus write --address 0x0100 --value 500 192.168.1.100

# Read from RTU
modbus read --address 0x0003 --count 1 /dev/ttyUSB0 --baud 9600
```

#### Using `mbpoll` (Cross-platform)

```bash
# Install mbpoll
# apt install mbpoll  # Debian/Ubuntu
# brew install mbpoll  # macOS

# Read holding registers (TCP)
mbpoll -a 1 -r 4 -c 1 -t 4 192.168.1.100

# Read holding registers (RTU)
mbpoll -a 1 -r 4 -c 1 -t 4 -b 9600 -P none -m rtu /dev/ttyUSB0
```

### Getting Help

#### Before Reporting Issues

1. **Check logs** - Look for ERROR and WARNING messages
2. **Enable debug logging** - Provides detailed information
3. **Test Modbus manually** - Isolate integration vs inverter issues
4. **Check similar issues** - Search GitHub issues for similar problems

#### What to Include in Bug Reports

1. **Version information**
   - Home Assistant version
   - Integration version
   - Inverter model and firmware version

2. **Logs**
   - Relevant ERROR/WARNING messages
   - Debug logs if available
   - Full stack trace if present

3. **Configuration**
   - Connection type (TCP/RTU)
   - Custom configuration (if any)
   - Affected entities

4. **Steps to reproduce**
   - What you did
   - What you expected
   - What actually happened

5. **Modbus test results** (if applicable)
   - Can you read/write the register manually?
   - What values do you get?

### Known Limitations

1. **Switch entities are read-only** - This is intentional for safety
2. **DateTime entities are read-only** - Write support not implemented
3. **Some values only writable in specific modes** - Inverter limitation
4. **Single register writes only** - Multi-register writes not yet supported

### Recent Fixes

See [CHANGELOG.md](../CHANGELOG.md) for complete history:

- **Phase 1**: Critical bug fixes (timedelta import, datetime decoder, YAML parsing, blocking I/O, bounds checking, write verification)
- **Phase 2**: Code duplication elimination (device_info.py module)
- **Phase 3**: Code quality & safety (error handling, type hints, logging)
- **Phase 4**: Testing & documentation (unit tests, guides)

### Reporting New Issues

Create an issue on GitHub with:
- Clear title describing the problem
- All information from "What to Include" above
- Label as `bug` for defects or `question` for help

### Contributing

Found a fix? Please:
1. Fork the repository
2. Create a feature branch
3. Add tests if applicable
4. Submit a pull request

## Quick Reference

### Integration Options

| Option | Default | Purpose |
|--------|---------|---------|
| Fast interval | 2s | Frequency for dynamic sensors |
| Slow interval | 5s | Frequency for static sensors |
| Battery type | Lithium | Filters battery mode options |

### Writable Entities

**Number Entities** (ToU, Battery):
- Program 1-6 Power, Voltage, SOC
- Battery current limits
- Battery SOC thresholds

**Select Entities** (ToU, Modes):
- Time of Use enable/disable
- Program 1-6 charging modes

**Time Entities** (ToU):
- Program 1-6 time slots

### File Locations

- Definitions: `custom_components/deye_modbus/definitions/deye_hybrid.yaml`
- Configuration: `custom_components/deye_modbus/config_flow.py`
- Platform files: `custom_components/deye_modbus/*.py`
- Tests: `tests/*.py`
- Docs: `docs/*.md`
