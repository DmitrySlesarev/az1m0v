"""Compatibility facade for the EV IP/UART transport stack.

The old public imports used CAN naming. The implementation now uses a
self-written TCP/IP + UART endpoint model from :mod:`communication.ip_uart_transport`.
New code should import that module directly.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from communication.ip_uart_transport import (
    EVTCPIPProtocol,
    EndpointSwitch,
    FrameType,
    ITFrame,
    ITMessage,
    PacketCodec,
    TCPIPTransportInterface,
    TransportMode,
    UARTEndpoint,
    UARTFrameCodec,
)


class CANFrame(ITFrame):
    """Backwards-compatible frame constructor mapped to an IP/UART service frame."""

    def __init__(
        self,
        can_id: Optional[int] = None,
        data: bytes = b"",
        timestamp: Optional[float] = None,
        frame_type: FrameType = FrameType.DATA,
        is_extended: bool = False,
        is_remote: bool = False,
        dlc: Optional[int] = None,
        *,
        service_id: Optional[int] = None,
        source: str = "raspberry-pi",
        destination: str = "edge-switch",
        qos: int = 0,
        sequence: int = 0,
        ttl: int = 16,
        metadata: Optional[dict[str, Any]] = None,
    ):
        if service_id is None:
            if can_id is None:
                raise ValueError("service_id is required")
            service_id = can_id
        if dlc is not None and len(data) != int(dlc):
            raise ValueError(f"Data length ({len(data)}) must match DLC ({dlc})")
        super().__init__(
            service_id=service_id,
            payload=data,
            source=source,
            destination=destination,
            timestamp=timestamp if timestamp is not None else time.time(),
            frame_type=frame_type,
            qos=qos,
            sequence=sequence,
            ttl=ttl,
            metadata=metadata or {},
        )
        self.is_extended = is_extended
        self.is_remote = is_remote


class CANMessage(ITMessage):
    """Backwards-compatible message constructor mapped to an EV service message."""

    def __init__(
        self,
        message_id: int,
        name: str,
        description: str,
        data: dict[str, Any],
        timestamp: float,
        source: str,
        priority: int = 0,
        destination: str = "edge-switch",
    ):
        super().__init__(
            service_id=message_id,
            name=name,
            description=description,
            data=data,
            timestamp=timestamp,
            source=source,
            destination=destination,
            priority=priority,
        )


class CANBusInterface(TCPIPTransportInterface):
    """Compatibility wrapper over :class:`TCPIPTransportInterface`.

    Positional arguments retain their old names, but ``channel`` is now the
    endpoint identifier and ``interface`` is the transport mode. ``socketcan``
    maps to ``udp`` so existing Raspberry Pi configs automatically use the
    preferred IP stack.
    """

    def __init__(
        self,
        channel: str = "raspberry-pi",
        bitrate: int = 115200,
        interface: str = TransportMode.UDP.value,
        **kwargs: Any,
    ):
        mode = "udp" if interface == "socketcan" else interface
        if mode == "slcan":
            mode = "udp"
        super().__init__(
            endpoint_id=channel,
            mode=mode,
            bind_host=kwargs.get("bind_host", "0.0.0.0"),
            bind_port=kwargs.get("bind_port", 0),
            switch_host=kwargs.get("switch_host", "127.0.0.1"),
            switch_port=kwargs.get("switch_port", 9900),
            recv_timeout_s=kwargs.get("recv_timeout_s", 0.0),
        )
        self.channel = channel
        self.bitrate = bitrate
        self.interface = mode

    def get_statistics(self) -> dict[str, Any]:
        stats = super().get_statistics()
        stats.update(
            {
                "channel": self.channel,
                "bitrate": self.bitrate,
                "interface": self.interface,
            }
        )
        return stats


EVCANProtocol = EVTCPIPProtocol
CANFrameType = FrameType

__all__ = [
    "CANBusInterface",
    "CANFrame",
    "CANFrameType",
    "CANMessage",
    "EVCANProtocol",
    "EVTCPIPProtocol",
    "EndpointSwitch",
    "FrameType",
    "ITFrame",
    "ITMessage",
    "PacketCodec",
    "TCPIPTransportInterface",
    "TransportMode",
    "UARTEndpoint",
    "UARTFrameCodec",
]
