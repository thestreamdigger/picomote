# Changelog

All notable changes to this project will be documented in this file.

## [0.2.1] - 2024-07-23
### Improvements
- Improved display initialization for better visual consistency
- Removed splash screen for faster startup
- Updated display margins for better readability
- Fixed pixel position consistency between initial rendering and updates
- Added version information to codebase

## [0.2.0] - 2024-07-23
### Initial Release of Picomote

#### Core Features
- IR signal reception and decoding for remote control integration
- Key group system with "Media" and "Keyboard" groups for easier navigation
- Quick toggle between key groups with a single encoder click
- Visual selection interface with highlighted currently selected key
- Learning mode for mapping IR signals to specific keys
- Persistent mapping storage in filesystem
- Uppercase letter display while using lowercase for HID commands

#### Media Key Support
- Basic media controls: Play/Pause, Stop, Next/Previous tracks
- Volume management: Volume Up/Down, Mute
- Advanced media controls: Record, Fast Forward, Rewind, Eject
- Display brightness control: Brightness Up/Down

#### Keyboard Support
- Full keyboard layout including letters, numbers, and symbols
- Function keys (F1-F12)
- Navigation keys (arrows, home, end, etc.)
- Modifiers (Shift, Ctrl, Alt, GUI)
- Special characters and symbols

#### Hardware Support
- OLED display with dynamic status information
- Rotary encoder for navigation and selection
- Status LED for visual feedback
- IR receiver for capturing remote control signals
- HID device implementation for keyboard and consumer control

#### Configuration
- Flexible settings via `settings.json`
- Adjustable display options and rotation
- Configurable temporary message timing
- Customizable input pins for different hardware setups 