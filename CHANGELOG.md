# Changelog

## [1.1.0] - 2026-02-17

- Updated version and documentation to reflect current feature set
- Fixed README configuration example to match actual settings.json
- Added idle modes documentation (idle, deep idle)
- Added configuration reference table
- Updated CircuitPython badge to 9.x

## [1.0.5] - 2025-11-09

- Added progressive idle modes (idle → deep idle) with configurable timeouts
- Added inverted display option for idle mode
- Added deep idle animation with minimal CPU usage
- Added IR command display in deep idle mode
- Added start_in_deep_idle configuration option
- Added USB connection monitoring and status display
- Added LRU mapping cache for fast IR code lookups
- Added cache preloading for frequently used mappings

## [1.0.2] - 2025-06-24

- Improved IR signal processing reliability
- Refined display update timing and refresh logic

## [1.0.1] - 2025-11-03

- Removed unused DisplayCache class and module (-149 lines)
- Removed redundant code: duplicate logger, unused USB variables, dead code paths
- Fixed impossible condition in visual_feedback()
- Improved IRManager cache encapsulation

## [1.0.0] - 2025-06-15

- First stable production release
- IR to USB HID mapping (media and keyboard modes)
- Optional OLED display and rotary encoder
- Headless mode support (works without display/encoder)
- Persistent mapping storage
- Robust error handling and logging
