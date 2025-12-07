# Write Verification Feature

## Overview

The Deye Modbus integration implements **automatic read-after-write verification** for all writable entities (number, select, and time entities). This feature helps detect when the inverter rejects or modifies written values, providing immediate feedback to users.

## Why Write Verification?

During testing and user reports, we discovered that some inverter register writes would appear successful but the inverter would:
- Reject the value and keep the old one
- Modify the value to something different (e.g., ToU SOC jumping between 100 and 15)
- Silently fail without any error indication

Without verification, these issues could go unnoticed, leading to incorrect automation behavior and user confusion.

## How It Works

### Basic Flow

For every write operation to a writable entity:

1. **Validate** - Check that the value is within allowed ranges
2. **Convert** - Transform the user value to raw register format
3. **Write** - Send the value to the inverter via Modbus
4. **Verify** - Immediately read back the register value
5. **Compare** - Check if the read value matches what was written
6. **Alert** - Raise an error if verification fails

### Example: Number Entity Write

```python
# User sets battery_max_charging_current to 50A
await entity.async_set_native_value(50)

# 1. Validate: 50A is within range (0-200A) ✓
# 2. Convert: 50A * (1/0.1) = 500 raw value
# 3. Write: Write 500 to register 0x0108
# 4. Verify: Read register 0x0108
# 5. Compare: Read value is 500 ✓
# 6. Success: Refresh coordinator data
```

### Example: Write Verification Failure

```python
# User sets program_1_soc to 100%
await entity.async_set_native_value(100)

# 1. Validate: 100% is within range (0-100%) ✓
# 2. Convert: 100% → 100 raw value
# 3. Write: Write 100 to register 0x00B0
# 4. Verify: Read register 0x00B0
# 5. Compare: Read value is 15 (inverter rejected our value!) ✗
# 6. ERROR: "Write verification failed: wrote 100 but read back 15"
```

## Masked Writes (Select Entities)

Some registers contain multiple settings in different bit positions. For these, we use **masked writes** to preserve other bits:

### Example: Masked Write with Verification

```python
# Register 0x00F0 structure:
# Bits 0-3: Program charge mode
# Bits 4-7: Other settings (should be preserved)

# Current register value: 0b11110000 (240)
# User selects "Enabled" (value 3 = 0b0011)
# Mask: 0b00001111 (preserve upper 4 bits)

# 1. Read current value: 0b11110000
# 2. Apply mask: (0b11110000 & ~0b00001111) | (0b0011 & 0b00001111)
#    Result: 0b11110011
# 3. Write: 0b11110011 to register
# 4. Verify read: 0b11110011
# 5. Compare masked bits: (0b11110011 & 0b00001111) == (0b0011 & 0b00001111) ✓
#    Only the lower 4 bits are checked - upper bits can vary
```

## Error Handling

### Verification Failure

When verification fails, the integration:

1. **Logs an error** with details about what was written vs. what was read
2. **Raises HomeAssistantError** - This appears in the Home Assistant UI
3. **Does NOT refresh coordinator** - Prevents showing incorrect state

Example error log:
```
ERROR: Write verification FAILED for battery_max_charging_current:
wrote 500 but read back 100 (register 0x0108)
```

### Verification Error (Read Failure)

If the verification read itself fails:

1. **Logs a warning** - Documents the issue for debugging
2. **Does NOT fail the write** - Assumes write succeeded
3. **Refreshes coordinator** - Updates state from inverter

Example warning log:
```
WARNING: Failed to verify write for battery_max_charging_current at
register 0x0108: ModbusError
```

## Logging Levels

The integration uses different log levels for different scenarios:

| Level | Scenario | Example |
|-------|----------|---------|
| `DEBUG` | Successful verification | "Write verification OK for battery_max_charging_current: value 500 confirmed at register 0x0108" |
| `INFO` | Successful write | "Wrote number battery_max_charging_current (value=50 -> raw=500) to register 0x0108" |
| `WARNING` | Verification read error | "Exception during write verification for battery_max_charging_current: Timeout" |
| `ERROR` | Verification mismatch | "Write verification FAILED for battery_max_charging_current: wrote 500 but read back 100" |

## Configuration

Write verification is **always enabled** and cannot be disabled. This is by design to ensure data integrity.

## Performance Impact

- **Minimal** - Each write takes ~2x as long (one write + one read)
- **Writes are infrequent** - Most entities are read-only sensors
- **Benefit outweighs cost** - Detecting write failures is critical

## Debugging Write Issues

If you encounter write verification failures:

### 1. Check the Logs

Look for ERROR messages with "Write verification FAILED":

```
2025-12-07 15:30:45 ERROR [custom_components.deye_modbus.number]
Write verification FAILED for program_1_soc: wrote 100 but read back 15 (register 0x00B0)
```

This tells you:
- **What entity** had the issue (`program_1_soc`)
- **What you tried to write** (100)
- **What the inverter actually has** (15)
- **Which register** (0x00B0)

### 2. Common Causes

**Inverter Restrictions**
- Some values can only be set when the inverter is in certain modes
- Example: Can't change battery settings while battery is charging

**Value Conflicts**
- Writing contradictory values to related registers
- Example: Setting SOC higher than another SOC threshold

**Firmware Limitations**
- Some firmware versions reject certain values
- Check if firmware update is available

**Timing Issues**
- Inverter may need time to process previous writes
- Try waiting a few seconds before retrying

### 3. Enable Debug Logging

Add to `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.deye_modbus: debug
```

This will show successful writes and detailed verification info.

### 4. Manual Verification

You can use a Modbus tool to verify the register value directly:
```bash
# Example using modbus-cli
modbus read --address 0x00B0 --count 1 YOUR_INVERTER_IP
```

## Related Features

- **Input Validation** - Values are validated before write (see Phase 1 fixes)
- **Range Checking** - Values must be within min/max bounds from definitions
- **Scale Conversion** - Values are properly scaled before writing

## Implementation Details

For developers interested in the implementation:

- **number.py** lines 156-196: Write verification for number entities
- **select.py** lines 142-197: Masked write verification for select entities
- **time.py** lines 134-174: Write verification for time entities
- **CHANGELOG.md**: Full history of write verification feature development

## Future Improvements

Potential enhancements being considered:

- **Retry logic** - Automatically retry failed writes with exponential backoff
- **Verification delay** - Add configurable delay before verification read
- **Partial verification** - For multi-register writes, verify each register
- **Write queue** - Prevent concurrent writes to same register
