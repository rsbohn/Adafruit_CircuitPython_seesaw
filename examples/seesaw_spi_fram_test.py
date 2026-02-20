# SPDX-FileCopyrightText: 2023 Adafruit Industries
# SPDX-License-Identifier: MIT
"""
SeeSaw SPI FRAM example — Adafruit SPI Non-Volatile FRAM Breakout (MB85RS4MT)
Product ID 4719: https://www.adafruit.com/product/4719

Wiring (ATtiny817 SeeSaw ↔ MB85RS4MT FRAM):
  SeeSaw pin 1 (MOSI/PA1)  → FRAM SI
  SeeSaw pin 2 (MISO/PA2)  → FRAM SO
  SeeSaw pin 3 (SCK/PA3)   → FRAM SCK
  SeeSaw pin 4 (CS/PA4)    → FRAM CS
  SeeSaw 3V3               → FRAM VCC
  SeeSaw GND               → FRAM GND
  SeeSaw GND               → FRAM WP  (write-protect tied low = always writable)
  SeeSaw GND               → FRAM HOLD (tied low = hold disabled)

Host microcontroller connects to the SeeSaw breakout over I2C (SDA/SCL).
"""

import board
import digitalio

from adafruit_seesaw.digitalio import DigitalIO
from adafruit_seesaw.seesaw import Seesaw
from adafruit_seesaw.spi import SPIDevice

# ── SeeSaw ──────────────────────────────────────────────────────────────────
i2c = board.I2C()  # uses board.SCL and board.SDA
# i2c = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector

seesaw = Seesaw(i2c)

# ── SPI bus via SeeSaw SERCOM ───────────────────────────────────────────────
# MB85RS4MT supports SPI mode 0 (polarity=0, phase=0), up to 40 MHz.
# Keep the SeeSaw clock conservative.
spi = SPIDevice(seesaw, baudrate=100_000, polarity=0, phase=0)

# ── Chip-select (active-low) ────────────────────────────────────────────────
cs_pin = seesaw.pin_mapping.spi_cs_pin  # PA4 on ATtiny817
cs = DigitalIO(seesaw, cs_pin)
cs.direction = digitalio.Direction.OUTPUT
cs.value = True  # deassert CS

# ── MB85RS4MT helper constants ───────────────────────────────────────────────
_RDID = 0x9F  # Read Device ID
_RDSR = 0x05  # Read Status Register
_WREN = 0x06  # Write Enable
_WRITE = 0x02  # Write Memory
_READ = 0x03  # Read Memory


def _cmd(spi_bus, cs, *bytes_out):
    """Send bytes and return nothing (write-only transaction)."""
    cs.value = False
    spi_bus.write(bytes(bytes_out))
    cs.value = True


def read_device_id():
    """Return the 4-byte device ID of the FRAM."""
    cs.value = False
    spi.write(bytes([_RDID]))
    result = bytearray(4)
    spi.readinto(result)
    cs.value = True
    return result


def read_status():
    """Return the FRAM status register byte."""
    cs.value = False
    spi.write(bytes([_RDSR]))
    result = bytearray(1)
    spi.readinto(result)
    cs.value = True
    return result[0]


def write_enable():
    """Set the FRAM write-enable latch (required before any write)."""
    _cmd(spi, cs, _WREN)


def write_fram(address, data):
    """Write *data* bytes starting at *address* (24-bit address)."""
    write_enable()
    cs.value = False
    # opcode + 3-byte address + data
    header = bytes(
        [
            _WRITE,
            (address >> 16) & 0xFF,
            (address >> 8) & 0xFF,
            address & 0xFF,
        ]
    )
    spi.write(header)
    spi.write(bytes(data))
    cs.value = True


def read_fram(address, length):
    """Read *length* bytes from *address* (24-bit address)."""
    cs.value = False
    header = bytes(
        [
            _READ,
            (address >> 16) & 0xFF,
            (address >> 8) & 0xFF,
            address & 0xFF,
        ]
    )
    spi.write(header)
    result = bytearray(length)
    spi.readinto(result)
    cs.value = True
    return result


# ── Demo ─────────────────────────────────────────────────────────────────────
device_id = read_device_id()
print(f"FRAM Device ID: {[hex(b) for b in device_id]}")
# Expected for MB85RS4MT: [0x04, 0x7F, 0x27, 0x03]

status = read_status()
print(f"FRAM Status Register: 0x{status:02X}")

test_address = 0x000000
test_data = b"Hello, FRAM!"

print(f"Writing {test_data!r} to address 0x{test_address:06X}")
write_fram(test_address, test_data)

readback = read_fram(test_address, len(test_data))
print(f"Read back: {bytes(readback)!r}")

if readback == test_data:
    print("SUCCESS: data matches!")
else:
    print("ERROR: data mismatch!")
