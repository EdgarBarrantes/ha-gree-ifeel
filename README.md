# Gree I Feel

Make a Gree air conditioner steer by a room thermometer of your choice, silently, over infrared.

Gree units measure the room with a sensor inside the indoor unit, which often reads well off the
room (near the floor, in the unit's own draught). Their remotes have **I Feel**: the remote measures
the room itself and sends the reading to the unit every few minutes, and the unit then heats or
cools by that reading instead. This integration does what the remote does, with any temperature
sensor in Home Assistant and any infrared emitter.

- **Silent.** I Feel reports don't make the unit beep (Wi-Fi commands do, on many models).
- **Checked.** With the unit's Wi-Fi climate entity linked, it checks that the unit's room
  temperature becomes the reported one.
- **Re-armed.** Units drop I Feel after a power cut or a gap in reports, and then ignore lone
  reports. When that happens, the integration sends one remote press with I Feel on (the unit
  beeps once) and reports again. Quiet hours keep that beep out of the night.

## Requirements

- Home Assistant 2026.10 or newer.
- An **infrared emitter** in Home Assistant that can reach the indoor unit's receiver: anything
  that shows up as an `infrared` entity (Broadlink, ESPHome, Shelly, ZHA or MQTT infrared
  emitters).
- A temperature sensor in the room.
- Optional: the unit's **climate entity**. The built-in Gree (Wi-Fi) integration allows checking
  and automatic re-arming. Gree Infrared works too, for the re-arm press's mode and set point.

## Install

Settings > Marketplace (HACS on older versions) > add this repository as a custom repository
(type Integration), install **Gree I Feel**, restart, then Settings > Devices & services >
Add integration > Gree I Feel.

## Set up

1. Pick the infrared emitter, the room temperature sensor and, if you have it, the unit's climate
   entity.
2. Open the entry's options and set:
   - **Reports:** how often (default every 2 minutes), an offset, whether to also send when the
     reading changes, and whether to pause while the unit is off.
   - **Checking and re-arming:** misses before acting (default 3), automatic re-arm on or off,
     quiet hours, and a re-arm schedule for units without Wi-Fi feedback.
   - **Re-arm press:** a remote press carries the unit's whole state. Mode and set point come from
     the climate entity; set fan, flap, display light and Health to what the unit uses, or the
     press changes them.

## Entities

| Entity | What it is |
|---|---|
| Reporting (switch) | Turn the reports off, for example while using the real remote |
| Re-arm I Feel (button) | One remote press with I Feel on (beeps once) |
| Send report (button) | Send the current reading now |
| Reported temperature | The last whole degree sent |
| Following reports (binary sensor) | On while the unit's room temperature matches the reports (only with a climate entity) |
| Unit's room temperature, Missed reports, Last report, Last re-arm | Diagnostics |

When the unit keeps ignoring the reports (automatic re-arm off, or 3 re-arms without effect), a
**repair issue** appears. Events for automations: `gree_ifeel_not_following`, `gree_ifeel_rearmed`,
`gree_ifeel_following`.

## Notes

- The real remote's own reports overwrite ours: leave its batteries out, or turn its I Feel off.
- Reports hold whole degrees Celsius (the protocol has nothing finer); use the offset to bias the
  rounding.
- Commands from other integrations may turn I Feel off (a press without the I Feel bit). The
  integration re-arms when it notices.
- The frames were checked against a YAN1F1-family remote and a floor console. Other Gree remotes
  use the same I Feel report as far as known; please open an issue if your unit ignores it.

## Protocol

I Feel report: 38 kHz, header 6000 / 3000 µs, 16 bits LSB first (mark 660, space 545 for 0, 1647
for 1) and a closing mark. Byte 0 is the temperature in whole degrees Celsius, byte 1 is `0xA5`.
The re-arm press is the remote's state frame (IRremoteESP8266's Gree layout) with the I Feel bit
(byte 5, bit 2) set. See `custom_components/gree_ifeel/protocol.py`.

## Development

```
uv venv --python 3.14 && uv pip install pytest-homeassistant-custom-component infrared-protocols
.venv/bin/python -m pytest -q
```

MIT licensed.
