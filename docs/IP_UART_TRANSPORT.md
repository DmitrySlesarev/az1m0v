# IP/UART vehicle transport

This repository no longer needs a CAN controller library for the EV application
messages. The Raspberry Pi side uses a self-written TCP/IP model with UDP as
the preferred host transport, then an edge switch converts those application
frames into UART/COM byte streams for endpoint devices such as the engine
controller, battery controller, charger, or Arduino peripheral.

## Layer model

1. Application layer
   - `EVTCPIPProtocol` builds EV service messages such as `BMS_STATUS`,
     `MOTOR_STATUS`, `VESC_SET_RPM`, and Arduino peripheral commands.
   - Service IDs are 16-bit application service numbers, not CAN arbitration
     IDs. Payloads are not limited to 8 bytes.
2. Transport/network layer
   - `TCPIPTransportInterface` sends frames to the edge switch.
   - Default mode is UDP (`mode: "udp"`). TCP and an in-memory `virtual` mode
     are available for lab tests.
3. Edge switch
   - `EndpointSwitch` receives a UDP/TCP packet, validates the packet CRC, and
     chooses a UART endpoint from the frame destination (`engine`, `battery`,
     `charger`, `peripheral`, etc.).
4. Link/physical endpoint layer
   - `UARTFrameCodec` wraps the same application packet with SLIP framing so it
     can move safely through a COM/UART stream.
   - `UARTEndpoint` writes the framed bytes to `/dev/ttyUSB*`, `/dev/ttyACM*`,
     or another serial device.

## Raspberry Pi configuration

The default config block is:

```json
"tcpip_uart": {
  "endpoint_id": "raspberry-pi",
  "mode": "udp",
  "bind_host": "0.0.0.0",
  "bind_port": 0,
  "switch_host": "127.0.0.1",
  "switch_port": 9900,
  "recv_timeout_s": 0.0,
  "uart_baudrate": 115200,
  "endpoints": {
    "engine": {"port": "/dev/ttyUSB0", "baudrate": 115200},
    "battery": {"port": "/dev/ttyUSB1", "baudrate": 115200},
    "charger": {"port": "/dev/ttyUSB2", "baudrate": 115200},
    "peripheral": {"port": "/dev/ttyACM0", "baudrate": 115200}
  }
}
```

For a single Raspberry Pi that also hosts the edge switch process, keep
`switch_host` as `127.0.0.1`. If the switch is another board, set it to that
board's LAN IP and keep UDP port `9900` or choose a port allowed by your
network.

## Engine kit wiring pattern

Example flow for an engine command:

1. EV control code calls `EVTCPIPProtocol.send_vesc_command_rpm(...)`.
2. The frame is encoded as an `AZIP` packet and sent by UDP to the switch.
3. The switch decodes and validates the packet.
4. Because the destination is `engine`, the switch writes a SLIP-framed packet
   to the configured engine UART, for example `/dev/ttyUSB0`.
5. The engine-side firmware reads from UART, strips SLIP framing, validates the
   `AZIP` packet, then consumes the service payload.

The Arduino peripheral uses the same route. Its compact status and command
payloads live in `communication/uart_peripheral.py`; the serial stream framing
is still handled by `UARTFrameCodec`.

## Local tests without hardware

Run the focused unit tests:

```bash
poetry run pytest tests/unit/test_ip_uart_transport.py tests/unit/test_can_bus.py tests/unit/test_arduino_can_bridge.py
```

The tests use `virtual` transport mode and fake serial objects so no Raspberry
Pi UART devices are required.

## Hardware smoke test idea

On a Raspberry Pi with a USB-UART adapter connected to the engine kit:

1. Confirm the device path:
   ```bash
   python -m serial.tools.list_ports
   ```
2. Put that path under `tcpip_uart.endpoints.engine.port`.
3. Start the EV system normally.
4. On the endpoint firmware side, read SLIP-delimited frames and decode the
   `AZIP` packet format: magic `AZIP`, version byte, body length, JSON body,
   and CRC32.

If you only want to validate the switch path first, configure a loopback UART
pair or run the tests with the fake serial endpoint.
