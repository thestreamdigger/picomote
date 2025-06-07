"""Main execution file for Picomote IR"""

import time
import supervisor
import traceback

from config import logger, settings, HAS_KEYCODE, HAS_CONSUMER, HAS_IRREMOTE, __version__
from device import HIDMapperDevice

def main():
    logger.info("Main", f"--- Starting Picomote IR v{__version__} ---")
    device = None
    try:
        device = HIDMapperDevice()

        while True:
            device.update()
            time.sleep(0.01)

    except KeyboardInterrupt:
        if device and device.display:
            try:
                device.display.root_group = None
            except:
                pass

    except Exception as e:
        logger.error("Main", "!!! FATAL ERROR in main loop !!!")
        logger.error("Main", f"Error Type: {type(e).__name__}")
        logger.error("Main", f"Error Args: {e.args}")

        print("--- TRACEBACK ---")
        traceback.print_exception(e, e, e.__traceback__)
        print("-----------------")

        reboot_delay = settings.get_value("hid_mapper", "timing", {}).get("reboot_delay", 10)

        if device and device.led:
            try:
                for _ in range(reboot_delay * 4):
                    device.led.value = not device.led.value
                    time.sleep(0.125)
            except:
                pass

        time.sleep(reboot_delay)
        supervisor.reload()

if __name__ == "__main__":
    main() 