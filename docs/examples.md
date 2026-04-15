# Examples

The `gardena_smart_local_api/examples/` directory contains runnable scripts that
demonstrate the library. They all share a common base (`ExampleApp`) and accept the
same core arguments.

## Running examples

Install the example dependencies and run a script directly:

```
uv sync --group examples
uv run gardena_smart_local_api/examples/irrigation.py --help
```

## Common arguments

All examples accept:

| Argument | Description |
| -------- | ----------- |
| `-g` / `--gateway` | Gateway hostname (e.g. `GARDENA-123456`) or IP address |
| `-p` / `--password` | First 8 characters of the ID on the back of the gateway |
| `-d` / `--device-id` | ID of the specific device to target |
| `-w` / `--wait` | Keep running after the command, printing event counts |
| `-j` / `--dump-json` | Write each received message to a timestamped JSON file |

Use the `list` command (available in every example) to discover device IDs:

```
uv run gardena_smart_local_api/examples/irrigation.py \
    --gateway GARDENA-123456 --password MYPASSWD list
```

## irrigation.py

Controls water controls and the irrigation controller. Compatible devices:
`Gen1WaterControl`, `Gen2WaterControl`, `Gen2IrrigationControl`.

```
irrigation.py -g <gw> -p <pw> list
irrigation.py -g <gw> -p <pw> -d <id> start [valve_id] [duration_seconds]
irrigation.py -g <gw> -p <pw> -d <id> stop  [valve_id]
```

- **list** — print IDs and names of all compatible devices.
- **start** — open a valve for `duration` seconds (default: 60). `valve_id` selects
  which valve to open (0-indexed, default: 0). Gen1 devices only have valve 0.
- **stop** — close a valve. Omitting `valve_id` closes all valves.

After a `start` on a gen2 device the example checks the resulting timeslot state
and warns if the device refused to start (e.g. due to a duty-cycle limit).

## mower.py

Controls SILENO robotic mowers. Compatible devices: `Gen1Mower1`, `Gen1Mower2`.

```
mower.py -g <gw> -p <pw> list
mower.py -g <gw> -p <pw> -d <id> start [duration_hours]
mower.py -g <gw> -p <pw> -d <id> stop
mower.py -g <gw> -p <pw> -d <id> status
```

- **start** — begin a mowing session for `duration` hours (default: 1).
- **stop** — send the mower back to its charging station.
- **status** — print the current mower status string.

## sensor.py

Reads values from smart sensors. Compatible devices: `Sensor1`, `Sensor2`.

```
sensor.py -g <gw> -p <pw> list
sensor.py -g <gw> -p <pw> -d <id> read [duration_seconds]
```

- **read** — trigger measurement requests and display a live-updating readout for
  `duration` seconds (default: 1). Reported values:
  - Temperature (°C)
  - Soil moisture (%)
  - Light (lx) — Sensor1 only
  - Battery level (%)
  - RF link quality (%)
  - Frost warning

## power.py

Controls the smart Power Adapter. Compatible devices: `PowerAdapter`.

```
power.py -g <gw> -p <pw> list
power.py -g <gw> -p <pw> -d <id> on  [duration_seconds]
power.py -g <gw> -p <pw> -d <id> off
power.py -g <gw> -p <pw> -d <id> identify
```

- **on** — enable the output socket for `duration` seconds (default: 60).
- **off** — disable the output socket immediately.
- **identify** — blink the device's LED for visual identification.

## ExampleApp

`ExampleApp` is the shared base used by all examples. It handles:

- Argument parsing (with support for script-specific extra arguments)
- Establishing the WebSocket connection with TLS and Basic Auth
- Running device discovery and building the `DeviceMap`
- A background receiver task that dispatches incoming messages to events or replies
- A background updater task that applies incoming events to device state
- `send_request()` — sends a request list and waits (up to 10 seconds) for all
  matching replies
- `--wait` mode that keeps the connection open for ongoing event monitoring
- `--dump-json` mode that writes every received message to a file

`ExampleApp` is designed to be used as an async context manager. Your script
connects and discovers devices in `__aenter__` and cleans up in `__aexit__`.
