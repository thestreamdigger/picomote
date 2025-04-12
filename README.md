# Picomote

[![CircuitPython 7.x+](https://img.shields.io/badge/CircuitPython-7.x%2B-purple.svg)](https://circuitpython.org)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Version](https://img.shields.io/badge/version-v0.2.1-lightgrey.svg)](CHANGELOG.md)

A CircuitPython device for the RP2040 that allows mapping IR codes to HID keyboard keys.

## Overview

This project, **Picomote**, transforms an RP2040 microcontroller (like the WeAct RP2040 or Raspberry Pi Pico) into a device that receives infrared (IR) remote control signals and translates them into USB HID keyboard keystrokes. It's ideal for controlling presentations, media players, or any application on a computer using existing IR remote controls.

## Features

- OLED display interface for selection and status
- IR signal encoding and decoding
- Learning mode to easily add new mappings
- Sends USB HID keys to control computers
- Persistence of mappings in files
- Feedback LED for operations
- Rotary encoder navigation
- Key grouping system with dedicated Media and Keyboard groups
- Quick toggle between key groups with encoder button

## Required Hardware

- RP2040 Microcontroller (Raspberry Pi Pico or WeAct RP2040)
- IR Receiver (VS1838B or equivalent)
- I2C SSD1306 OLED Display (128x64)
- Rotary encoder with button
- LED for visual feedback
- Pull-up resistors as needed

## Default Pinout

| Component      | RP2040 Pin | Description             |
|----------------|------------|-------------------------|
| IR Receiver    | GP15       | IR signal input         |
| OLED SDA       | GP2        | I2C data for display    |
| OLED SCL       | GP3        | I2C clock for display   |
| Encoder CLK    | GP12       | Encoder clock           |
| Encoder DT     | GP13       | Encoder data            |
| Encoder SW     | GP14       | Encoder button          |
| Status LED     | GP25       | Onboard or external LED |

## Installation

1. Install CircuitPython 7.x or higher on your RP2040 device
2. Copy the following files to the device:
   - `boot.py`
   - `code.py`
   - `config.py`
   - `device.py`
   - `settings.json`
3. Copy the required libraries to the `/lib` folder:
   - adafruit_hid/
   - adafruit_irremote.mpy
   - adafruit_display_text/
   - adafruit_displayio_ssd1306.mpy

## Usage

1. Connect the device to a computer via USB
2. The OLED display will show the key selection interface
3. Use the rotary encoder to navigate between available keys
4. Short press the encoder button to toggle between Media and Keyboard key groups
5. To map a new IR code:
   - Select the desired key with the encoder
   - Press and hold the encoder button until learning mode is entered
   - Press the button on the remote control you want to map
   - The device will save the mapping automatically
6. To use the mappings:
   - Point the remote control at the IR receiver
   - Press the mapped button on the remote control
   - The device will send the corresponding HID key to the computer

## Available Media Keys

The Media key group includes:
- Play/Pause, Stop, Next, Previous track
- Volume control (Vol+, Vol-, Mute)
- Media transport (Record, Fast Forward, Rewind, Eject)
- Screen brightness control (Bright+, Bright-)

The Keyboard group includes letters, numbers, symbols, function keys and more.

## Mappings

Mappings are saved in the `/mappings/` folder as `.ir` files containing the hexadecimal codes of the IR signals. The filenames correspond to the mapped HID keys.

## Customization

Adjust pins and settings by editing the `settings.json` file:

- `pins`: Pin configuration for all components
- `preferences`: Preferences like display rotation, display enable, and I2C address.
- `timing`: Time adjustments for debounce, feedback, timeouts (`temp_message_duration` controls default temporary message display time).
- `logging`: Set the default logging level (`default_log_level` e.g., "INFO", "DEBUG").

## Troubleshooting

- **LED blinking rapidly multiple times**: Indicates an error
- **Display showing "NO KEYS/LIB ERR"**: Missing or corrupted libraries
- **IR not detected**: Check the IR receiver connection and pin configuration

## License

This project is free software; you can redistribute it and/or modify it under the terms of the license of your choice.

## Acknowledgements

- CircuitPython and Adafruit team for the excellent libraries
- The RP2040 community for resources and support 