# Picomote IR Dependencies

This document lists all the required libraries for the Picomote IR project and how to install them.

## Required Libraries

### CircuitPython Built-in Libraries
These libraries are already included in CircuitPython and don't need to be installed:

- `board` - GPIO pin access
- `digitalio` - Digital pin control  
- `busio` - I2C/SPI communication
- `displayio` - Display system
- `terminalio` - Text fonts
- `pulseio` - PWM/PulseIn signals
- `rotaryio` - Rotary encoder
- `usb_hid` - USB HID devices
- `time`, `gc`, `os`, `supervisor`, `json` - Standard libraries

### Adafruit Libraries (External)
These libraries must be installed in the `lib/` folder:

- `adafruit_hid` - Keyboard and media control functionality
- `adafruit_irremote` - IR receiver/transmitter
- `adafruit_displayio_ssd1306` - SSD1306 OLED display support
- `adafruit_display_text` - Text rendering on display
- `adafruit_bus_device` - I2C/SPI communication dependency
- `adafruit_bitmap_font` - Bitmap fonts for displays

## How to Install Libraries

### Method 1: Adafruit Bundle (Recommended)
1. Download the [CircuitPython Library Bundle](https://circuitpython.org/libraries)
2. Extract the ZIP file
3. Copy the required libraries from the bundle's `lib/` folder to your device's `lib/` folder

### Method 2: Individual Installation
1. Download each library individually from the [Adafruit repository](https://github.com/adafruit/Adafruit_CircuitPython_Bundle)
2. Copy to your device's `lib/` folder

### Method 3: Using circup (if available)
```bash
circup install adafruit_hid adafruit_irremote adafruit_displayio_ssd1306 adafruit_display_text
```

## lib/ Folder Structure

```
lib/
├── adafruit_hid/
├── adafruit_display_text/
├── adafruit_bus_device/
├── adafruit_bitmap_font/
├── adafruit_irremote.py
├── adafruit_displayio_ssd1306.py
└── neopixel.py
```

## Optional Dependencies

The project was developed with error handling for libraries that may not be present:

- If `adafruit_hid` is not available, keyboard functionality will be disabled
- If `adafruit_irremote` is not available, IR receiver will be disabled
- If display libraries are not available, display will be disabled

## Dependency Verification

The project automatically checks library availability and adapts accordingly. You can check the status in the console:

```python
print(f"HID available: {HAS_HID}")
print(f"IR available: {HAS_IRREMOTE}")
print(f"Display available: {HAS_DISPLAY}")
```

## Important Notes

- All libraries must be compatible with your CircuitPython version
- The `lib/` folder is included in `.gitignore` to avoid pushing libraries to the repository
- Make sure your device has enough storage space for all libraries (some can be large) 