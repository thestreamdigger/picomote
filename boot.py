"""Boot script for Picomote IR"""

import board
import storage
import usb_cdc
import supervisor
import time
import os

print("--- Boot Sequence Started ---")

storage.disable_usb_drive()

try:
    import usb_hid
    KEYBOARD_DEVICE = usb_hid.Device(
        report_descriptor=bytes([
            0x05, 0x01,  # Usage Page (Generic Desktop)
            0x09, 0x06,  # Usage (Keyboard)
            0xA1, 0x01,  # Collection (Application)
            0x05, 0x07,  # Usage Page (Key Codes)
            0x19, 0xE0,  # Usage Minimum (Left Control)
            0x29, 0xE7,  # Usage Maximum (Right GUI)
            0x15, 0x00,  # Logical Minimum (0)
            0x25, 0x01,  # Logical Maximum (1)
            0x75, 0x01,  # Report Size (1)
            0x95, 0x08,  # Report Count (8)
            0x81, 0x02,  # Input (Data, Variable, Absolute)
            0x95, 0x01,  # Report Count (1)
            0x75, 0x08,  # Report Size (8)
            0x81, 0x01,  # Input (Constant)
            0x95, 0x05,  # Report Count (5)
            0x75, 0x01,  # Report Size (1)
            0x05, 0x08,  # Usage Page (LEDs)
            0x19, 0x01,  # Usage Minimum (Num Lock)
            0x29, 0x05,  # Usage Maximum (Kana)
            0x91, 0x02,  # Output (Data, Variable, Absolute)
            0x95, 0x01,  # Report Count (1)
            0x75, 0x03,  # Report Size (3)
            0x91, 0x01,  # Output (Constant)
            0x95, 0x06,  # Report Count (6)
            0x75, 0x08,  # Report Size (8)
            0x15, 0x00,  # Logical Minimum (0)
            0x25, 0xFF,  # Logical Maximum(255)
            0x05, 0x07,  # Usage Page (Key Codes)
            0x19, 0x00,  # Usage Minimum (0)
            0x29, 0xFF,  # Usage Maximum (255)
            0x81, 0x00,  # Input (Data, Array)
            0xC0         # End Collection
        ]),
        usage_page=0x01,
        usage=0x06,
        in_report_lengths=[8],
        out_report_lengths=[1],
        report_ids=[1],
    )

    CONSUMER_CONTROL_DEVICE = usb_hid.Device(
        report_descriptor=bytes((
            0x05, 0x0C,        # Usage Page (Consumer)
            0x09, 0x01,        # Usage (Consumer Control)
            0xA1, 0x01,        # Collection (Application)
            0x75, 0x10,        # Report Size (16) bits = 2 bytes
            0x95, 0x01,        # Report Count (1)
            0x15, 0x01,        # Logical Minimum (1)
            0x26, 0xFF, 0x03,  # Logical Maximum (1023)
            0x19, 0x01,        # Usage Minimum (1)
            0x2A, 0xFF, 0x03,  # Usage Maximum (1023)
            0x81, 0x00,        # Input (Data, Array)
            0xC0               # End Collection
        )),
        usage_page=0x0C,
        usage=0x01,
        in_report_lengths=[2],
        out_report_lengths=[0],
    )

    usb_cdc.enable(console=True, data=False)
    usb_hid.enable((KEYBOARD_DEVICE, CONSUMER_CONTROL_DEVICE))

except Exception as e:
    print(f"Boot ERROR enabling HID: {e}")
    usb_cdc.enable(console=True, data=False)

for remount_attempt in range(3):
    try:
        storage.remount("/", readonly=False)
        
        test_file = '/.fs_writable_test'
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            break
        except Exception as test_e:
            if remount_attempt < 2:
                time.sleep(0.5)
    except Exception as e:
        if remount_attempt < 2:
            time.sleep(0.5)

supervisor.runtime.autoreload = False

for dir_attempt in range(3):
    try:
        if "mappings" not in os.listdir("/"):
            os.mkdir("/mappings")
            
            if "mappings" in os.listdir("/"):
                test_file = '/mappings/.write_test'
                try:
                    with open(test_file, 'w') as f:
                        f.write('test')
                    os.remove(test_file)
                    break
                except Exception as wt_e:
                    pass
        else:
            test_file = '/mappings/.write_test'
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                break
            except Exception as wt_e:
                try:
                    storage.remount("/", readonly=False)
                    time.sleep(0.5)
                except Exception as rm_e:
                    pass
                    
    except OSError as e:
        if e.args[0] == 30:
            try:
                storage.remount("/", readonly=False)
                time.sleep(0.5)
            except Exception as rm_e:
                pass
        if dir_attempt < 2:
            time.sleep(0.5)
    except Exception as e:
        if dir_attempt < 2:
            time.sleep(0.5)

print("--- Boot Sequence Complete ---")

