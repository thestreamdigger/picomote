"""Configuration module for Picomote IR

Provides:
1. Version information and feature detection
2. Key mapping definitions for media and keyboard controls
3. Logging system with colored console output
4. Settings management with defaults and JSON file loading
"""

__version__ = "1.1.0"

import json
import board
import time
import supervisor
import os

try:
    from adafruit_hid.keycode import Keycode
    HAS_KEYCODE = True
except ImportError:
    HAS_KEYCODE = False
    class Keycode:
        pass

try:
    from adafruit_hid.consumer_control_code import ConsumerControlCode
    HAS_CONSUMER = True
except ImportError:
    HAS_CONSUMER = False
    class ConsumerControlCode:
        pass

try:
    import adafruit_irremote
    HAS_IRREMOTE = True
except ImportError:
    HAS_IRREMOTE = False

MEDIA_KEYS = []
if HAS_CONSUMER:
    MEDIA_KEYS = [
        ("Play/Pause", ConsumerControlCode.PLAY_PAUSE, True),
        ("Stop", ConsumerControlCode.STOP, True),
        ("Next", ConsumerControlCode.SCAN_NEXT_TRACK, True),
        ("Prev", ConsumerControlCode.SCAN_PREVIOUS_TRACK, True),
        ("Vol+", ConsumerControlCode.VOLUME_INCREMENT, True),
        ("Vol-", ConsumerControlCode.VOLUME_DECREMENT, True),
        ("Mute", ConsumerControlCode.MUTE, True),
        ("Record", ConsumerControlCode.RECORD, True),
        ("FFwd", ConsumerControlCode.FAST_FORWARD, True),
        ("Rewind", ConsumerControlCode.REWIND, True),
        ("Eject", ConsumerControlCode.EJECT, True),
        ("Bright+", ConsumerControlCode.BRIGHTNESS_INCREMENT, True),
        ("Bright-", ConsumerControlCode.BRIGHTNESS_DECREMENT, True),
    ]

KEYBOARD_KEYS = []
if HAS_KEYCODE:
    KEYBOARD_KEYS = [
        # Letters
        ("a", Keycode.A), ("b", Keycode.B), ("c", Keycode.C), ("d", Keycode.D), ("e", Keycode.E),
        ("f", Keycode.F), ("g", Keycode.G), ("h", Keycode.H), ("i", Keycode.I), ("j", Keycode.J),
        ("k", Keycode.K), ("l", Keycode.L), ("m", Keycode.M), ("n", Keycode.N), ("o", Keycode.O),
        ("p", Keycode.P), ("q", Keycode.Q), ("r", Keycode.R), ("s", Keycode.S), ("t", Keycode.T),
        ("u", Keycode.U), ("v", Keycode.V), ("w", Keycode.W), ("x", Keycode.X), ("y", Keycode.Y),
        ("z", Keycode.Z),
        # Numbers
        ("0", Keycode.ZERO), ("1", Keycode.ONE), ("2", Keycode.TWO), ("3", Keycode.THREE),
        ("4", Keycode.FOUR), ("5", Keycode.FIVE), ("6", Keycode.SIX), ("7", Keycode.SEVEN),
        ("8", Keycode.EIGHT), ("9", Keycode.NINE),
        # Common Symbols
        (" ", Keycode.SPACE), ("-", Keycode.MINUS), ("=", Keycode.EQUALS),
        ("[", Keycode.LEFT_BRACKET), ("]", Keycode.RIGHT_BRACKET), ("\\", Keycode.BACKSLASH),
        (";", Keycode.SEMICOLON), ("'", Keycode.QUOTE), (",", Keycode.COMMA),
        (".", Keycode.PERIOD), ("/", Keycode.FORWARD_SLASH), ("`", Keycode.GRAVE_ACCENT),
        # Shifted Symbols
        ("~", (Keycode.SHIFT, Keycode.GRAVE_ACCENT)), ("!", (Keycode.SHIFT, Keycode.ONE)),
        ("@", (Keycode.SHIFT, Keycode.TWO)), ("#", (Keycode.SHIFT, Keycode.THREE)),
        ("$", (Keycode.SHIFT, Keycode.FOUR)), ("%", (Keycode.SHIFT, Keycode.FIVE)),
        ("^", (Keycode.SHIFT, Keycode.SIX)), ("&", (Keycode.SHIFT, Keycode.SEVEN)),
        ("*", (Keycode.SHIFT, Keycode.EIGHT)), ("(", (Keycode.SHIFT, Keycode.NINE)),
        (")", (Keycode.SHIFT, Keycode.ZERO)), ("_", (Keycode.SHIFT, Keycode.MINUS)),
        ("+", (Keycode.SHIFT, Keycode.EQUALS)),
        ("{", (Keycode.SHIFT, Keycode.LEFT_BRACKET)),
        ("}", (Keycode.SHIFT, Keycode.RIGHT_BRACKET)),
        ("|", (Keycode.SHIFT, Keycode.BACKSLASH)),
        (":", (Keycode.SHIFT, Keycode.SEMICOLON)),
        ("\"", (Keycode.SHIFT, Keycode.QUOTE)),
        ("<", (Keycode.SHIFT, Keycode.COMMA)),
        (">", (Keycode.SHIFT, Keycode.PERIOD)),
        ("?", (Keycode.SHIFT, Keycode.FORWARD_SLASH)),
        # Control Keys
        ("Enter", Keycode.ENTER), ("Esc", Keycode.ESCAPE), ("Bksp", Keycode.BACKSPACE),
        ("Tab", Keycode.TAB), ("CapsLk", Keycode.CAPS_LOCK),
        # Modifiers
        ("Ctrl", Keycode.LEFT_CONTROL), ("Shift", Keycode.LEFT_SHIFT),
        ("Alt", Keycode.LEFT_ALT), ("GUI", Keycode.LEFT_GUI),
        # Function Keys
        ("F1", Keycode.F1), ("F2", Keycode.F2), ("F3", Keycode.F3), ("F4", Keycode.F4),
        ("F5", Keycode.F5), ("F6", Keycode.F6), ("F7", Keycode.F7), ("F8", Keycode.F8),
        ("F9", Keycode.F9), ("F10", Keycode.F10), ("F11", Keycode.F11), ("F12", Keycode.F12),
        # Navigation Keys
        ("Ins", Keycode.INSERT), ("Del", Keycode.DELETE), ("Home", Keycode.HOME),
        ("End", Keycode.END), ("PgUp", Keycode.PAGE_UP), ("PgDn", Keycode.PAGE_DOWN),
        ("Up", Keycode.UP_ARROW), ("Down", Keycode.DOWN_ARROW),
        ("Left", Keycode.LEFT_ARROW), ("Right", Keycode.RIGHT_ARROW),
        # Keypad Keys
        ("NumLk", Keycode.KEYPAD_NUMLOCK),
        ("KP /", Keycode.KEYPAD_FORWARD_SLASH), ("KP *", Keycode.KEYPAD_ASTERISK),
        ("KP -", Keycode.KEYPAD_MINUS), ("KP +", Keycode.KEYPAD_PLUS),
        ("KP Ent", Keycode.KEYPAD_ENTER),
        ("KP 1", Keycode.KEYPAD_ONE), ("KP 2", Keycode.KEYPAD_TWO), ("KP 3", Keycode.KEYPAD_THREE),
        ("KP 4", Keycode.KEYPAD_FOUR), ("KP 5", Keycode.KEYPAD_FIVE), ("KP 6", Keycode.KEYPAD_SIX),
        ("KP 7", Keycode.KEYPAD_SEVEN), ("KP 8", Keycode.KEYPAD_EIGHT), ("KP 9", Keycode.KEYPAD_NINE),
        ("KP 0", Keycode.KEYPAD_ZERO), ("KP .", Keycode.KEYPAD_PERIOD),
    ]

FALLBACK_KEY_SEQUENCE = [
    ("Play/Pause", None), ("Stop", None), ("Next", None), ("Prev", None), 
    ("Vol+", None), ("Vol-", None), ("Mute", None),
    ("a", None), ("b", None), ("c", None),
    ("Enter", None), ("Space", None), ("Esc", None),
    ("Up", None), ("Down", None), ("Left", None), ("Right", None),
]

ALL_KEYS_FOR_MAPPING = MEDIA_KEYS + KEYBOARD_KEYS
if not HAS_KEYCODE and not HAS_CONSUMER:
    ALL_KEYS_FOR_MAPPING = FALLBACK_KEY_SEQUENCE

COMMAND_NAME_TO_KEYCODE = {}
for item in ALL_KEYS_FOR_MAPPING:
    if len(item) == 2:
        name, code = item[0], item[1]
        COMMAND_NAME_TO_KEYCODE[name.lower()] = code 
    elif len(item) == 3:
        name, code, is_media_key = item
        COMMAND_NAME_TO_KEYCODE[name.lower()] = (name, code, is_media_key)

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    WAIT = '\033[96m'
    ENDC = '\033[0m'

class Logger:
    def __init__(self, enabled=True, level="INFO"):
        self.enabled = enabled
        self.levels = {
            "DEBUG": 0,
            "INFO": 1,
            "WAIT": 2,
            "OK": 3,
            "WARNING": 4,
            "ERROR": 5,
        }
        self.level = level

    def _log(self, level, module, message, **kwargs):
        if not self.enabled or self.levels[level] < self.levels[self.level]:
            return

        color_map = {
            "DEBUG": Colors.ENDC,
            "INFO": Colors.OKBLUE,
            "WAIT": Colors.WAIT,
            "OK": Colors.OKGREEN,
            "WARNING": Colors.WARNING,
            "ERROR": Colors.ERROR,
        }
        color = color_map.get(level, Colors.ENDC)

        message_str = f"{color}[{level}] {module}: {message}{Colors.ENDC}"
        if kwargs:
            extras = ', '.join(f"{k}={v}" for k, v in kwargs.items())
            message_str += f" ({extras})"
        print(message_str)

    def debug(self, module, message, **kwargs):
        self._log("DEBUG", module, message, **kwargs)

    def info(self, module, message, **kwargs):
        self._log("INFO", module, message, **kwargs)

    def wait(self, module, message, **kwargs):
        self._log("WAIT", module, message, **kwargs)

    def ok(self, module, message, **kwargs):
        self._log("OK", module, message, **kwargs)

    def warning(self, module, message, **kwargs):
        self._log("WARNING", module, message, **kwargs)

    def error(self, module, message, error=None, **kwargs):
        if error and "error" not in kwargs:
            kwargs["error"] = str(error)
        self._log("ERROR", module, message, **kwargs)

class Settings:
    def __init__(self):
        self.settings = {}
        self.defaults = {
            "display": {
                "pins": {
                    "ir_receiver": "GP15",
                    "rotary_encoder": {"clk": "GP12", "dt": "GP13", "sw": "GP14"},
                    "i2c": {"sda": "GP20", "scl": "GP21"}
                },
                "preferences": {
                    "display_enabled": True,
                    "display_address": 60,
                    "pin_pull_up": True,
                    "display_rotation": 180
                }
            },
            "status_leds": {
                "main_led": {"pin": "GP25", "is_inverted": False}
            },
            "hid_mapper": {
                "timing": {
                    "feedback_duration": 0.3,
                    "led_blink_count": 2,
                    "debounce_time": 0.05,
                    "long_press_delay": 1.5,
                    "ir_timeout": 20000,
                    "save_timeout": 30,
                    "reboot_delay": 5,
                    "temp_message_duration": 2.0
                },
                "logging": {
                    "default_log_level": "INFO"
                }
            },
            "ir_receiver": {
                "maxlen": 250,
                "idle_state": True
            }
        }
        self._load_settings()

    def _load_settings(self):
        try:
            if "settings.json" in os.listdir("/"):
                with open("/settings.json", "r") as f:
                    loaded_settings = json.load(f)
                self._merge_dicts(self.defaults, loaded_settings)
                self.settings = self.defaults
            else:
                self.settings = self.defaults
        except:
            self.settings = self.defaults

    def _merge_dicts(self, base, updates):
        for key, value in updates.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._merge_dicts(base[key], value)
            else:
                base[key] = value

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def get_section(self, section_key, default=None):
        return self.settings.get(section_key, default if default is not None else {})

    def get_value(self, section_key, value_key, default=None):
        section = self.get_section(section_key)
        return section.get(value_key, default)

settings = Settings()

log_level = settings.get_value("hid_mapper", "logging", {}).get("default_log_level", "INFO").upper()
logger = Logger(enabled=True, level=log_level)

logger.info("Config", "Configuration loaded.")
