# Picomote IR v1.0.1

[![CircuitPython 7.x+](https://img.shields.io/badge/CircuitPython-7.x%2B-purple.svg)](https://circuitpython.org)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Version](https://img.shields.io/badge/version-v1.0.1-brightgreen.svg)](CHANGELOG.md)
[![RP2040](https://img.shields.io/badge/Raspberry%20Pico-RP2040-c51a4a.svg)](https://www.raspberrypi.com/products/rp2040/)

**IR remote to USB HID keyboard mapper for Raspberry Pi RP2040/RP2350**

Maps IR remote control signals to USB keyboard commands using CircuitPython. Features a simple OLED interface for configuring and recording IR signals directly on the device. Useful for controlling media streamers, audio software, video players, and other computer applications with any standard IR remote.

## Features

- **Universal IR support** - Works with most IR remotes (NEC, Sony, Samsung, RC5/RC6)
- **Two operation modes** - Media keys and full keyboard mapping
- **OLED display** with rotary encoder navigation
- **Learning mode** - Map any IR button to any keyboard key
- **Persistent storage** - Mappings saved between reboots
- **Visual feedback** - Status LED and display notifications
- **Modular hardware support** - Can operate with or without display and rotary encoder

## Hardware Requirements

| Component | Pin | Description |
|-----------|-----|-------------|
| IR Receiver | GP28 | VS1838B or equivalent 38kHz receiver (required) |
| OLED Display | GP20/GP21 | I2C SSD1306 128x64 pixels (optional) |
| Rotary Encoder | GP12/GP13/GP14 | With integrated push button (optional) |
| Status LED | GP25 | Visual feedback (optional) |

## Installation

1. **Install CircuitPython 7.x+** on your RP2040/RP2350
2. **Copy libraries** to `/lib/` folder:
   ```
   adafruit_hid/
   adafruit_irremote.mpy
   adafruit_display_text/
   adafruit_displayio_ssd1306.mpy
   ```
3. **Copy project files** to root directory:
   ```
   boot.py
   code.py
   config.py
   device.py
   ir_manager.py
   settings.json
   ```

## Usage

### Navigation (with display and encoder)
- **Rotate encoder** - Browse available keys
- **Short press** - Switch between Media and Keyboard modes
- **Long press** - Enter learning mode for current key

### Learning New Mappings
1. Navigate to the key you want to map
2. Long press the encoder to enter learning mode
3. Point your IR remote at the device
4. Press the remote button you want to map
5. Mapping is automatically saved

### Display Modes

**Media Mode** - Common media keys:
```
Media: 3/13
< Prev  PLAY  Next >
```

**Keyboard Mode** - Full keyboard:
```
Keyboard: 15/104
< n  O  p >
```

**Learning Mode**:
```
LEARNING: play/pause
Point remote
Time: 18s
```

## Headless Mode Operation

Picomote IR can operate without the display and rotary encoder in "headless mode":

- **IR functionality** remains fully operational
- **Existing mappings** continue to work normally
- **LED feedback** provides basic status information
- **Serial console** shows detailed status messages
- **No learning mode** available without the rotary encoder

To use headless mode:
1. Create mappings on a device with display/encoder or manually add mapping files to `/mappings/`
2. Deploy the device without display/encoder components
3. IR signals will be processed according to existing mappings

## Configuration

Edit `settings.json` to customize pin assignments and behavior:

```json
{
    "display": {
        "pins": {
            "ir_receiver": "GP28",
            "rotary_encoder": {
                "clk": "GP13", "dt": "GP12", "sw": "GP14"
            },
            "i2c": {"sda": "GP20", "scl": "GP21"}
        },
        "preferences": {
            "display_enabled": true,
            "idle_timeout": 5,
            "deep_idle_timeout": 15
        }
    },
    "status_leds": {
        "main_led": {"pin": "GP25", "is_inverted": false}
    }
}
```

## File Structure

```
/
├── boot.py             # Boot configuration and filesystem setup
├── code.py             # Main application entry point
├── config.py           # Configuration constants and settings
├── device.py           # Hardware device management
├── ir_manager.py       # IR signal processing and mapping
├── settings.json       # User configuration file
├── picomote.png        # Project logo
├── CHANGELOG.md        # Version history and changes
├── LICENSE             # GNU GPL v3 license
├── README.md           # Project documentation
├── lib/                # External libraries
└── mappings/           # Directory for IR key mappings
```

## Troubleshooting

**IR not detected:**
- Check IR receiver wiring (default GP28)
- Ensure remote is working
- Try closer distance (1-3 meters)

**Display issues:**
- Verify I2C connections (SDA/SCL)
- Check display address (default 0x3C)
- If intentionally using headless mode, ignore display-related messages

**USB not recognized:**
- Restart device
- Check USB cable and connection

**Serial Console Messages:**
- Connect to USB serial console to view detailed status messages
- Device will report which components are available/missing

## License

GNU General Public License v3.0 - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- CircuitPython and Adafruit teams for excellent libraries
- RP2040/RP2350 community for support and resources 