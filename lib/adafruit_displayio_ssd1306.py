# SPDX-FileCopyrightText: 2019 Scott Shawcroft for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`adafruit_displayio_ssd1306`
================================================================================

DisplayIO driver for SSD1306 monochrome displays


* Author(s): Scott Shawcroft
"""
try:
    from typing import Union
    from busdisplay import BusDisplay
    from fourwire import FourWire
    from i2cdisplaybus import I2CDisplayBus
except ImportError:
    from displayio import FourWire
    from displayio import I2CDisplay as I2CDisplayBus
    from displayio import Display as BusDisplay

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_DisplayIO_SSD1306.git"

# Sequence from page 19 here: https://cdn-shop.adafruit.com/datasheets/UG-2864HSWEG01+user+guide.pdf
_INIT_SEQUENCE = (
    b"\xAE\x00"  # DISPLAY_OFF
    b"\x20\x01\x00"  # Set memory addressing to horizontal mode.
    b"\x81\x01\xcf"  # set contrast control
    b"\xA1\x00"  # Column 127 is segment 0
    b"\xA6\x00"  # Normal display
    b"\xc8\x00"  # Normal display
    b"\xA8\x01\x3f"  # Mux ratio is 1/64
    b"\xd5\x01\x80"  # Set divide ratio
    b"\xd9\x01\xf1"  # Set pre-charge period
    b"\xda\x01\x12"  # Set com configuration
    b"\xdb\x01\x40"  # Set vcom configuration
    b"\x8d\x01\x14"  # Enable charge pump
    b"\xAF\x00"  # DISPLAY_ON
)


class SSD1306(BusDisplay):
    """
    SSD1306 driver

    :param int width: The width of the display
    :param int height: The height of the display
    :param int rotation: The rotation of the display in degrees. Default is 0. Must be one of
        (0, 90, 180, 270)
    """

    def __init__(self, bus: Union[FourWire, I2CDisplayBus], **kwargs) -> None:
        # Patch the init sequence for 32 pixel high displays.
        init_sequence = bytearray(_INIT_SEQUENCE)
        height = kwargs["height"]
        width = kwargs["width"]
        if "rotation" in kwargs and kwargs["rotation"] % 180 != 0:
            height = kwargs["width"]
            width = kwargs["height"]
        init_sequence[16] = height - 1  # patch mux ratio
        if height == 32 and width == 64:  # Make sure this only apply to that resolution
            init_sequence[16] = 64 - 1  # FORCED for 64x32 because it fail with formula
        if height in (32, 16) and width != 64:
            init_sequence[25] = 0x02  # patch com configuration
        col_offset = (
            0 if width == 128 else (128 - width) // 2
        )  # https://github.com/micropython/micropython/pull/7411
        row_offset = col_offset

        # for 64x48
        if kwargs["height"] == 48 and kwargs["width"] == 64:
            col_offset = (128 - kwargs["width"]) // 2
            row_offset = 0

            if "rotation" in kwargs and kwargs["rotation"] % 180 != 0:
                init_sequence[16] = kwargs["height"] - 1
                kwargs["height"] = height
                kwargs["width"] = width

        # for 72x40
        if kwargs["height"] == 40 and kwargs["width"] == 72:
            col_offset = (128 - kwargs["width"]) // 2
            row_offset = 0

            # add Internal IREF Setting for the 0.42 OLED as per
            # https://github.com/olikraus/u8g2/issues/1047 and
            # SSD1306B rev 1.1 datasheet at
            # https://www.buydisplay.com/download/ic/SSD1306.pdf
            seq_length = len(init_sequence) - 2
            init_sequence[seq_length:seq_length] = bytearray(b"\xad\x01\x30")

            if "rotation" in kwargs and kwargs["rotation"] % 180 != 0:
                init_sequence[16] = kwargs["height"] - 1
                kwargs["height"] = height
                kwargs["width"] = width

        super().__init__(
            bus,
            init_sequence,
            **kwargs,
            colstart=col_offset,
            rowstart=row_offset,
            color_depth=1,
            grayscale=True,
            pixels_in_byte_share_row=False,
            set_column_command=0x21,
            set_row_command=0x22,
            data_as_commands=True,
            brightness_command=0x81,
            single_byte_bounds=True,
        )
        self._is_awake = True  # Display starts in active state (_INIT_SEQUENCE)

    @property
    def is_awake(self) -> bool:
        """
        The power state of the display. (read-only)

        `True` if the display is active, `False` if in sleep mode.

        :type: bool
        """
        return self._is_awake

    def sleep(self) -> None:
        """
        Put display into sleep mode.

        Display uses < 10uA in sleep mode. Display remembers display data and operation mode
        active prior to sleeping. MP can access (update) the built-in display RAM.
        """
        if self._is_awake:
            self.bus.send(0xAE, b"")  # 0xAE = display off, sleep mode
            self._is_awake = False

    def wake(self) -> None:
        """
        Wake display from sleep mode
        """
        if not self._is_awake:
            self.bus.send(0xAF, b"")  # 0xAF = display on
            self._is_awake = True
