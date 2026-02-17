# Picomote IR v1.1.0

[![Version](https://img.shields.io/badge/version-1.1.0-blue?style=flat-square)](https://github.com/thestreamdigger/picomote)
[![License](https://img.shields.io/badge/license-GPL%20v3-green?style=flat-square)](LICENSE)
[![CircuitPython](https://img.shields.io/badge/CircuitPython-9.x-blue?style=flat-square)](https://circuitpython.org)
[![Status](https://img.shields.io/badge/status-stable-brightgreen?style=flat-square)]()
[![Raspberry Pi Pico](https://img.shields.io/badge/platform-Raspberry%20Pi%20Pico-C51A4A?style=flat-square)](https://www.raspberrypi.com/products/rp2040/)

**IR remote to USB HID keyboard mapper for Raspberry Pi RP2040/RP2350**

Maps IR remote control signals to USB keyboard commands using CircuitPython. Features a simple OLED interface for configuring and recording IR signals directly on the device. Useful for controlling media streamers, audio software, video players, and other computer applications with any standard IR remote.

## Features

- **Universal IR support** - Works with most IR remotes (NEC, Sony, Samsung, RC5/RC6)
- **Two operation modes** - Media keys and full keyboard mapping
- **OLED display** with rotary encoder navigation
- **Learning mode** - Map any IR button to any keyboard key
- **Persistent storage** - Mappings saved between reboots
- **Visual feedback** - Status LED and display notifications
- **Idle modes** - Progressive power-saving (idle → deep idle) with configurable timeouts
- **LRU mapping cache** - Fast IR code lookup with intelligent caching
- **USB monitoring** - Automatic detection and status display
- **Modular hardware support** - Can operate with or without display and rotary encoder

## Hardware Requirements

| Component | Pin | Description |
|-----------|-----|-------------|
| IR Receiver | GP28 | VS1838B or equivalent 38kHz receiver (required) |
| OLED Display | GP20/GP21 | I2C SSD1306 128x64 pixels (optional) |
| Rotary Encoder | GP12/GP13/GP14 | With integrated push button (optional) |
| Status LED | GP25 | Visual feedback (optional) |

## Installation

1. **Install CircuitPython 9.x** on your RP2040/RP2350
2. **Copy libraries** to `/lib/` folder:
   ```
   adafruit_hid/
   adafruit_irremote.mpy
   adafruit_display_text/
   adafruit_displayio_ssd1306.mpy
   adafruit_bus_device/
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

### Idle Modes

Device progressively reduces display activity to save power:

1. **Normal** - Full display with key navigation
2. **Idle** - Shows USB status, mapping count, and countdown to deep idle
3. **Deep idle** - Minimal animation (`++++` / `****`), lower CPU usage

Any encoder interaction wakes the display. IR signals are processed in all modes.

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
                "clk": "GP13",
                "dt": "GP12",
                "sw": "GP14"
            },
            "i2c": {
                "sda": "GP20",
                "scl": "GP21"
            }
        },
        "preferences": {
            "display_enabled": true,
            "display_address": 60,
            "pin_pull_up": true,
            "display_rotation": 0,
            "idle_mode_enabled": true,
            "idle_timeout": 10,
            "idle_display_enabled": true,
            "idle_display_inverted": true,
            "deep_idle_enabled": true,
            "deep_idle_timeout": 20,
            "deep_idle_display_enabled": true,
            "start_in_deep_idle": true
        }
    },
    "status_leds": {
        "main_led": {
            "pin": "GP25",
            "is_inverted": false
        }
    },
    "hid_mapper": {
        "timing": {
            "feedback_duration": 0.05,
            "led_blink_count": 1,
            "debounce_time": 0.05,
            "long_press_delay": 1.5,
            "ir_timeout": 20000,
            "save_timeout": 30,
            "reboot_delay": 5,
            "temp_message_duration": 1.0
        },
        "logging": {
            "default_log_level": "INFO"
        }
    },
    "ir_receiver": {
        "maxlen": 200,
        "idle_state": true
    }
}
```

### Configuration Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `display_rotation` | `0` | Display rotation in degrees (0, 90, 180, 270) |
| `idle_timeout` | `10` | Seconds before entering idle mode |
| `deep_idle_timeout` | `20` | Seconds in idle before entering deep idle |
| `start_in_deep_idle` | `true` | Start device directly in deep idle mode |
| `idle_display_inverted` | `true` | Invert display colors in idle mode |
| `ir_timeout` | `20000` | Learning mode timeout in milliseconds |
| `debounce_time` | `0.05` | Button debounce delay in seconds |

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
