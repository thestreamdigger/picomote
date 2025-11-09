# Changelog

## [1.0.1] - 2025-11-03

- Removed unused DisplayCache class and module (-149 lines)
- Removed redundant code: duplicate logger, unused USB variables, dead code paths
- Fixed impossible condition in visual_feedback()
- Improved IRManager cache encapsulation

## [1.0.0] - 2025-06-15

- First stable production release.
- IR to USB HID mapping (media and keyboard modes).
- Optional OLED display and rotary encoder.
- Headless mode support (works without display/encoder).
- Persistent mapping storage.
- Robust error handling and logging.
