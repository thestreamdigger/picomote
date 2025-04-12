"""
Boot script for Picomote

- Configures USB endpoints (CDC Console, HID Keyboard, HID Consumer Control)
- Enables USB drive (Mass Storage) for file transfers
- Makes internal filesystem writable
- Disables auto-reload
- Creates /mappings directory if needed
"""

import board
import storage
import usb_cdc
import supervisor
import time
import os

print("--- Boot Sequence Started ---")

try:
    import usb_hid
    # Define the HID keyboard device
    # Report ID 0x01: Keyboard
    # Uses standard 8-byte Boot Keyboard report descriptor
    # You can customize descriptors if needed for more advanced HID features
    KEYBOARD_DEVICE = usb_hid.Device(
        report_descriptor=bytes([
            # Standard Boot Keyboard Report Descriptor
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
        usage_page=0x01, # Generic Desktop
        usage=0x06,      # Keyboard
        in_report_lengths=[8], # Standard 8-byte keyboard report
        out_report_lengths=[1],# Standard 1-byte LED report
        report_ids=[1],       # Report ID 1
    )
    print("Boot: USB HID Keyboard device defined.")

    # Define the HID Consumer Control device
    CONSUMER_CONTROL_DEVICE = usb_hid.Device(
        report_descriptor=bytes((
            0x05, 0x0C,        # Usage Page (Consumer)
            0x09, 0x01,        # Usage (Consumer Control)
            0xA1, 0x01,        # Collection (Application)
            0x75, 0x10,        #   Report Size (16) bits = 2 bytes
            0x95, 0x01,        #   Report Count (1)
            0x15, 0x01,        #   Logical Minimum (1)
            0x26, 0xFF, 0x03,  #   Logical Maximum (1023)
            0x19, 0x01,        #   Usage Minimum (1)
            0x2A, 0xFF, 0x03,  #   Usage Maximum (1023)
            0x81, 0x00,        #   Input (Data, Array)
            0xC0               # End Collection
        )),
        usage_page=0x0C, # Consumer
        usage=0x01,      # Consumer Control
        in_report_lengths=[2], # 2 bytes for consumer control code
        out_report_lengths=[0], # No output report needed
    )
    print("Boot: USB HID Consumer Control device defined.")

    # Enable CDC console and BOTH HID Devices
    usb_cdc.enable(console=True, data=False)
    usb_hid.enable((KEYBOARD_DEVICE, CONSUMER_CONTROL_DEVICE))
    print("Boot: USB CDC Console, HID Keyboard, and Consumer Control enabled.")

except Exception as e:
    print(f"Boot ERROR enabling HID: {e}")
    # Fallback: Enable only CDC if HID fails
    usb_cdc.enable(console=True, data=False)
    print("Boot WARN: HID failed, only CDC Console enabled.")

# Disable USB drive for file transfers if desired (comment out the try block)
# try:
#     storage.enable_usb_drive()
#     print("Boot: USB drive enabled for file transfers.")
# except Exception as e:
#     print(f"Boot ERROR enabling USB drive: {e}")

# Remount filesystem as writable
for remount_attempt in range(3):
    try:
        storage.remount("/", readonly=False)
        print(f"Boot: Filesystem remounted as writable (attempt {remount_attempt+1}).")
        # Writability verification check
        test_file = '/.fs_writable_test'
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            print("Boot: Filesystem writability verified successfully.")
            break  # Exit loop if successful
        except Exception as test_e:
            print(f"Boot WARN: Write test failed after remount: {test_e}")
            if remount_attempt < 2:  # Don't try after the last iteration
                print("Boot: Will try remounting again...")
                time.sleep(0.5)  # Wait before trying again
    except RuntimeError as e:
        print(f"Boot ERROR remounting FS (attempt {remount_attempt+1}): {e}")
        if remount_attempt < 2:  # Don't try after the last iteration
            print("Boot: Will try remounting again...")
            time.sleep(0.5)  # Wait before trying again
    except Exception as e:
        print(f"Boot FATAL ERROR during remount (attempt {remount_attempt+1}): {e}")
        if remount_attempt < 2:
            print("Boot: Will try remounting again with delay...")
            time.sleep(1.0)  # Wait longer after severe error

# Disable auto-reload for stability
supervisor.runtime.autoreload = False
print("Boot: Auto-reload disabled.")

# Create /mappings directory if it doesn't exist
print("Boot: Checking for /mappings directory...")
for dir_attempt in range(3):
    try:
        if "mappings" not in os.listdir("/"):
            print(f"Boot: /mappings directory not found, creating... (attempt {dir_attempt+1})")
            os.mkdir("/mappings")
            # Check if directory was created
            if "mappings" in os.listdir("/"):
                print("Boot: /mappings directory created successfully.")
                # Check if directory is writable
                test_file = '/mappings/.write_test'
                try:
                    with open(test_file, 'w') as f:
                        f.write('test')
                    os.remove(test_file)
                    print("Boot: /mappings directory is writable.")
                    break  # Exit loop if everything is good
                except Exception as wt_e:
                    print(f"Boot WARN: /mappings directory write test failed: {wt_e}")
                    # Continue to try remounting again
            else:
                print("Boot WARN: mkdir command did not raise error but directory not created.")
        else:
            print("Boot: /mappings directory already exists.")
            # Check if directory is writable
            test_file = '/mappings/.write_test'
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                print("Boot: /mappings directory is writable.")
                break  # Exit loop if everything is good
            except Exception as wt_e:
                print(f"Boot WARN: /mappings directory is not writable: {wt_e}")
                # Try remounting to fix permissions
                try:
                    storage.remount("/", readonly=False)
                    time.sleep(0.5)
                    print("Boot: Remounted filesystem after directory write failure.")
                except Exception as rm_e:
                    print(f"Boot ERROR: Remount after write failure failed: {rm_e}")
                    
    except OSError as e:
        # Common errors: 13 (EACCES), 30 (EROFS), 17 (EEXIST - should be handled above)
        print(f"Boot ERROR creating /mappings directory (errno {e.args[0]}, attempt {dir_attempt+1}): {e}")
        if e.args[0] == 30:  # EROFS (Read-only file system)
            print("Boot WARN: Filesystem is read-only, attempting remount...")
            try:
                storage.remount("/", readonly=False)
                time.sleep(0.5)
                print("Boot: Remounted filesystem after EROFS error.")
            except Exception as rm_e:
                print(f"Boot ERROR: Remount after EROFS failed: {rm_e}")
        if dir_attempt < 2:  # Don't try after the last iteration
            print("Boot: Will try creating directory again...")
            time.sleep(0.5)
    except Exception as e:
        print(f"Boot FATAL ERROR checking/creating /mappings (attempt {dir_attempt+1}): {e}")
        if dir_attempt < 2:
            print("Boot: Will try again...")
            time.sleep(0.5)

print("--- Boot Sequence Complete ---")
# Boot sequence finishes, control passes to code.py