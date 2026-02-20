# SPDX-FileCopyrightText: 2023 Adafruit Industries
#
# SPDX-License-Identifier: MIT


"""
`adafruit_seesaw.spi`
====================================================

CircuitPython-compatible SPI interface via the SeeSaw SERCOM module.

Enables SPI peripherals (e.g. the Adafruit SPI FRAM Breakout,
product ID 4719) to be driven through an ATtiny817 SeeSaw chip over I2C.

* Author(s): Adafruit Industries

Implementation Notes
--------------------

**Hardware:**

* Adafruit ATtiny817 Seesaw Breakout:
  https://www.adafruit.com/product/5681
* Adafruit SPI Non-Volatile FRAM Breakout - 4 Mbit / 512 KBytes - MB85RS4MT
  (Product ID: 4719)

**Software and Dependencies:**

* Adafruit CircuitPython firmware: https://circuitpython.org/
* or Adafruit Blinka: https://circuitpython.org/blinka
* Adafruit's Bus Device library:
  https://github.com/adafruit/Adafruit_CircuitPython_BusDevice
"""

import struct

try:
    from micropython import const
except ImportError:

    def const(x):
        return x


__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_seesaw.git"

_SERCOM0_BASE = const(0x02)
_SERCOM_BAUD = const(0x04)
_SERCOM_DATA = const(0x05)


class SPIDevice:
    """CircuitPython-compatible SPI interface using the SeeSaw SERCOM.

    This class is intended to be a compatible subset of `busio.SPI`.
    Chip-select (CS) is left to the caller; use a
    :class:`~adafruit_seesaw.digitalio.DigitalIO` pin for CS management.

    :param ~adafruit_seesaw.seesaw.Seesaw seesaw: The SeeSaw device
    :param int baudrate: SPI clock frequency in Hz (default 100 000)
    :param int polarity: Clock polarity – 0 (idle low) or 1 (idle high)
    :param int phase: Clock phase – 0 (sample on leading edge) or
        1 (sample on trailing edge)

    Example::

        import board
        from adafruit_seesaw.seesaw import Seesaw
        from adafruit_seesaw.spi import SPIDevice
        from adafruit_seesaw.digitalio import DigitalIO
        import digitalio

        i2c = board.I2C()
        seesaw = Seesaw(i2c)

        spi = SPIDevice(seesaw, baudrate=100_000)

        cs = DigitalIO(seesaw, 4)
        cs.direction = digitalio.Direction.OUTPUT
        cs.value = True          # deassert CS

        # send a byte and receive the response
        cs.value = False         # assert CS
        spi.write(bytes([0x9F]))
        result = bytearray(4)
        spi.readinto(result)
        cs.value = True          # deassert CS
    """

    def __init__(self, seesaw, baudrate=100000, polarity=0, phase=0):
        self._seesaw = seesaw
        self.configure(baudrate=baudrate, polarity=polarity, phase=phase)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def configure(self, baudrate=100000, polarity=0, phase=0, bits=8):
        """Configure the SPI bus.

        :param int baudrate: SPI clock frequency in Hz
        :param int polarity: Clock polarity – 0 or 1
        :param int phase: Clock phase – 0 or 1
        :param int bits: Bits per transfer; only 8 is supported
        """
        if bits != 8:
            raise ValueError("Only 8-bit SPI transfers are supported")
        if polarity not in {0, 1}:
            raise ValueError("polarity must be 0 or 1")
        if phase not in {0, 1}:
            raise ValueError("phase must be 0 or 1")

        # 4-byte big-endian baud rate followed by a mode byte
        # mode byte: bits[1:0] = polarity | phase  (same encoding as SPI mode)
        mode = (polarity << 1) | phase
        cmd = struct.pack(">IB", baudrate, mode)
        self._seesaw.write(_SERCOM0_BASE, _SERCOM_BAUD, cmd)

    # ------------------------------------------------------------------
    # Data transfer
    # ------------------------------------------------------------------

    def write(self, buf, start=0, end=None):
        """Write the bytes in *buf* out over SPI.

        :param bytes buf: Data to transmit
        :param int start: Index of the first byte to send
        :param int end: Index after the last byte to send (``None`` = all)
        """
        if end is None:
            end = len(buf)
        self._seesaw.write(_SERCOM0_BASE, _SERCOM_DATA, buf[start:end])

    def readinto(self, buf, start=0, end=None, write_value=0):
        """Read bytes from SPI into *buf*.

        The SeeSaw clocks out *write_value* on MOSI for each byte read.

        :param bytearray buf: Buffer to read into
        :param int start: Index of the first byte position to fill
        :param int end: Index after the last byte position (``None`` = all)
        :param int write_value: Byte value to clock out on MOSI while reading
        """
        if end is None:
            end = len(buf)
        count = end - start

        # Send the requested number of write_value bytes so the SeeSaw
        # clocks the SPI peripheral and captures the MISO data.
        out = bytearray([write_value] * count)
        self._seesaw.write(_SERCOM0_BASE, _SERCOM_DATA, out)

        # Retrieve the bytes captured on MISO.
        self._seesaw.read(_SERCOM0_BASE, _SERCOM_DATA, buf[start:end])

    def write_readinto(
        self,
        buffer_out,
        buffer_in,
        out_start=0,
        out_end=None,
        in_start=0,
        in_end=None,
    ):
        """Simultaneously write *buffer_out* and read into *buffer_in*.

        Both buffers must cover the same number of bytes (after applying
        the start/end slices).

        :param bytes buffer_out: Data to transmit
        :param bytearray buffer_in: Buffer to receive into
        :param int out_start: Start index in *buffer_out*
        :param int out_end: End index in *buffer_out* (``None`` = all)
        :param int in_start: Start index in *buffer_in*
        :param int in_end: End index in *buffer_in* (``None`` = all)
        """
        if out_end is None:
            out_end = len(buffer_out)
        if in_end is None:
            in_end = len(buffer_in)

        if (out_end - out_start) != (in_end - in_start):
            raise ValueError("buffer slices must be the same length")

        # Transmit the outgoing bytes; the SeeSaw captures MISO in parallel.
        self._seesaw.write(_SERCOM0_BASE, _SERCOM_DATA, buffer_out[out_start:out_end])

        # Retrieve the bytes captured on MISO.
        self._seesaw.read(_SERCOM0_BASE, _SERCOM_DATA, buffer_in[in_start:in_end])

    def deinit(self):
        """Release the SPI device."""
        pass
