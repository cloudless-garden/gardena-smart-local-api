# Architecture

## Connection

The **GARDENA smart Gateway** is reachable over a TLS WebSocket on port **8443** and
acts as a bridge to the individual devices. The library wraps the protocol; WebSocket
connection handling is left to the caller (e.g. the Home Assistant integration).

Authentication uses HTTP Basic Auth with a password equal to the first 8 characters
of the ID printed on the back of the gateway (username is ignored on the gateway):

```
wss://GARDENA-123456:8443
Authorization: Basic base64("_:a3f2c8b1")
```

The gateway's TLS certificate is self-signed, so certificate verification must be
disabled on the client side.

## Protocol

GARDENA devices speak a JSON-based protocol derived from
[OMA LwM2M](https://www.openmobilealliance.org/solutions/lightweight-m2m-lwm2m/)
(Lightweight M2M) and the underlying
[IPSO Smart Objects](https://www.openmobilealliance.org/release/LightweightM2M/)
resource model.

State is organized as a tree of **objects** and **resources**:

```
{object_name}/{instance_id}/{resource_name}/{resource_instance_id}
```

For example, `lemonbeat/0/watering_timer_1` identifies the watering timer resource
on the first instance of the `lemonbeat` object. The `IpsoPath` class models these
paths and handles serialization.

## Device generations

There are two protocol generations, determined by the `protocol` field in each
device's [schema file](schema.md):

**Gen1** (older devices, e.g. Water Control 18869)
: Communicate with the gateway over a proprietary RF protocol (lemonbeat). The
  gateway translates these to the WebSocket protocol. Device objects include
  `lemonbeat`, `lemonbeat_status_message`, `connection_status`, `device`, and
  `firmware_update`. Commands are sent by writing an integer command code to
  `lemonbeat/0/command`.

**Gen2** (newer devices, e.g. Irrigation Control 469)
: Communicate with the gateway over OMA Lightweight M2M (LwM2M). Device objects include
  `actuator`, `timeslot`, `schedule`, `sg_common`, `device`, `firmware_update`,
  and `connection_status`. Actions (start, stop, identify, etc.) are sent as
  executable resources.

## Message flow

All messages are JSON arrays. The library models these with Pydantic:

**Outgoing (`EgressMessageList`)** — a list of `Request` objects. Each request
targets an IPSO path, specifies an operation (`read`, `write`, `execute`), and
carries an optional payload. Requests include a UUID `request_id` so replies can
be matched.

**Incoming** — parsed by `validate_message()` into one of three types:

- `Event` — unsolicited state update from the gateway (op: `update`, `overwrite`,
  or `delete`). Used to keep device state current.
- `Reply` — response to a `Request`. Contains `success: true/false` and the same
  `request_id`.
- `ErrorMessage` — protocol-level error. Contains an `error_source` and an
  `error_message` string. `success` is always `false`.

## Device discovery

Before any device can be controlled, a discovery request must be sent. The helper
`build_discovery_obj()` builds the appropriate request list. The replies contain the
current state of all registered devices. `create_devices_from_messages()` parses
those replies, looks up the matching schema by model number, and returns a
`DeviceMap` keyed by device ID.

## Device model

All device types extend `Device`, which stores raw IPSO state as a nested dict and
exposes it via `get_value(path)`. Device subclasses add typed properties and
`build_*_obj()` helper methods that return ready-to-send `EgressMessageList`
instances.

Incoming `Event` messages are applied to the device state via `update_data()`,
keeping properties up to date as long as the WebSocket connection is open.
