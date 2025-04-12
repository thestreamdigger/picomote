"""
Main device logic for Picomote

Handles:
- Rotary encoder input for HID key selection
- OLED display updates
- IR signal reception and decoding
- Button debouncing and long press detection for learning mode
- Saving IR code mappings to files
- Sending HID keyboard commands
- Status LED feedback
"""

import time
import board
import digitalio
import pulseio
import rotaryio
import busio
import displayio
import terminalio
import struct
import gc
import os
import supervisor

# Configuration and HID imports
from config import (
    settings, logger, __version__,
    MEDIA_KEYS, KEYBOARD_KEYS, ALL_KEYS_FOR_MAPPING, COMMAND_NAME_TO_KEYCODE,
    HAS_KEYCODE, HAS_CONSUMER, HAS_IRREMOTE
)

try:
    import adafruit_irremote
    # Não redefinir HAS_IRREMOTE pois já é importado de config.py
except ImportError:
    logger.error("Device", "adafruit_irremote library not found! IR functionality limited.")
    # Não sobrescrever HAS_IRREMOTE, apenas logar o erro

try:
    from adafruit_hid.keyboard import Keyboard
    import usb_hid
    HAS_HID = True
except ImportError:
    logger.error("Device", "adafruit_hid library not found! HID Keyboard disabled.")
    HAS_HID = False

try:
    from adafruit_hid.consumer_control import ConsumerControl
    HAS_CONSUMER_CONTROL = True and HAS_CONSUMER  # Will only be True if both are true
except ImportError:
    logger.error("Device", "adafruit_hid.consumer_control not found! Media keys disabled.")
    HAS_CONSUMER_CONTROL = False

try:
    from adafruit_display_text import label
    import adafruit_displayio_ssd1306
    HAS_DISPLAY = True
except ImportError:
    logger.warning("Device", "Display libraries (adafruit_display_text, adafruit_displayio_ssd1306) not found. Display disabled.")
    HAS_DISPLAY = False

class ButtonDebouncer:
    """
    Handles button debouncing and detects short/long presses.
    Modified to directly handle callbacks for short and long press.
    """
    def __init__(self, pin, pull, short_press_callback=None, long_press_callback=None,
                 debounce_delay=0.05, long_press_delay=1.5):
        self.button = digitalio.DigitalInOut(pin)
        self.button.direction = digitalio.Direction.INPUT
        self.button.pull = pull
        self.last_state = self.button.value # Initialize with current state
        self.debounce_time = time.monotonic()
        self.debounce_delay = debounce_delay
        self.long_press_delay = long_press_delay

        self.short_press_callback = short_press_callback
        self.long_press_callback = long_press_callback

        self.pressed = False
        self.press_start_time = 0
        self.long_press_triggered = False

    def update(self):
        """
        Checks the button state and triggers callbacks.
        Returns True if a callback was triggered, False otherwise.
        """
        triggered = False
        current_time = time.monotonic()
        button_state = self.button.value

        if button_state != self.last_state and (current_time - self.debounce_time) >= self.debounce_delay:
            self.debounce_time = current_time
            logger.debug("Button", f"State changed! New state: {button_state} (Pull-up means False=Pressed)")

            if not button_state:
                self.pressed = True
                self.press_start_time = current_time
                self.long_press_triggered = False
                logger.debug("Button", "Button Press registered.")
            else:
                self.pressed = False
                logger.debug("Button", "Button Release registered.")
                if not self.long_press_triggered and self.short_press_callback:
                    press_duration = current_time - self.press_start_time
                    if press_duration >= self.debounce_delay:
                         logger.debug("Button", f"Short press callback triggered (duration: {press_duration:.2f}s)")
                         self.short_press_callback()
                         triggered = True
                elif self.long_press_triggered:
                    logger.debug("Button", "Release after long press, short press callback skipped.")

            self.last_state = button_state

        if self.pressed and not self.long_press_triggered and self.long_press_callback:
            if (current_time - self.press_start_time) >= self.long_press_delay:
                logger.debug("Button", "Long press callback triggered.")
                self.long_press_callback()
                self.long_press_triggered = True
                triggered = True

        return triggered


class HIDMapperDevice:
    """
    Main class for the Picomote device.
    """
    def __init__(self):
        logger.info("Device", "Initializing Picomote...")
        self.led = None
        self.led_inverted = False
        self.encoder = None
        self.encoder_button = None
        self.display = None
        self.display_group = None
        self.status_label = None
        self.prev_label = None
        self.current_label = None
        self.next_label = None
        self.info_label = None
        self.pulsein = None
        self.decoder = None
        self.keyboard = None
        self.consumer_control = None  # For media keys
        self.keyboard_layout = None # For potential future international layouts
        
        # New variables for display control
        self._display_needs_update = True
        self._display_count = 0

        # --- Temporary Display State ---
        self.temp_display_status = None
        self.temp_display_info = None
        self.temp_display_expiry = 0.0
        # ------------------------------

        # --- Learning Mode Display State ---
        self.learning_remaining_time = 0
        # -----------------------------------

        # --- Key Group Management ---
        self.key_groups = []
        if MEDIA_KEYS: # Only add if not empty
             self.key_groups.append(("Media", MEDIA_KEYS))
        if KEYBOARD_KEYS: # Only add if not empty
             self.key_groups.append(("Keyboard", KEYBOARD_KEYS))
        
        self.current_key_group_index = 0 # Start with the first available group
        self.current_key_index = 0 # Index within the current group
        self.last_encoder_position = 0
        # -------------------------
        
        self.ir_mappings = {} # Dictionary to store loaded IR code -> key_name mappings

        self.in_learning_mode = False
        self.learning_key_name = None
        self.learning_start_time = 0

        # Check if we have valid key groups available
        if not self.key_groups:
            logger.error("Device", "No valid key groups found (MEDIA_KEYS or KEYBOARD_KEYS are empty). Check libraries/config.")
            # Exibir mensagem de erro no display se possível
        else:
            logger.info("Device", f"Initialized with {len(self.key_groups)} key groups.")

        logger.debug("Init", "Attempting initial filesystem remount...")
        try:
            import storage
            storage.remount("/", readonly=False)
            logger.debug("Init", "Filesystem remount successful.")
        except Exception as e:
            logger.warning("Init", f"Filesystem remount failed: {e}")

        logger.debug("Init", "Initializing LED...")
        self._init_led()
        logger.debug("Init", "Initializing Display...")
        self._init_display()
        logger.debug("Init", "Initializing Rotary Encoder...")
        self._init_rotary_encoder()
        logger.debug("Init", "Initializing IR Receiver...")
        self._init_ir_receiver()
        logger.debug("Init", "Initializing HID...")
        self._init_hid()
        
        logger.debug("Init", "Ensuring mappings directory...")
        self._ensure_mappings_directory()
        
        logger.debug("Init", "Loading mappings...")
        self._load_mappings()

        logger.debug("Init", "Performing initial display update...")
        self._update_display()
        self.visual_feedback(False)
        logger.info("Device", "Initialization complete.")

    # --- Initialization Methods --- #

    def _init_led(self):
        """Initializes the main status LED (GP25)."""
        led_config = settings.get_section("status_leds", {}).get("main_led", {})
        pin_name = led_config.get("pin", "GP25")
        self.led_inverted = led_config.get("is_inverted", False)
        try:
            pin = getattr(board, pin_name)
            self.led = digitalio.DigitalInOut(pin)
            self.led.direction = digitalio.Direction.OUTPUT
            self.led.value = self.led_inverted # Start OFF
            logger.info("LED", f"Initialized on {pin_name}")
        except Exception as e:
            logger.error("LED", f"Failed to initialize on {pin_name}: {e}")
            self.led = None

    def _init_display(self):
        """Initializes the OLED display."""
        self.display_is_ready = False  # Initialize display readiness flag
        
        if not HAS_DISPLAY:
            logger.warning("Display", "Skipping initialization - libraries missing.")
            return

        display_prefs = settings.get_section("display", {}).get("preferences", {})
        if not display_prefs.get("display_enabled", True):
            logger.info("Display", "Disabled in settings.")
            return

        i2c_pins = settings.get_section("display", {}).get("pins", {}).get("i2c", {})
        sda_pin_name = i2c_pins.get("sda")
        scl_pin_name = i2c_pins.get("scl")
        i2c_address = display_prefs.get("display_address", 60)
        rotation = display_prefs.get("display_rotation", 0)

        if not sda_pin_name or not scl_pin_name:
            logger.error("Display", "I2C pins (SDA/SCL) not defined in settings.")
            return

        try:
            logger.debug("Display", "Starting OLED display...")
            displayio.release_displays() # Release any previous display
            sda_pin = getattr(board, sda_pin_name)
            scl_pin = getattr(board, scl_pin_name)
            i2c = busio.I2C(scl_pin, sda_pin)
            display_bus = displayio.I2CDisplay(i2c, device_address=i2c_address)
            self.display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64, rotation=rotation)
            logger.debug("Display", "OLED display initialized successfully")
            
            # Initialize font
            self.display_font = terminalio.FONT
            
            # Mark display as ready for internal use
            self.display_is_ready = True
            
            # Create an empty display group as placeholder
            self.display_group = displayio.Group()
            self.display.root_group = self.display_group
            
            # Use the same update method for initial content to ensure consistent positioning
            logger.debug("Display", "Populating initial display content...")
            self._update_display(force_update=True)
            
            logger.info("Display", f"OLED 128x64 Initialized (Rotation: {rotation})")

        except Exception as e:
            logger.error("Display", f"Initialization failed: {e}")
            self.display = None
            self.display_group = None

    def _init_rotary_encoder(self):
        """Initializes the rotary encoder and its button."""
        encoder_pins = settings.get_section("display", {}).get("pins", {}).get("rotary_encoder", {})
        clk_pin_name = encoder_pins.get("clk")
        dt_pin_name = encoder_pins.get("dt")
        sw_pin_name = encoder_pins.get("sw")

        if not clk_pin_name or not dt_pin_name or not sw_pin_name:
            logger.error("Encoder", "Pins (CLK/DT/SW) not defined in settings.")
            return

        try:
            clk_pin = getattr(board, clk_pin_name)
            dt_pin = getattr(board, dt_pin_name)
            sw_pin = getattr(board, sw_pin_name)

            self.encoder = rotaryio.IncrementalEncoder(clk_pin, dt_pin)
            self.last_encoder_position = self.encoder.position

            # Use ButtonDebouncer for the switch
            display_prefs = settings.get_section("display", {}).get("preferences", {})
            pull_up = display_prefs.get("pin_pull_up", True)
            pull = digitalio.Pull.UP if pull_up else digitalio.Pull.DOWN

            timing_prefs = settings.get_section("hid_mapper", {}).get("timing", {})
            debounce = timing_prefs.get("debounce_time", 0.05)
            long_press = timing_prefs.get("long_press_delay", 1.5)

            self.encoder_button = ButtonDebouncer(
                sw_pin,
                pull,
                short_press_callback=self._encoder_short_press_handler, # Define later if needed
                long_press_callback=self._enter_learning_mode_handler,
                debounce_delay=debounce,
                long_press_delay=long_press
            )
            logger.info("Encoder", f"Initialized (CLK:{clk_pin_name}, DT:{dt_pin_name}, SW:{sw_pin_name}) LongPress: {long_press}s")

        except Exception as e:
            logger.error("Encoder", f"Initialization failed: {e}")
            self.encoder = None
            self.encoder_button = None

    def _init_ir_receiver(self):
        """Initializes the IR receiver."""
        if not HAS_IRREMOTE:
             logger.warning("IR", "Skipping initialization - library missing.")
             return

        ir_pins = settings.get_section("display", {}).get("pins", {})
        pin_name = ir_pins.get("ir_receiver")
        ir_config = settings.get_section("ir_receiver", {})
        maxlen = ir_config.get("maxlen", 250)
        idle_state = ir_config.get("idle_state", True)

        if not pin_name:
            logger.error("IR", "Pin not defined in settings.")
            return

        try:
            pin = getattr(board, pin_name)
            logger.debug("IR", f"Got pin {pin_name}")
            self.pulsein = pulseio.PulseIn(pin, maxlen=maxlen, idle_state=idle_state)
            logger.debug("IR", "PulseIn created successfully")
            self.pulsein.clear()
            logger.debug("IR", "PulseIn cleared")
            self.decoder = adafruit_irremote.GenericDecode()
            logger.debug("IR", "GenericDecode created successfully")
            logger.info("IR", f"Receiver initialized on {pin_name}")
        except Exception as e:
            logger.error("IR", f"Initialization failed on {pin_name}: {e}")
            self.pulsein = None
            self.decoder = None

    def _init_hid(self):
        """Initializes the USB HID Keyboard device."""
        logger.debug("HID Init", "Starting HID initialization...")
        if not HAS_HID:
             logger.warning("HID Init", "Skipping initialization - adafruit_hid library missing.")
             return
        try:
            logger.debug("HID Init", "Attempting to initialize Keyboard...")
            self.keyboard = Keyboard(usb_hid.devices)
            logger.info("HID Init", "Keyboard device initialized successfully.")
            
            logger.debug("HID Init", "Attempting to initialize Consumer Control...")
            if HAS_CONSUMER_CONTROL:
                self.consumer_control = ConsumerControl(usb_hid.devices)
                logger.info("HID Init", "Media Controls initialized successfully.")
            else:
                logger.warning("HID Init", "Consumer Control library not available, skipping.")
                
        except Exception as e:
            logger.error("HID Init", f"Initialization failed: {e}")
            self.keyboard = None
            self.consumer_control = None
        logger.debug("HID Init", f"Finished. Keyboard: {self.keyboard is not None}, ConsumerControl: {self.consumer_control is not None}")

    def _load_mappings(self):
        """Load the saved mappings from files in the /mappings directory."""
        logger.info("Mappings", "Loading from /mappings/ directory...")
        try:
            # Ensure that the mappings directory exists and is accessible
            if not self._ensure_mappings_directory():
                logger.warning("Mappings", "Could not access the mappings directory, continuing with zero mappings")
                return
            
            mapped_count = 0
            mappings_dir = "/mappings"
            
            # Try to list the directory with robust error handling
            try:
                files = os.listdir(mappings_dir)
            except OSError as e:
                logger.error("Mappings", f"Error listing directory (errno {e.args[0]}): {e}")
                # Try to remount and list again
                try:
                    import storage
                    storage.remount("/", readonly=False)
                    time.sleep(0.3)
                    files = os.listdir(mappings_dir)
                    logger.info("Mappings", "Directory listed after remount")
                except Exception as e2:
                    logger.error("Mappings", f"Could not list directory after remount: {e2}")
                    return
            except Exception as e:
                logger.error("Mappings", f"Unexpected error listing directory: {e}")
                return
            
            logger.debug("Mappings", f"Found {len(files)} files in /mappings")
            
            for filename in files:
                if filename.endswith(".ir"):
                    filepath = mappings_dir + "/" + filename
                    
                    # Extract key name from filename (remove .ir extension)
                    key_name = filename[:-3]
                    
                    # Convert underscores back to slashes for display names (e.g. "play_pause" -> "play/pause")
                    # Keep command names in lowercase for consistency
                    display_key_name = key_name.replace("_", "/")
                    
                    try:
                        with open(filepath, "r") as f:
                            ir_code_hex = f.read().strip()
                            # Convert hex string to int
                            try:
                                ir_code = int(ir_code_hex, 16)
                                # Add to mappings dict
                                self.ir_mappings[ir_code] = display_key_name
                                logger.debug("Mappings", f"Loaded: {key_name} -> {ir_code_hex}")
                                mapped_count += 1
                            except ValueError as ve:
                                logger.error("Mappings", f"Invalid format in {filename}: {ve}")
                    except OSError as e:
                        logger.error("Mappings", f"Filesystem error reading {filename} (errno {e.args[0]}): {e}")
                    except Exception as e:
                        logger.error("Mappings", f"Error reading {filename}: {e}")
            
            logger.info("Mappings", f"Loaded {mapped_count} mappings.")
        except Exception as e:
            logger.error("Mappings", f"Error loading mappings: {e}")

    # --- Helper for Key Group --- #
    def _get_current_key_list(self):
        """Returns the list of key tuples for the currently selected group."""
        if not self.key_groups:
            return [] # Return empty list if no groups defined
        # Ensure index is valid (though it should be)
        group_idx = self.current_key_group_index % len(self.key_groups)
        return self.key_groups[group_idx][1] # Return the list part of the tuple

    def _get_current_group_name(self):
        """Returns the name of the currently selected group."""
        if not self.key_groups:
            return "No Groups"
        group_idx = self.current_key_group_index % len(self.key_groups)
        return self.key_groups[group_idx][0] # Return the name part of the tuple

    # --- Update and Event Handling Methods --- #

    def update(self):
        """Main update loop called repeatedly."""
        # Increment display counter
        self._display_count += 1
        
        # Check if any temporary message has expired - do this FIRST
        current_time = time.monotonic()
        if self.temp_display_expiry > 0:
            if current_time >= self.temp_display_expiry:
                logger.debug("Update", f"Temp display expired at {self.temp_display_expiry:.2f}, current time {current_time:.2f}")
                # Reset temporary display variables
                self.temp_display_status = None
                self.temp_display_info = None
                self.temp_display_expiry = 0.0
                # Force an update to return to home screen
                self._update_display(force_update=True)
                logger.debug("Update", "Returned to home screen after temp message expired")
        
        # Ensure we have valid keys to display (on first run)
        if (not hasattr(self, 'current_display_checked') or not self.current_display_checked) and \
           ALL_KEYS_FOR_MAPPING and len(ALL_KEYS_FOR_MAPPING) > 0 and ALL_KEYS_FOR_MAPPING[0][0] != "LIB_ERR":
            logger.debug("Update", "First update loop - forcing display update.")
            self._update_display(force_update=True)
            self.current_display_checked = True

        self._update_encoder()
        
        if self.encoder_button:
            self.encoder_button.update()

        if self.in_learning_mode:
            self.process_learning_mode()
        else:
            self.handle_ir_signal()

        # Periodically update display to ensure state is correct
        if self._display_count % 100 == 0:  # Every ~1 second (assuming 0.01s update cycle)
            self._update_display()

        # Garbage collection periodically
        # Consider doing this less frequently if performance allows
        # if time.monotonic() % 10 < 0.01: # Roughly every 10 seconds
        #    gc.collect()

    def _update_encoder(self):
        """Reads encoder position and updates the selected key index WITHIN the current group."""
        if not self.encoder:
            return

        current_key_list = self._get_current_key_list()
            
        if not current_key_list: # Check if the current list is empty
            return

        position = self.encoder.position
        delta = position - self.last_encoder_position

        if delta != 0:
            logger.debug("Encoder", f"Change detected: Delta={delta}, LastPos={self.last_encoder_position}, NewPos={position}")
            total_keys = len(current_key_list)
            # Update index within the current group, ensuring it wraps around correctly
            self.current_key_index = (self.current_key_index + delta) % total_keys
            self.last_encoder_position = position
            logger.debug("Encoder", f"Group: '{self._get_current_group_name()}', New Index: {self.current_key_index}, Key: {current_key_list[self.current_key_index][0]}")
            self._display_needs_update = True # Signal display update needed
            self._update_display() # Update display immediately on change
        
    def handle_ir_signal(self):
        """Checks for IR signals, decodes them, and acts accordingly."""
        # Use explicit checks like in cmd-ir
        if not hasattr(self, 'pulsein') or self.pulsein is None:
            # Try to initialize the IR receiver if possible
            try:
                self._init_ir_receiver()
                if not hasattr(self, 'pulsein') or self.pulsein is None:
                    return
            except Exception as e:
                logger.debug("IR", f"Could not initialize IR: {e}")
                return
                
        if not hasattr(self, 'decoder') or self.decoder is None:
            # Try to initialize the decoder if possible
            try:
                if HAS_IRREMOTE:
                    self.decoder = adafruit_irremote.GenericDecode()
                else:
                    return
            except Exception as e:
                logger.debug("IR", f"Could not initialize decoder: {e}")
                return
                
        # Check length *after* confirming objects exist
        if len(self.pulsein) == 0:
            return
        else:
            logger.debug("IR", f"PulseIn buffer has data (length: {len(self.pulsein)}). Attempting read...")

        pulses = None
        try:
            pulses = self.decoder.read_pulses(self.pulsein, blocking=False)
            if not pulses:
                logger.debug("IR", "read_pulses returned None (likely incomplete signal).")
                return
            logger.debug("IR", f"Read {len(pulses)} pulses.")
            
            if len(pulses) < 8: # Ignore noise / incomplete signals
                logger.debug("IR", "Ignoring signal - too short.")
                return

            # Attempt decoding
            logger.debug("IR", "Attempting to decode pulses...")
            code_values = self.decoder.decode_bits(pulses)
            logger.debug("IR", f"Decoded bits: {code_values}")

            # NEC typical structure: 4 bytes (Address, ~Address, Command, ~Command)
            # We use the full 32-bit sequence as the unique code for mapping.
            if len(code_values) >= 4:
                # Construct the 32-bit integer code
                ir_code = 0
                for byte_val in code_values[:4]: # Use first 4 bytes
                    ir_code = (ir_code << 8) | byte_val

                logger.debug("IR", f"Constructed IR Code: {hex(ir_code)} ({ir_code})")

                # --- Action based on mode ---
                if self.in_learning_mode:
                    logger.debug("IR", "Device in learning mode.")
                    if self.learning_key_name:
                        logger.debug("IR", f"Calling save_mapping for key '{self.learning_key_name}'")
                        self.save_mapping(ir_code, self.learning_key_name)
                    else:
                        logger.warning("IR", "Received code in learning mode, but no key selected.")
                        self.exit_learn_mode()
                else:
                    logger.debug("IR", "Device in normal mode.")
                    # Normal mode: Check if code is mapped
                    if ir_code in self.ir_mappings:
                        key_name = self.ir_mappings[ir_code]
                        logger.debug("IR", f"Code {hex(ir_code)} FOUND in mappings for key '{key_name}'.")
                        # Adicionar feedback visual antes de enviar o comando
                        self._set_temp_display(status="Sending", info=f"{key_name}", duration=1.0)
                        self.visual_feedback(True, 0.1, blink_count=1)  # Feedback visual rápido
                        # Enviar o comando HID
                        self._send_hid_key(key_name)
                    else:
                        logger.debug("IR", f"Code {hex(ir_code)} NOT found in mappings.")
                        # Replace _update_display with _set_temp_display
                        self._set_temp_display(status="IR Received", info="Not Mapped", duration=1.0)
                        self.visual_feedback(True, 0.15, blink_count=2) # Feedback for received code

            else:
                logger.warning("IR", f"Decoded incomplete code (length {len(code_values)}): {code_values}")

        except adafruit_irremote.IRNECRepeatException:
            logger.debug("IR", "NEC Repeat code ignored.")
            pass # Ignore repeat codes for simplicity now
        except adafruit_irremote.IRDecodeException as e:
            logger.warning("IR", f"Decoding failed: {e}")
            if self.in_learning_mode:
                 # Replace _update_display with _set_temp_display
                 self._set_temp_display(status="Decode Error", duration=1.0)
                 self.visual_feedback(True, 0.5, blink_count=2) # Feedback less negative
                 time.sleep(1)
                 self.exit_learn_mode()
        except Exception as e:
            logger.error("IR", f"Error processing signal: {e}")
            # Attempt to recover by clearing pulsein if it exists
            if self.pulsein:
                try: self.pulsein.clear() 
                except: pass 
        finally:
            # Ensure buffer is cleared after processing or error, if pulsein exists
            if self.pulsein:
                 try: self.pulsein.clear() 
                 except: pass

    # --- Mapping and HID Methods --- #

    def save_mapping(self, ir_code, key_name):
        """Save a mapping between an IR code and a key."""
        try:
            # Verify and create the mappings directory (with better error handling)
            if not self._ensure_mappings_directory():
                logger.error("Save", "Mappings directory not available or cannot be written to")
                self._set_temp_display(status="Error", info="Directory inaccessible", duration=1.5)
                self.visual_feedback(True, 0.1, blink_count=5)  # Error feedback with 5 quick blinks
                time.sleep(1.5)
                self.exit_learn_mode()
                return False
            
            # Standardize filenames:
            # 1. Convert to lowercase
            # 2. Convert slashes (/) to underscores (_)
            # Example: "Play/Pause" -> "play_pause"
            safe_filename = key_name.lower().replace("/", "_")
            
            filepath = f"/mappings/{safe_filename}.ir"
            logger.debug("Save", f"Attempting to save mapping to {filepath}")
            
            # Convert int to hex string
            ir_code_hex = f"0x{ir_code:08x}"
            
            # Try to force filesystem to be writable
            try:
                import storage
                storage.remount("/", readonly=False)
                logger.debug("Save", "Filesystem remounted as writable")
                time.sleep(0.3)  # Give time for the system to stabilize
            except Exception as e:
                logger.warning("Save", f"Filesystem remount failed: {e}")
            
            # Attempt file write
            write_success = False
            for attempt in range(3):  # Try up to 3 times
                try:
                    logger.debug("Save", f"Write attempt {attempt+1} for {filepath}")
                    
                    # Check again if the directory exists (may have been accidentally removed)
                    if "mappings" not in os.listdir("/"):
                        logger.warning("Save", "Mappings directory not found, recreating...")
                        try:
                            os.mkdir("/mappings")
                        except Exception as dir_e:
                            logger.error("Save", f"Could not create directory: {dir_e}")
                            continue  # Try next iteration
                    
                    # Now try writing the actual file
                    with open(filepath, "w") as f:
                        f.write(ir_code_hex)
                    write_success = True
                    logger.debug("Save", f"Successfully wrote mapping to {filepath}")
                    break
                except OSError as e:
                    # Specifically handle read-only filesystem error
                    if e.args[0] == 30:  # EROFS (Read-only file system)
                        logger.error("Save", "Filesystem is read-only, trying to remount")
                        try:
                            import storage
                            storage.remount("/", readonly=False)
                            time.sleep(0.5)  # Longer wait for remounting
                        except Exception as remount_error:
                            logger.error("Save", f"Remount failed: {remount_error}")
                    else:
                        logger.error("Save", f"Filesystem error: {e}")
                    time.sleep(0.5)  # Wait a bit before retrying
                except Exception as e:
                    logger.error("Save", f"Write attempt {attempt+1} failed: {e}")
                    time.sleep(0.5)  # Wait a bit before retrying
            
            if not write_success:
                logger.error("Save", f"Failed to save mapping after multiple attempts")
                self._set_temp_display(status="Save Error", info=f"Try again", duration=1.5)
                self.visual_feedback(True, 0.1, blink_count=5)  # Error feedback with 5 quick blinks
                time.sleep(1.5)
                self.exit_learn_mode()
                return False
            
            # Important: Update the mapping dictionary with lowercase names with slashes
            # Keep consistency with how commands are stored
            self.ir_mappings[ir_code] = key_name.lower()
            logger.info("Save", f"Mapping saved: {key_name.lower()} -> {ir_code_hex}")
            
            # Update display
            self._display_needs_update = True
            self._set_temp_display(status="Saved", info=f"{key_name.lower()}", duration=1.0)
            
            # Exit learning mode after successful save
            time.sleep(1)  # Show the success message for a moment
            self.exit_learn_mode()
            
            return True
        except Exception as e:
            logger.error("Save", f"Error saving mapping: {e}")
            self.visual_feedback(True, 0.1, blink_count=5)  # Error feedback with 5 quick blinks
            return False

    def _check_filesystem_writable(self):
        """Checks if the filesystem is writable by attempting to create a temp file."""
        test_file = '/.fs_writable_test'
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return True
        except OSError as e:
            if e.args[0] == 30: # errno 30 is Read-Only Filesystem
                 logger.warning("FS Check", "Filesystem is read-only.")
            else:
                 logger.error("FS Check", f"Unexpected OSError checking writability: {e}")
            return False
        except Exception as e:
            logger.error("FS Check", f"Error during writability check: {e}")
            return False

    def _send_hid_key(self, key_name):
        """Sends a key press using HID keyboard or consumer control."""
        try:
            # Check if we have a valid keyboard instance
            if not hasattr(self, 'keyboard') or not self.keyboard:
                logger.error("HID", "No keyboard device available")
                return False
                
            # Standardize key_name to lowercase for consistency
            key_name = key_name.lower()
                
            # Check if the key exists in our mapping dictionary
            if key_name not in COMMAND_NAME_TO_KEYCODE:
                # Try with underscore replacement for backward compatibility
                alt_key_name = key_name.replace("_", "/")
                if alt_key_name in COMMAND_NAME_TO_KEYCODE:
                    key_name = alt_key_name
                    logger.debug("HID", f"Using alternate key name: {key_name}")
                else:
                    logger.error("HID", f"Key name '{key_name}' not found in COMMAND_NAME_TO_KEYCODE.")
                    return False
            
            key_code = COMMAND_NAME_TO_KEYCODE[key_name]
            
            # Check if it's a media key (tuple containing name, code, is_media flag)
            if isinstance(key_code, tuple) and len(key_code) == 3 and key_code[2]:
                if hasattr(self, 'consumer_control') and self.consumer_control:
                    logger.debug("HID", f"Sending media key: {key_name}")
                    self.consumer_control.send(key_code[1])  # Send media code
                else:
                    logger.error("HID", "No consumer control device available")
                    return False
            else:
                # Regular keyboard key
                logger.debug("HID", f"Sending keyboard key: {key_name}")
                
                # Handle single key or key combinations
                if isinstance(key_code, tuple):
                    # It's a key combination (e.g., Shift+A)
                    self.keyboard.press(*key_code)
                    self.keyboard.release_all()
                else:
                    # Single key
                    self.keyboard.press(key_code)
                    self.keyboard.release_all()
                    
            logger.debug("HID", f"Key sent successfully: {key_name}")
            return True
            
        except Exception as e:
            logger.error("HID", f"Error sending key {key_name}: {e}")
            return False

    # --- Display and Feedback Methods --- #

    def _update_display(self, force_update=False, status=None, info=None):
        """Update the display with current status."""
        try:
            if not self.display or not hasattr(self, 'display_is_ready') or not self.display_is_ready:
                return
                
            # Check and update temporary state expiration
            # Note: primary expiration check is now in the update() method
            # This is just a fallback check
            current_time = time.monotonic()
            if self.temp_display_expiry > 0 and current_time >= self.temp_display_expiry:
                logger.debug("Display", f"Backup expiration check: Temp message expired at {self.temp_display_expiry:.2f}")
                self.temp_display_status = None
                self.temp_display_info = None
                self.temp_display_expiry = 0.0
                self._display_needs_update = True  # Force update after temporary expires
                force_update = True  # Force update immediately when messages expire
            
            # Decide if update is needed
            needs_update = force_update or self._display_needs_update or (self._display_count % 20 == 0)
            if not needs_update:
                return
                
            logger.debug("Display", "Updating display content...")
            
            # Create a new display group each time
            temp_group = displayio.Group()
            font = terminalio.FONT
            
            # Status line (priority order: passed status > temp_status > normal)
            if status:
                status_line = status[:21]  # Limit to display width
            elif self.temp_display_status:
                status_line = self.temp_display_status[:21]
            else:
                status_line = self._build_status_line()
            
            status_label = label.Label(font, text=status_line, color=0xFFFFFF, x=0, y=8)
            temp_group.append(status_label)
            
            # Selection line: Show available keys from the CURRENT GROUP
            current_key_list = self._get_current_key_list()
            if not current_key_list:
                key_line = "NO KEYS IN GROUP"
                key_label = label.Label(font, text=key_line, color=0xFFFFFF, x=0, y=28)
                temp_group.append(key_label)
            else:
                current_idx = self.current_key_index
                current_idx = min(current_idx, len(current_key_list) - 1)  # Ensure valid index
                
                prev_idx = (current_idx - 1) % len(current_key_list)
                next_idx = (current_idx + 1) % len(current_key_list)
                
                # Get original key names from the current list
                prev_key_orig = current_key_list[prev_idx][0]
                curr_key_orig = current_key_list[current_idx][0]
                next_key_orig = current_key_list[next_idx][0]

                # --- Display Transformation (Always Uppercase Letters) --- 
                def get_display_key(key_name):
                    if len(key_name) == 1 and 'a' <= key_name <= 'z':
                        return key_name.upper() # Show letters as uppercase
                    return key_name # Keep others as is (e.g., "Play/Pause", "Enter")

                prev_key = get_display_key(prev_key_orig)
                curr_key = get_display_key(curr_key_orig)
                next_key = get_display_key(next_key_orig)
                # ---------------------------------------------------------
                
                # Add previous key with "< " prefix
                prev_text = f"< {prev_key}"
                prev_label = label.Label(font, text=prev_text, color=0xFFFFFF, x=0, y=28)
                temp_group.append(prev_label)
                
                # Add current key with highlighted background and padding
                # Add spaces before and after the text for padding
                curr_text = f"  {curr_key}  "  # 2 spaces of padding on each side
                
                # Position current text with additional horizontal padding
                current_x = len(prev_text) * 8 + 3  # Reduced to move closer to previous key
                
                # Vertical offset to create simulated vertical padding (moving text down)
                current_y = 28 + 1 # Move text 1px down to simulate vertical padding
                
                curr_label = label.Label(
                    font, 
                    text=curr_text, 
                    color=0x000000,  # Black text
                    background_color=0xFFFFFF,  # White background
                    x=current_x, 
                    y=current_y
                )
                temp_group.append(curr_label)
                
                # Add next key with " >" suffix
                next_text = f"{next_key} >"
                # Position next key after current key with adjusted spacing
                next_x = current_x + len(curr_text) * 8 + 3  # Reduced to move closer to current key
                next_label = label.Label(font, text=next_text, color=0xFFFFFF, x=next_x, y=28)
                temp_group.append(next_label)
            
            # Info line (priority order: passed info > temp_info > learning countdown > normal)
            if info:
                info_line = info[:21]  # Limit to display width
            elif self.temp_display_info:
                info_line = self.temp_display_info[:21]
            elif self.in_learning_mode and self.learning_remaining_time > 0:
                # During learning mode, always show the countdown timer
                info_line = f"Time: {self.learning_remaining_time}s"
            else:
                # Use the ORIGINAL key name (lowercase) for mapping check
                if current_key_list:
                    current_key = current_key_list[self.current_key_index][0].lower()  # MODIFICADO: converter para minúsculas
                    is_mapped = current_key in self.ir_mappings.values()
                    if is_mapped:
                        info_line = "Mapped"
                    else:
                        info_line = "Not Mapped"
                else:
                    info_line = "NO KEYS IN GROUP"
            
            #info_x = max(0, (self.display.width - len(info_line) * 8) // 2) # Commented to align left
            info_x = 0 # Force left alignment
            info_label = label.Label(font, text=info_line, color=0xFFFFFF, x=info_x, y=48)
            temp_group.append(info_label)
            
            # Update the display with the new group
            self.display.root_group = temp_group
            
            self._display_needs_update = False # Reset the flag after update
            
        except Exception as e:
            logger.error("Display", f"Update error: {e}")
            try:
                # Create a minimal error display
                error_group = displayio.Group()
                err_msg = f"ERR: {str(e)[:15]}"
                error_label = label.Label(terminalio.FONT, text=err_msg, color=0xFFFFFF, x=0, y=8)
                error_group.append(error_label)
                self.display.root_group = error_group
                logger.debug("Display", "Displayed error message.")
            except Exception as display_err:
                logger.error("Display", f"Fatal display error: {display_err}")

    def visual_feedback(self, turn_on, duration=None, blink_count=None):
        """Controls the main status LED for feedback (solid or blinking)."""
        if not self.led:
            return

        try:
            timing_prefs = settings.get_section("hid_mapper", {}).get("timing", {})
            default_duration = duration if duration is not None else timing_prefs.get("feedback_duration", 0.3)
            default_blink_count = blink_count if blink_count is not None else timing_prefs.get("led_blink_count", 2)

            # Normalize blink count to be at least 1 for blinking
            if duration is not None and default_blink_count < 1: default_blink_count = 1

            led_state_on = turn_on if not self.led_inverted else not turn_on
            led_state_off = not led_state_on

            # Solid ON/OFF state (used for learning mode indication or direct state setting)
            if duration is None:
                 if self.led.value != led_state_on:
                      self.led.value = led_state_on
                 return

            # Blinking feedback
            initial_state = self.led.value
            # Ensure LED starts in the OFF state for the blink sequence unless it should be ON
            if self.led.value != led_state_off:
                self.led.value = led_state_off
                time.sleep(0.01) # Small delay before starting blink

            if default_blink_count <= 0: default_blink_count = 1 # Ensure at least one blink cycle
            on_time = default_duration / (default_blink_count * 2)
            off_time = default_duration / (default_blink_count * 2)

            for _ in range(default_blink_count):
                self.led.value = led_state_on
                time.sleep(on_time)
                self.led.value = led_state_off
                time.sleep(off_time)

            # Restore state: Stay ON if in learning mode, otherwise turn OFF
            # (Previously restored initial_state, but better to ensure OFF unless learning)
            if self.in_learning_mode:
                 self.led.value = True if not self.led_inverted else False # Stay ON in learning
            else:
                 self.led.value = False if not self.led_inverted else True # Default to OFF

        except Exception as e:
            logger.error("LED Feedback", f"Error: {e}")

    def _build_status_line(self):
        """Builds the status line for the display based on current device state"""
        if self.in_learning_mode:
            return "LEARNING: " + (self.learning_key_name or "??")
        else:
            # Show current group name and index within the group
            group_name = self._get_current_group_name()
            current_key_list = self._get_current_key_list()
            if current_key_list:
                current_idx = self.current_key_index + 1  # Human-readable (1-based)
                total_keys = len(current_key_list)
                return f"{group_name}: {current_idx}/{total_keys}"
            else:
                return f"{group_name}: No Keys"

    def _ensure_mappings_directory(self):
        """Ensures that the /mappings directory exists and is writable."""
        logger.debug("Mapping Dir", "Checking for /mappings directory...")
        try:
            # First, try to ensure that the filesystem is writable
            try:
                import storage
                storage.remount("/", readonly=False)
                logger.debug("Mapping Dir", "Remounted filesystem as writable")
                time.sleep(0.2)  # Small delay for filesystem to stabilize
            except Exception as e:
                logger.warning("Mapping Dir", f"Initial remount attempt failed: {e}")

            # Check if the /mappings directory exists
            has_mappings_dir = "mappings" in os.listdir("/")
            logger.debug("Mapping Dir", f"Directory exists: {has_mappings_dir}")
            
            if not has_mappings_dir:
                logger.warning("Mapping", "/mappings/ directory missing, attempting creation.")
                # Try to create the directory directly
                try:
                    os.mkdir("/mappings")
                    logger.info("Mapping", "Created /mappings/ directory.")
                    has_mappings_dir = True
                except OSError as e:
                    if e.args[0] == 30:  # EROFS (Read-only file system)
                        logger.error("Mapping", "Filesystem is read-only, attempting remount")
                        
                        # Try remounting to create directory
                        for attempt in range(3):
                            try:
                                import storage
                                storage.remount("/", readonly=False)
                                logger.info("Mapping", f"Remounted filesystem as writable (attempt {attempt+1})")
                                time.sleep(0.5)  # Longer time between attempts
                                
                                # Try again to create the directory
                                os.mkdir("/mappings")
                                logger.info("Mapping", "Created /mappings/ directory after remount.")
                                has_mappings_dir = True
                                break
                            except Exception as e2:
                                logger.error("Mapping", f"Remount/creation attempt {attempt+1} failed: {e2}")
                                time.sleep(0.3)
                    else:
                        logger.error("Mapping", f"Error creating directory (errno {e.args[0]}): {e}")
                except Exception as e:
                    logger.error("Mapping", f"Unexpected error creating directory: {e}")
            
            # Check if the directory was created successfully
            if not has_mappings_dir:
                logger.error("Mapping Dir", "Failed to create /mappings directory after multiple attempts")
                return False
                
            # Check if the directory is writable
            logger.debug("Mapping Dir", "Checking directory writability...")
            test_file = '/mappings/.write_test'
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                logger.debug("Mapping Dir", "Writability test successful.")
                return True
            except OSError as e:
                if e.args[0] == 30:  # EROFS (Read-only file system)
                    logger.error("Mapping Dir", "Filesystem still read-only after remount attempts")
                    # Last remount attempt
                    try:
                        import storage
                        storage.remount("/", readonly=False)
                        time.sleep(0.5)
                        
                        # Try the write test again
                        with open(test_file, 'w') as f:
                            f.write('test')
                        os.remove(test_file)
                        logger.debug("Mapping Dir", "Writability test successful after final remount.")
                        return True
                    except Exception as final_e:
                        logger.error("Mapping Dir", f"Final remount/write attempt failed: {final_e}")
                else:
                    logger.error("Mapping Dir", f"Writability test failed (errno {e.args[0]}): {e}")
                return False
            except Exception as e:
                logger.error("Mapping Dir", f"Writability test failed with unexpected error: {e}")
                return False
                
        except Exception as e:
            logger.error("Mapping", f"General error checking /mappings/: {e}")
            return False

    def _set_temp_display(self, status=None, info=None, duration=None, update_now=True):
        """Set a temporary message to display on the OLED.
        
        Args:
            status: Text for the status line (top)
            info: Text for the information line (bottom)
            duration: Duration in seconds. If None, uses default from settings.json.
            update_now: If True, update the display immediately
        """
        # Get default duration from settings if not provided
        if duration is None:
            duration = settings.get_value("hid_mapper", "timing", {}).get("temp_message_duration", 2.0)
            
        # Calculate exact expiration time
        expiry_time = time.monotonic() + duration
        logger.debug("Display", f"Setting temporary display - Status: '{status}', Info: '{info}', Duration: {duration}s, Will expire at: {expiry_time:.2f}")
        
        if status is not None:
            self.temp_display_status = status
            
        if info is not None:
            self.temp_display_info = info
            
        # Set expiration time based on current time
        self.temp_display_expiry = expiry_time
        
        # Force a display update
        self._display_needs_update = True
        
        # Update the display immediately if requested
        if update_now:
            self._update_display(force_update=True)
            
        # Schedule clearing after duration has passed
        # We cannot use actual threading/timers in CircuitPython, but we log the intent
        logger.debug("Display", f"Will return to home screen at time {expiry_time:.2f}")
            
        return True  # For use in conditional expressions

    def exit_learn_mode(self):
        """Exits learning mode and returns to normal operation."""
        logger.info("Learn", "Exiting learning mode.")
        self.in_learning_mode = False
        self.learning_key_name = None
        self.learning_remaining_time = 0  # Reset the remaining time
        self.visual_feedback(False) # Turn LED OFF
        
        # Clear any temporary display messages
        self.temp_display_status = None
        self.temp_display_info = None
        self.temp_display_expiry = 0.0
        
        # Force clear any display updates in the queue
        self._display_needs_update = True
        
        # Force display update to show normal state (home screen)
        logger.debug("Learn", "Forcing display update to return to home screen")
        self._update_display(force_update=True)

    def process_learning_mode(self):
        """Manages the learning mode state (timeout, IR check)."""
        if not self.in_learning_mode:
            return

        # Check for IR signal first
        if hasattr(self, 'pulsein') and self.pulsein is not None and len(self.pulsein) > 0:
            self.handle_ir_signal() # This will exit learning mode if successful
            return # Don't check timeout immediately after receiving signal

        # Check for timeout
        timing_prefs = settings.get_section("hid_mapper", {}).get("timing", {})
        timeout = timing_prefs.get("ir_timeout", 20000) / 1000.0 # ms to s
        elapsed = time.monotonic() - self.learning_start_time

        if elapsed >= timeout:
            logger.warning("Learn", "Timeout waiting for IR signal.")
            self._set_temp_display(status="Timeout", info="No IR signal", duration=1.5)
            self.visual_feedback(True, 0.5, blink_count=2) # Feedback less negative
            time.sleep(1) # Show message
            self.exit_learn_mode()
        else:
            # Update display periodically with countdown - but don't use temp_display mechanism
            # for this to avoid interfering with the normal display updates
            if self.display and int(elapsed) % 2 != int(elapsed-0.1) % 2: # Update every second approx
                remaining = int(timeout - elapsed)
                # Store the remaining time in the instance variable for use in other display updates
                self.learning_remaining_time = remaining
                # The learning mode itself overrides the display via _build_status_line
                # Just pass the remaining time via the info parameter without setting temp_display
                # Show time remaining on display without setting temp display variables
                self._update_display(info=f"Time: {remaining}s", force_update=True)
            else:
                # Ensure the display is updated with the correct time even if not at the exact interval
                self._display_needs_update = True
                 
            # Keep LED solid ON during learning
            self.visual_feedback(True)

    def _encoder_short_press_handler(self):
        """Handles short press of the encoder button to cycle through key groups."""
        if not self.key_groups or len(self.key_groups) <= 1:
             logger.debug("Button", "Short press ignored - only one (or zero) key group defined.")
             self.visual_feedback(True, 0.05) # Very short blink
             return
             
        logger.info("Button", "Encoder short press detected - Cycling key group.")
        
        # Cycle to the next group
        self.current_key_group_index = (self.current_key_group_index + 1) % len(self.key_groups)
        self.current_key_index = 0 # Reset index within the new group
        self.last_encoder_position = self.encoder.position # Reset encoder tracking for the new list
        
        group_name = self._get_current_group_name()
        logger.debug("Button", f"Switched to group: {group_name}")
        
        # Provide feedback
        self._set_temp_display(status=f"Mode: {group_name}", duration=1.0, update_now=False) # Update forced below
        self.visual_feedback(True, 0.1) # Quick blink
        
        # Force display update to show the new group
        self._update_display(force_update=True)

    def _enter_learning_mode_handler(self):
        """Callback for long press on encoder button to enter learning mode for the selected key in the current group."""
        logger.debug("Learn", "Enter learning mode handler triggered.") # Log entry
        
        current_key_list = self._get_current_key_list()
        if not current_key_list:
            logger.warning("Learn", "No keys defined in the current group for mapping")
            self._set_temp_display(status="Learning", info="No keys in group", duration=1.5)
            self.visual_feedback(True, 0.5, blink_count=2)
            return

        # Try to initialize IR if needed
        if not hasattr(self, 'pulsein') or self.pulsein is None:
            logger.warning("Learn", "IR not initialized, trying...")
            try:
                self._init_ir_receiver()
            except Exception as e:
                logger.error("Learn", f"Failed to initialize IR: {e}")
                
        if not hasattr(self, 'decoder') or self.decoder is None:
            logger.warning("Learn", "Decoder not initialized, trying...")
            try:
                if HAS_IRREMOTE:
                    self.decoder = adafruit_irremote.GenericDecode()
                else:
                    return
            except Exception as e:
                logger.error("Learn", f"Failed to initialize decoder: {e}")

        # Even with failures, we try to enter learning mode
        if self.in_learning_mode:
            return # Already in learning mode

        # Assign only the key name (string) from the sequence tuple IN THE CURRENT GROUP
        # Convert to lowercase for consistency
        self.learning_key_name = current_key_list[self.current_key_index][0].lower()
        
        # Log the assigned key name directly
        logger.info("Learn", f"Entering learning mode for key: {self.learning_key_name}")
        self.in_learning_mode = True
        self.learning_start_time = time.monotonic()
        if self.pulsein:
            try:
                self.pulsein.clear() # Clear buffer before starting
            except Exception as e:
                logger.error("Learn", f"Error clearing buffer: {e}")
        self.visual_feedback(True) # Turn LED ON solid for learning
        # The _update_display will show learning mode via _build_status_line
        self._update_display(force_update=True)
