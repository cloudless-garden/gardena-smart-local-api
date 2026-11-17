# Schema files

Each supported device model has a YAML schema file in
`gardena_smart_local_api/schema/`. These files describe the IPSO objects and
resources exposed by the device, and are loaded at runtime by `ModelLoader`.

## File naming

Files are named `{model_number}_{device_name}.yaml`, where the model number is the
EAN suffix printed on the device label (visible in the `Supported Devices` table in
the README). For example, `18869_water_control.yaml` describes the smart Water
Control with model number 18869.

## File structure

```yaml
name: smart Water Control       # Human-readable device name
protocol: gen1                  # gen1 or gen2
commands:                       # gen1 only: named command codes
  reboot: 31
  reset_all_valve_errors: 36
objects:
  lemonbeat:                    # IPSO object name
    resources:
      watering_timer_1:         # Resource name
        type: vi                # Value type
        access: rw              # Access mode
        unit: s                 # Optional unit
        min: -36000             # Optional constraint
        max: 36000
        description: >-
          Watering timer (write >0=start manual, ...)
```

Multi-instance objects (gen2) carry `multi_instance: true`:

```yaml
objects:
  actuator:
    multi_instance: true
    resources:
      state:
        type: vi
        access: r
```

## Resource types

| Type | Python type  | Description                          |
| ---- | ------------ | ------------------------------------ |
| `vb` | `bool`       | Boolean                              |
| `vi` | `int`        | Integer                              |
| `vf` | `float`      | Float                                |
| `vs` | `str`        | String                               |
| `vo` | `bytes`      | Opaque (base64-encoded over the wire)|
| `ai` | `list[int]`  | Integer array                        |
| `as` | `list[str]`  | String array                         |

Executable resources (`access: x`) have `type: null` — they carry no value and are
invoked by sending a write request to their path with arguments in the payload.

## Access modes

| Mode | Meaning                    |
| ---- | -------------------------- |
| `r`  | Read-only                  |
| `rw` | Read and write             |
| `w`  | Write-only                 |
| `x`  | Executable (gen2)          |

## Gen1 commands

Gen1 devices do not use executable resources. Instead, they expose a single
`command` resource on the `lemonbeat` object that accepts an integer code. The
schema `commands` section maps human-readable names to those codes:

```yaml
commands:
  reboot: 31
  measure_battery: 6
  reset_all_valve_errors: 36
```

## Error fields

Errors are surfaced through several fields depending on device generation:

**`device/0/error_code`** (both gen1 and gen2)
: LwM2M standard integer array. Non-empty when the device reports an error
  condition. Values are device-specific.

**`lemonbeat/0/error`** (gen1)
: Enum-style integer: `0=none`, `1=eeprom`, `2=brown_out`.

**`lemonbeat/0/valve_error_1`** (gen1 water controls)
: Valve error: `0=none`, `1=valve_broken`, `2=frost_prevents_starting`,
  `3=low_battery_prevents_starting`, `4=valve_power_supply_failed`.

**`actuator/{id}/error`** (gen2)
: Actuator-specific error integer. Values are model-dependent.

**`irrigation_control/0/error`** (gen2 Irrigation Control)
: Device-level error integer.

**`firmware_update/0/update_result`** (both)
: Result of the last firmware update attempt:
  `0=Initial, 1=Success, 2=Not enough storage, 3=Out of memory,
  4=Connection lost, 5=CRC check failure, 6=Unsupported package type,
  7=Invalid URI, 8=Update failed, 9=Unsupported protocol`.

Protocol-level errors (e.g. unknown device, bad request) are returned as an
`ErrorMessage` rather than a `Reply`. The `error_source` field identifies which
part of the gateway rejected the request, and `error_message` contains a
human-readable description.

## Adding a new device

1. Create `gardena_smart_local_api/schema/{model_number}_{name}.yaml`.
2. Set `protocol` to `gen1` or `gen2`.
3. List all IPSO objects and resources the device exposes, with types and access
   modes. Descriptions and units are optional but helpful.
4. If the device has a distinct behaviour (e.g. new actuator type), add a
   corresponding subclass in `gardena_smart_local_api/devices/`.
