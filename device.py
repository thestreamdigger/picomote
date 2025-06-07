"""Main device logic for Picomote IR"""

import time
import board
import digitalio
import pulseio
import rotaryio
import busio
import displayio
import terminalio
import gc
import os
import supervisor

from config import (
    settings, logger, __version__,
    MEDIA_KEYS, KEYBOARD_KEYS, ALL_KEYS_FOR_MAPPING, COMMAND_NAME_TO_KEYCODE,
    HAS_KEYCODE, HAS_CONSUMER, HAS_IRREMOTE
)

from ir_manager import IRManager
from display_cache import DisplayCache

try:
    import adafruit_irremote
    from adafruit_hid.keyboard import Keyboard
    from adafruit_hid.consumer_control import ConsumerControl
    import usb_hid
    HAS_HID = True
except ImportError:
    HAS_HID = False

try:
    from adafruit_display_text import label
    import adafruit_displayio_ssd1306
    HAS_DISPLAY = True
except ImportError:
    HAS_DISPLAY = False

class ButtonDebouncer:
    def __init__(self, pin, pull, short_press_callback=None, long_press_callback=None,
                 debounce_delay=0.05, long_press_delay=1.5):
        self.button = digitalio.DigitalInOut(pin)
        self.button.direction = digitalio.Direction.INPUT
        self.button.pull = pull
        self.last_state = self.button.value
        self.debounce_time = time.monotonic()
        self.debounce_delay = debounce_delay
        self.long_press_delay = long_press_delay
        self.short_press_callback = short_press_callback
        self.long_press_callback = long_press_callback
        self.pressed = False
        self.press_start_time = 0
        self.long_press_triggered = False

    def update(self):
        triggered = False
        current_time = time.monotonic()
        button_state = self.button.value

        if button_state != self.last_state and (current_time - self.debounce_time) >= self.debounce_delay:
            self.debounce_time = current_time
            if not button_state:
                self.pressed = True
                self.press_start_time = current_time
                self.long_press_triggered = False
            else:
                self.pressed = False
                if not self.long_press_triggered and self.short_press_callback:
                    press_duration = current_time - self.press_start_time
                    if press_duration >= self.debounce_delay:
                         self.short_press_callback()
                         triggered = True
            self.last_state = button_state

        if self.pressed and not self.long_press_triggered and self.long_press_callback:
            if (current_time - self.press_start_time) >= self.long_press_delay:
                self.long_press_callback()
                self.long_press_triggered = True
                triggered = True

        return triggered

class HIDMapperDevice:
    def __init__(self):
        self.led = None
        self.led_inverted = False
        self.encoder = None
        self.encoder_button = None
        self.display = None
        self.display_group = None
        self.pulsein = None
        self.decoder = None
        self.keyboard = None
        self.consumer_control = None
        
        self.ir_manager = None
        self.display_cache = DisplayCache(max_cache_size=5)
        
        self._display_needs_update = True
        self._display_count = 0
        self._display_dirty = False

        self.temp_display_status = None
        self.temp_display_info = None
        self.temp_display_expiry = 0.0
        self.learning_remaining_time = 0

        self.last_activity_time = time.monotonic()
        self.in_idle_mode = False
        self.in_deep_idle_mode = False
        self.idle_entry_time = 0
        
        self.key_groups = []
        if MEDIA_KEYS:
             self.key_groups.append(("Media", MEDIA_KEYS))
        if KEYBOARD_KEYS:
             self.key_groups.append(("Keyboard", KEYBOARD_KEYS))
        
        self.current_key_group_index = 0
        self.current_key_index = 0
        self.last_encoder_position = 0
        
        self.ir_mappings = {}
        self.in_learning_mode = False
        self.learning_key_name = None
        self.learning_start_time = 0

        try:
            self.usb_connected = supervisor.runtime.usb_connected
        except:
            self.usb_connected = False

        display_prefs = settings.get_section("display", {}).get("preferences", {})
        start_in_deep_idle = display_prefs.get("start_in_deep_idle", False)
        
        if start_in_deep_idle:
            self.in_deep_idle_mode = True
            self.in_idle_mode = True
            self.idle_entry_time = time.monotonic()
        
        self._init_led()
        self._init_display()
        self._init_rotary_encoder()
        self._init_ir_receiver()
        self._init_hid()
        self._load_mappings()
        self._ensure_mappings_directory()
        
        if start_in_deep_idle and self.display:
                self._update_deep_idle_display()
        elif self.display:
            self._set_temp_display(f"Picomote IR v{__version__}", 
                                 f"USB: {'Connected' if self.usb_connected else 'Not Connected'}", 3.0)
        
        self.last_usb_check = time.monotonic()
        self.usb_check_interval = 5.0

    def get_version(self):
        return __version__

    def check_usb_status(self):
        try:
            current_status = supervisor.runtime.usb_connected
            if current_status != self.usb_connected:
                self.usb_connected = current_status
                if not current_status:
                    self._set_temp_display("USB Not Connected", "Limited function", 2.0)
            return current_status
        except:
            return self.usb_connected

    def _init_led(self):
        led_config = settings.get_section("status_leds", {}).get("main_led", {})
        try:
            pin = getattr(board, led_config.get("pin", "GP25"))
            self.led = digitalio.DigitalInOut(pin)
            self.led.direction = digitalio.Direction.OUTPUT
            self.led_inverted = led_config.get("is_inverted", False)
            self.led.value = self.led_inverted
        except:
            self.led = None

    def _init_display(self):
        self.display_is_ready = False
        
        if not HAS_DISPLAY:
            return

        display_prefs = settings.get_section("display", {}).get("preferences", {})
        if not display_prefs.get("display_enabled", True):
            return

        i2c_pins = settings.get_section("display", {}).get("pins", {}).get("i2c", {})
        sda_pin_name = i2c_pins.get("sda")
        scl_pin_name = i2c_pins.get("scl")

        if not sda_pin_name or not scl_pin_name:
            return

        try:
            displayio.release_displays()
            sda_pin = getattr(board, sda_pin_name)
            scl_pin = getattr(board, scl_pin_name)
            i2c = busio.I2C(scl_pin, sda_pin)
            display_bus = displayio.I2CDisplay(i2c, device_address=display_prefs.get("display_address", 60))
            self.display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64, 
                                                             rotation=display_prefs.get("display_rotation", 0))
            
            self.display_font = terminalio.FONT
            self.display_is_ready = True
            self.display_group = displayio.Group()
            self.display.root_group = self.display_group
            
            if not self.in_deep_idle_mode:
                self._update_display(force_update=True)
            
        except:
            self.display = None
            self.display_group = None

    def _init_rotary_encoder(self):
        encoder_pins = settings.get_section("display", {}).get("pins", {}).get("rotary_encoder", {})
        clk_pin_name = encoder_pins.get("clk")
        dt_pin_name = encoder_pins.get("dt")
        sw_pin_name = encoder_pins.get("sw")

        if not all([clk_pin_name, dt_pin_name, sw_pin_name]):
            return

        try:
            clk_pin = getattr(board, clk_pin_name)
            dt_pin = getattr(board, dt_pin_name)
            sw_pin = getattr(board, sw_pin_name)

            self.encoder = rotaryio.IncrementalEncoder(clk_pin, dt_pin)
            self.last_encoder_position = self.encoder.position

            display_prefs = settings.get_section("display", {}).get("preferences", {})
            pull = digitalio.Pull.UP if display_prefs.get("pin_pull_up", True) else digitalio.Pull.DOWN

            timing_prefs = settings.get_section("hid_mapper", {}).get("timing", {})

            self.encoder_button = ButtonDebouncer(
                sw_pin, pull,
                short_press_callback=self._encoder_short_press_handler,
                long_press_callback=self._enter_learning_mode_handler,
                debounce_delay=timing_prefs.get("debounce_time", 0.05),
                long_press_delay=timing_prefs.get("long_press_delay", 1.5)
            )
        except:
            self.encoder = None
            self.encoder_button = None

    def _init_ir_receiver(self):
        if not HAS_IRREMOTE:
             return

        ir_pins = settings.get_section("display", {}).get("pins", {})
        pin_name = ir_pins.get("ir_receiver")

        if not pin_name:
            return

        try:
            pin = getattr(board, pin_name)
            ir_config = settings.get_section("ir_receiver", {})
            self.pulsein = pulseio.PulseIn(pin, maxlen=ir_config.get("maxlen", 200), 
                                         idle_state=ir_config.get("idle_state", True))
            self.pulsein.clear()
            self.decoder = adafruit_irremote.GenericDecode()
            self.ir_manager = IRManager(self.pulsein, self.decoder)
        except:
            self.pulsein = None
            self.decoder = None
            self.ir_manager = None

    def _init_hid(self):
        if not self.usb_connected or not HAS_HID:
             return
        try:
            self.keyboard = Keyboard(usb_hid.devices)
            if HAS_CONSUMER:
                self.consumer_control = ConsumerControl(usb_hid.devices)
        except:
            self.keyboard = None
            self.consumer_control = None

    def _remount_rw(self):
        try:
            import storage
            storage.remount("/", readonly=False)
            time.sleep(0.2)
            return True
        except:
            return False

    def _load_mappings(self):
        try:
            if not self._ensure_mappings_directory():
                return
            
            mapped_count = 0
            mappings_dir = "/mappings"
            
            try:
                files = os.listdir(mappings_dir)
            except:
                if self._remount_rw():
                    try:
                        files = os.listdir(mappings_dir)
                    except:
                        return
                else:
                    return
            
            ir_files = [f for f in files if f.endswith(".ir")]
            
            for filename in ir_files:
                filepath = mappings_dir + "/" + filename
                key_name = filename[:-3]
                display_key_name = key_name.replace("_", "/")
                
                try:
                    with open(filepath, "r") as f:
                        ir_code_hex = f.read().strip()
                        ir_code = int(ir_code_hex, 16)
                        self.ir_mappings[ir_code] = display_key_name
                        mapped_count += 1
                except:
                    continue
            
            if self.ir_manager and self.ir_mappings:
                self.ir_manager.preload_frequent_mappings(self.ir_mappings, max_preload=5)
                
        except:
            pass

    def _get_current_key_data(self):
        if not self.key_groups:
            return "No Groups", []
        group = self.key_groups[self.current_key_group_index % len(self.key_groups)]
        return group[0], group[1]

    def update(self):
        ir_detected = self.handle_ir_signal()
        current_time = time.monotonic()
        
        if hasattr(self, '_last_ir_time') and (current_time - self._last_ir_time) < 0.05:
            time.sleep(0.005)
            return
        
        self._display_count += 1
        
        if self.temp_display_expiry > 0 and current_time >= self.temp_display_expiry:
                self.temp_display_status = None
                self.temp_display_info = None
                self.temp_display_expiry = 0.0
                self._update_display(force_update=True)
        
        self._update_encoder()
        if self.encoder_button:
            self.encoder_button.update()
            
        if self.in_deep_idle_mode and self._display_count % 100 == 0:
            self._update_deep_idle_display()
        
        self._check_idle_mode()
            
        if self._display_count % 500 == 0:
            self.check_usb_status()
            
        if (not hasattr(self, 'current_display_checked') or not self.current_display_checked) and \
           ALL_KEYS_FOR_MAPPING and len(ALL_KEYS_FOR_MAPPING) > 0 and \
           not self.in_deep_idle_mode:
            self._update_display(force_update=True)
            self.current_display_checked = True

        if self.in_learning_mode:
            self.process_learning_mode()

        if self._display_count % 50 == 0 and not self.in_idle_mode:
            self._update_display()
        
        if ir_detected:
            return
        elif self.in_deep_idle_mode:
            time.sleep(0.05)
        elif self.in_idle_mode:
            time.sleep(0.02)
        elif self.in_learning_mode:
            time.sleep(0.01)
        else:
            time.sleep(0.015)

    def _record_activity(self):
        self.last_activity_time = time.monotonic()
        activity_source = getattr(self, '_activity_source', None)
        
        if (self.in_idle_mode or self.in_deep_idle_mode) and activity_source != 'ir':
            self.in_idle_mode = False
            self.in_deep_idle_mode = False
            
            current_time = time.monotonic()
            if self.temp_display_expiry > 0 and current_time >= self.temp_display_expiry:
                self.temp_display_status = None
                self.temp_display_info = None
                self.temp_display_expiry = 0.0
            
            self._display_needs_update = True
            self._update_display(force_update=True)
        
        self._activity_source = None

    def _check_idle_mode(self):
        if self.in_learning_mode or self.temp_display_expiry > 0:
            self.last_activity_time = time.monotonic()
            return
            
        current_time = time.monotonic()
        display_prefs = settings.get_section("display", {}).get("preferences", {})
        
        if self.in_deep_idle_mode:
            return
        
        idle_enabled = display_prefs.get("idle_mode_enabled", True)
        if not idle_enabled or not self.display or not self.display_is_ready:
            return
            
        if self.in_idle_mode:
            deep_idle_enabled = display_prefs.get("deep_idle_enabled", True)
            deep_idle_timeout = display_prefs.get("deep_idle_timeout", 180)
            
            if deep_idle_enabled and (current_time - self.idle_entry_time >= deep_idle_timeout):
                self.in_deep_idle_mode = True
                self._update_deep_idle_display()
            else:
                current_second = int(current_time - self.last_activity_time)
                if not hasattr(self, '_last_displayed_second') or current_second != self._last_displayed_second:
                    self._last_displayed_second = current_second
                    if hasattr(self, '_last_idle_countdown'):
                        delattr(self, '_last_idle_countdown')
                    self._update_idle_display()
        else:
            idle_timeout = display_prefs.get("idle_timeout", 30)
            if (current_time - self.last_activity_time > idle_timeout):
                self.in_idle_mode = True
                self.idle_entry_time = current_time
                self._last_displayed_second = -1
                self._update_idle_display()

    def _update_idle_display(self):
        if not self.display or not self.display_is_ready or not self.in_idle_mode:
            return
            
        display_prefs = settings.get_section("display", {}).get("preferences", {})
        display_enabled = display_prefs.get("idle_display_enabled", True)
        inverted_display = display_prefs.get("idle_display_inverted", True)
        
        if not display_enabled:
            self.display.root_group = displayio.Group()
            return
        
        current_time = time.monotonic()
        idle_seconds = int(current_time - self.last_activity_time)
        
        deep_idle_enabled = display_prefs.get("deep_idle_enabled", True)
        deep_idle_timeout = display_prefs.get("deep_idle_timeout", 180)
        
        if deep_idle_enabled:
            seconds_until_deep_idle = max(0, deep_idle_timeout - idle_seconds)
            if seconds_until_deep_idle <= 1:
                countdown_text = "Sleeping..."
            elif seconds_until_deep_idle > 60:
                mins = seconds_until_deep_idle // 60
                secs = seconds_until_deep_idle % 60
                countdown_text = f"Sleep: {mins}m {secs}s"
            else:
                countdown_text = f"Sleep: {seconds_until_deep_idle}s"
        else:
            countdown_text = f"Idle: {idle_seconds}s"
        
        if hasattr(self, '_last_idle_countdown') and self._last_idle_countdown == countdown_text:
            return
            
        self._last_idle_countdown = countdown_text
        
        temp_group = displayio.Group()
        font = terminalio.FONT
        
        if inverted_display:
            bg_color = 0xFFFFFF
            text_color = 0x000000
            bg_bitmap = displayio.Bitmap(self.display.width, self.display.height, 1)
            bg_palette = displayio.Palette(1)
            bg_palette[0] = bg_color
            bg_rect = displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette)
            temp_group.append(bg_rect)
        else:
            text_color = 0xFFFFFF
        
        line_height = 16
        base_y = 12
        left_margin = 6
        
        usb_status = f"USB: {'Connected' if self.usb_connected else 'Not Connected'}"
        usb_label = label.Label(font, text=usb_status, color=text_color, x=left_margin, y=base_y)
        temp_group.append(usb_label)
        
        mappings_text = f"Mappings: {len(self.ir_mappings)}"
        mappings_label = label.Label(font, text=mappings_text, color=text_color, 
                                   x=left_margin, y=base_y + line_height)
        temp_group.append(mappings_label)
        
        countdown_width = len(countdown_text) * 6
        countdown_x = self.display.width - countdown_width - 6
        countdown_y = 58
        
        countdown_label = label.Label(font, text=countdown_text, color=text_color, 
                                    x=countdown_x, y=countdown_y)
        temp_group.append(countdown_label)
        
        self.display.root_group = temp_group
        self._display_needs_update = False

    def _update_encoder(self):
        if not self.encoder:
            return

        group_name, current_key_list = self._get_current_key_data()
            
        if not current_key_list:
            return

        position = self.encoder.position
        delta = position - self.last_encoder_position

        if delta != 0:
            self._activity_source = 'encoder'
            self._record_activity()
            
            total_keys = len(current_key_list)
            self.current_key_index = (self.current_key_index + delta) % total_keys
            self.last_encoder_position = position
            self._display_needs_update = True
            self._display_dirty = True
            self._update_display()
        
    def handle_ir_signal(self):
        if not self.ir_manager:
            return False
            
        ir_code = self.ir_manager.get_ir_code()
        if not ir_code:
            return False
            
        self._last_ir_time = time.monotonic()
        self._activity_source = 'ir'
        self._record_activity()

        if self.in_learning_mode:
            if self.learning_key_name:
                self.save_mapping(ir_code, self.learning_key_name)
            else:
                self.exit_learn_mode()
        else:
            key_name = self.ir_manager.lookup_mapping(ir_code, self.ir_mappings)
                        
            if key_name:
                if self.in_deep_idle_mode:
                    self._show_ir_command_in_deep_idle(key_name)
                else:
                    self._set_temp_display("Sending", f"{key_name}", 0.5)
                
                self._send_hid_key(key_name)
                self.visual_feedback(True, 0.1, blink_count=1)
            else:
                if self.in_deep_idle_mode:
                    self._show_ir_command_in_deep_idle("Not Mapped")
                else:
                    self._set_temp_display("IR Received", "Not Mapped", 0.5)
                
                self.visual_feedback(True, 0.15, blink_count=2)
        
        return True

    def _show_ir_command_in_deep_idle(self, command_text):
        if not self.display or not self.display_is_ready:
            return
            
        display_prefs = settings.get_section("display", {}).get("preferences", {})
        if not display_prefs.get("deep_idle_display_enabled", True):
            return
            
        temp_group = displayio.Group()
        font = terminalio.FONT
        
        current_time = time.monotonic()
        animation_cycle = (current_time * 8) % 2
        dot = "++++" if animation_cycle < 1 else "****"
            
        dot_label = label.Label(font, text=dot, color=0xFFFFFF,
                              x=self.display.width // 2 - 16, y=self.display.height // 2)
        temp_group.append(dot_label)
        
        max_cmd_length = 18
        if len(command_text) > max_cmd_length:
            command_text = command_text[:max_cmd_length-1] + "…"
            
        cmd_width = len(command_text) * 6
        cmd_x = self.display.width - cmd_width - 4
        cmd_y = 58
        
        cmd_label = label.Label(font, text=command_text, color=0xFFFFFF, x=cmd_x, y=cmd_y)
        temp_group.append(cmd_label)
            
        self.display.root_group = temp_group
        self._deep_idle_cmd_clear_time = time.monotonic() + 2.0
        self._display_needs_update = False

    def _update_deep_idle_display(self):
        if not self.display or not self.display_is_ready or not self.in_deep_idle_mode:
            return
            
        current_time = time.monotonic()
        if hasattr(self, '_deep_idle_cmd_clear_time') and self._deep_idle_cmd_clear_time > 0:
            if current_time >= self._deep_idle_cmd_clear_time:
                self._deep_idle_cmd_clear_time = 0
            else:
                return
            
        display_prefs = settings.get_section("display", {}).get("preferences", {})
        if not display_prefs.get("deep_idle_display_enabled", True):
            self.display.root_group = displayio.Group()
            return
        
        animation_cycle = (current_time * 0.5) % 2
        dot = "++++" if animation_cycle < 1 else "****"
        
        if hasattr(self, '_last_deep_idle_dot') and self._last_deep_idle_dot == dot:
            return
            
        self._last_deep_idle_dot = dot
            
        temp_group = displayio.Group()
        font = terminalio.FONT
        
        dot_label = label.Label(font, text=dot, color=0xFFFFFF,
                              x=self.display.width // 2 - 16, y=self.display.height // 2)
        temp_group.append(dot_label)
            
        self.display.root_group = temp_group
        self._display_needs_update = False

    def _encoder_short_press_handler(self):
        self._activity_source = 'button'
        self._record_activity()
        
        if not self.key_groups or len(self.key_groups) <= 1:
             self.visual_feedback(True, 0.05)
             return
        
        self.current_key_group_index = (self.current_key_group_index + 1) % len(self.key_groups)
        self.current_key_index = 0
        self.last_encoder_position = self.encoder.position
        
        group_name, _ = self._get_current_key_data()
        self._set_temp_display(f"Mode: {group_name}", duration=1.0, update_now=False)
        self.visual_feedback(True, 0.1)
        self._update_display(force_update=True)

    def _enter_learning_mode_handler(self):
        self._activity_source = 'button'
        self._record_activity()
        
        group_name, current_key_list = self._get_current_key_data()
        if not current_key_list:
            self._set_temp_display("Learning", "No keys in group", 1.5)
            self.visual_feedback(True, 0.5, blink_count=2)
            return

        if self.ir_manager:
            self.ir_manager.reset_debounce()

        if self.in_learning_mode:
            return

        self.learning_key_name = current_key_list[self.current_key_index][0].lower()
        self.in_learning_mode = True
        self.learning_start_time = time.monotonic()
        if self.ir_manager:
            self.ir_manager.clear_buffer()
        self.visual_feedback(True)
        self._update_display(force_update=True)

    def _update_display(self, force_update=False, status=None, info=None):
        try:
            if not self.display or not hasattr(self, 'display_is_ready') or not self.display_is_ready:
                return
                
            if (self.in_idle_mode or self.in_deep_idle_mode) and not force_update:
                return
                
            current_time = time.monotonic()
            if self.temp_display_expiry > 0 and current_time >= self.temp_display_expiry:
                self.temp_display_status = None
                self.temp_display_info = None
                self.temp_display_expiry = 0.0
                self._display_needs_update = True
                force_update = True
            
            needs_update = force_update or self._display_needs_update or self._display_dirty or (self._display_count % 50 == 0)
            if not needs_update:
                return
            
            temp_group = displayio.Group()
            font = terminalio.FONT
            
            status_line = (status or self.temp_display_status or self._build_status_line())[:21]
            status_label = label.Label(font, text=status_line, color=0xFFFFFF, x=0, y=10)
            temp_group.append(status_label)
            
            group_name, current_key_list = self._get_current_key_data()
            if not current_key_list:
                key_line = "NO KEYS IN GROUP"
                key_label = label.Label(font, text=key_line, color=0xFFFFFF, x=0, y=32)
                temp_group.append(key_label)
            else:
                current_idx = min(self.current_key_index, len(current_key_list) - 1)
                prev_idx = (current_idx - 1) % len(current_key_list)
                next_idx = (current_idx + 1) % len(current_key_list)
                
                prev_key_orig = current_key_list[prev_idx][0]
                curr_key_orig = current_key_list[current_idx][0]
                next_key_orig = current_key_list[next_idx][0]

                def get_display_key(key_name):
                    return key_name.upper() if len(key_name) == 1 and 'a' <= key_name <= 'z' else key_name

                prev_key = get_display_key(prev_key_orig)
                curr_key = get_display_key(curr_key_orig)
                next_key = get_display_key(next_key_orig)
                
                prev_text = f"< {prev_key}"
                prev_label = label.Label(font, text=prev_text, color=0xFFFFFF, x=0, y=32)
                temp_group.append(prev_label)
                
                curr_text = f"  {curr_key}  "
                current_x = len(prev_text) * 8 + 3
                current_y = 32 + 1
                
                curr_label = label.Label(font, text=curr_text, color=0x000000, background_color=0xFFFFFF,
                                       x=current_x, y=current_y)
                temp_group.append(curr_label)
                
                next_text = f"{next_key} >"
                next_x = current_x + len(curr_text) * 8 + 3
                next_label = label.Label(font, text=next_text, color=0xFFFFFF, x=next_x, y=32)
                temp_group.append(next_label)
            
            if info:
                info_line = info[:21]
            elif self.temp_display_info:
                info_line = self.temp_display_info[:21]
            elif self.in_learning_mode and self.learning_remaining_time > 0:
                info_line = f"Time: {self.learning_remaining_time}s"
            else:
                if current_key_list:
                    current_key = current_key_list[self.current_key_index][0].lower()
                    is_mapped = current_key in self.ir_mappings.values()
                    info_line = "Mapped" if is_mapped else "Not Mapped"
                else:
                    info_line = "NO KEYS IN GROUP"
            
            info_width = len(info_line) * 6
            info_x = self.display.width - info_width - 4
            info_y = 58
            
            info_label = label.Label(font, text=info_line, color=0xFFFFFF, x=info_x, y=info_y)
            temp_group.append(info_label)
            
            self.display.root_group = temp_group
            self._display_needs_update = False
            self._display_dirty = False
            
        except Exception as e:
            try:
                error_group = displayio.Group()
                err_msg = f"ERR: {str(e)[:15]}"
                error_label = label.Label(terminalio.FONT, text=err_msg, color=0xFFFFFF, x=0, y=10)
                error_group.append(error_label)
                self.display.root_group = error_group
            except:
                pass

    def visual_feedback(self, turn_on, duration=None, blink_count=None):
        if not self.led:
            return

        timing = settings.get_section("hid_mapper", {}).get("timing", {})
        duration = duration or timing.get("feedback_duration", 0.3)
        blink_count = blink_count or timing.get("led_blink_count", 2)

        led_state_on = turn_on if not self.led_inverted else not turn_on
        led_state_off = not led_state_on

        if duration is None:
            if self.led.value != led_state_on:
                self.led.value = led_state_on
            return

        if self.led.value != led_state_off:
            self.led.value = led_state_off
            time.sleep(0.01)

        if blink_count < 1: 
            blink_count = 1
        on_time = duration / (blink_count * 2)
        off_time = duration / (blink_count * 2)

        for _ in range(blink_count):
            self.led.value = led_state_on
            time.sleep(on_time)
            self.led.value = led_state_off
            time.sleep(off_time)

        if self.in_learning_mode:
            self.led.value = True if not self.led_inverted else False
        else:
            self.led.value = False if not self.led_inverted else True

    def _build_status_line(self):
        if self.in_learning_mode:
            return "LEARNING: " + (self.learning_key_name or "??")
        else:
            group_name, current_key_list = self._get_current_key_data()
            if current_key_list:
                current_idx = self.current_key_index + 1
                total_keys = len(current_key_list)
                return f"{group_name}: {current_idx}/{total_keys}"
            else:
                return f"{group_name}: No Keys"

    def _ensure_mappings_directory(self):
        try:
            if not self._remount_rw():
                return False
            
            if "mappings" not in os.listdir("/"):
                os.mkdir("/mappings")
            
            test_file = '/mappings/.test'
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return True
        except:
            return False

    def _set_temp_display(self, status=None, info=None, duration=None, update_now=True):
        if duration is None:
            duration = settings.get_value("hid_mapper", "timing", {}).get("temp_message_duration", 0.5)
            
        expiry_time = time.monotonic() + duration
        
        if status is not None:
            self.temp_display_status = status
            
        if info is not None:
            self.temp_display_info = info
            
        self.temp_display_expiry = expiry_time
        self._display_needs_update = True
        
        if update_now:
            self._update_display(force_update=True)
            
        return True

    def exit_learn_mode(self):
        self.in_learning_mode = False
        self.learning_key_name = None
        self.learning_remaining_time = 0
        self.visual_feedback(False)
        
        self.temp_display_status = None
        self.temp_display_info = None
        self.temp_display_expiry = 0.0
        self._display_needs_update = True
        self._update_display(force_update=True)

    def process_learning_mode(self):
        if not self.in_learning_mode:
            return

        timing_prefs = settings.get_section("hid_mapper", {}).get("timing", {})
        timeout = timing_prefs.get("ir_timeout", 20000) / 1000.0
        elapsed = time.monotonic() - self.learning_start_time

        if elapsed >= timeout:
            self._set_temp_display("Timeout", "No IR signal", 1.5)
            self.visual_feedback(True, 0.5, blink_count=2)
            time.sleep(1)
            self.exit_learn_mode()
        else:
            if self.display and int(elapsed) % 2 != int(elapsed-0.1) % 2:
                remaining = int(timeout - elapsed)
                self.learning_remaining_time = remaining
                self._update_display(info=f"Time: {remaining}s", force_update=True)
            else:
                self._display_needs_update = True
                 
            self.visual_feedback(True)

    def save_mapping(self, ir_code, key_name):
        try:
            if not self._ensure_mappings_directory():
                self._set_temp_display("Error", "Directory inaccessible", 1.5)
                self.visual_feedback(True, 0.1, blink_count=5)
                time.sleep(1.5)
                self.exit_learn_mode()
                return False
            
            safe_filename = key_name.lower().replace("/", "_")
            filepath = f"/mappings/{safe_filename}.ir"
            ir_code_hex = f"0x{ir_code:08x}"
            
            write_success = False
            for attempt in range(3):
                try:
                    if attempt > 0:
                        self._remount_rw()
                    
                    if attempt == 0 and "mappings" not in os.listdir("/"):
                        try:
                            os.mkdir("/mappings")
                        except:
                            continue
                    
                    with open(filepath, "w") as f:
                        f.write(ir_code_hex)
                    write_success = True
                    break
                except:
                    time.sleep(0.3)
            
            if not write_success:
                self._set_temp_display("Save Error", "Try again", 1.5)
                self.visual_feedback(True, 0.1, blink_count=5)
                time.sleep(1.5)
                self.exit_learn_mode()
                return False
            
            self.ir_mappings[ir_code] = key_name.lower()
            
            if self.ir_manager and len(self.ir_manager.mapping_cache) < self.ir_manager.max_cache_size:
                    self.ir_manager.mapping_cache[ir_code] = key_name.lower()
                    self.ir_manager.cache_usage_count[ir_code] = 0
                    self.ir_manager.cache_access_time[ir_code] = time.monotonic()
            
            self._display_needs_update = True
            self._set_temp_display("Saved", f"{key_name}", 1.0)
            
            time.sleep(1)
            self.exit_learn_mode()
            return True
        except:
            self.visual_feedback(True, 0.1, blink_count=5)
            return False

    def _send_hid_key(self, key_name):
        try:
            if not self.check_usb_status():
                self._set_temp_display("USB Not Connected", "Cannot send key", 2.0)
                self.visual_feedback(True, 0.1, blink_count=3)
                return False
            
            if not hasattr(self, 'keyboard') or not self.keyboard:
                return False
                
            key_name = key_name.lower()
                
            if key_name not in COMMAND_NAME_TO_KEYCODE:
                alt_key_name = key_name.replace("_", "/")
                if alt_key_name in COMMAND_NAME_TO_KEYCODE:
                    key_name = alt_key_name
                else:
                    return False
            
            key_code = COMMAND_NAME_TO_KEYCODE[key_name]
            
            if isinstance(key_code, tuple) and len(key_code) == 3 and key_code[2]:
                if hasattr(self, 'consumer_control') and self.consumer_control:
                    self.consumer_control.send(key_code[1])
                else:
                    return False
            else:
                if isinstance(key_code, tuple):
                    self.keyboard.press(*key_code)
                    self.keyboard.release_all()
                else:
                    self.keyboard.press(key_code)
                    self.keyboard.release_all()
                    
            return True
        except:
            return False 