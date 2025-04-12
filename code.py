"""
Picomote - Main Execution File

Initializes the device and runs the main update loop.
"""

import time
import supervisor
import traceback
import gc

# Import configuration and device logic
from config import logger, settings, HAS_KEYCODE, HAS_CONSUMER, HAS_IRREMOTE
from device import HIDMapperDevice

# --- Main Execution --- #

def main():
    logger.info("Main", "--- Starting Picomote ---")
    device = None
    try:
        # Initialize the main device class
        device = HIDMapperDevice()
        logger.ok("Main", "Device initialized successfully.")

        # Main loop
        while True:
            # Call the device's update method repeatedly
            device.update()

            # Small delay to prevent excessive CPU usage and allow USB servicing
            # Adjust if needed, but 0 is often fine for blocking I/O
            time.sleep(0.01)

    except KeyboardInterrupt:
        # Graceful exit on Ctrl+C in the REPL
        logger.info("Main", "KeyboardInterrupt detected. Exiting gracefully.")
        if device and device.display:
            try:
                # Clear display on exit
                device.display.root_group = None
            except Exception as display_e:
                logger.warning("Main", f"Could not clear display on exit: {display_e}")

    except Exception as e:
        # Log fatal error and attempt reboot
        logger.error("Main", "!!! FATAL ERROR in main loop !!!")
        logger.error("Main", f"Error Type: {type(e).__name__}")
        logger.error("Main", f"Error Args: {e.args}")

        # Print traceback to console
        print("--- TRACEBACK ---")
        traceback.print_exception(e, e, e.__traceback__)
        print("-----------------")

        reboot_delay = settings.get_value("hid_mapper", "timing", {}).get("reboot_delay", 10)
        logger.error("Main", f"Attempting reboot in {reboot_delay} seconds...")

        # Blink LED rapidly to indicate error before reboot
        if device and device.led:
            try:
                for _ in range(reboot_delay * 4): # Faster blink
                    device.led.value = not device.led.value
                    time.sleep(0.125)
            except Exception as led_e:
                logger.error("Main", f"Could not blink LED during error: {led_e}")

        time.sleep(reboot_delay) # Wait before rebooting
        supervisor.reload() # Attempt to reload the main script

    finally:
        # Cleanup actions if needed (though reboot often handles this)
        logger.info("Main", "--- Program End ---")

if __name__ == "__main__":
    main() 