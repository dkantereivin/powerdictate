"""
Option E: Raspberry Pi / Hardware Sidecar USB-C Audio Gadget & Bridge
======================================================================
Provides configuration utilities for running PowerDictate on or with a
portable Raspberry Pi / Linux USB OTG device configured as a USB Audio Class 2 (UAC2)
Gadget or Bluetooth Audio Bridge.
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, Any


USB_GADGET_SETUP_SCRIPT = """#!/usr/bin/env bash
# USB Audio Gadget Configuration for Raspberry Pi (UAC2)
# Configures USB-C OTG port to present the Pi as a USB Digital Microphone / Headset to any phone.

set -e

CONFIGFS_ROOT="/sys/kernel/config"
GADGET_DIR="$CONFIGFS_ROOT/usb_gadget/powerdictate"

if [ ! -d "$CONFIGFS_ROOT" ]; then
    echo "Configfs not found. Run: sudo modprobe libcomposite"
    exit 1
fi

sudo modprobe libcomposite

if [ -d "$GADGET_DIR" ]; then
    echo "Gadget already configured."
    exit 0
fi

sudo mkdir -p "$GADGET_DIR"
cd "$GADGET_DIR"

# USB Vendor/Product IDs (Standard USB Audio Class)
echo 0x1d6b > idVendor  # Linux Foundation
echo 0x0101 > idProduct # Audio Gadget
echo 0x0200 > bcdUSB
echo 0x0100 > bcdDevice

mkdir -p strings/0x409
echo "CTU-Dictation-001" > strings/0x409/serialnumber
echo "PowerDictate" > strings/0x409/manufacturer
echo "Medical Audio Bridge" > strings/0x409/product

# Create UAC2 Audio Function
mkdir -p functions/uac2.usb0
# Configure 8kHz mono audio for hospital telephony standard
echo 8000 > functions/uac2.usb0/c_srate
echo 1 > functions/uac2.usb0/c_chmask
echo 8000 > functions/uac2.usb0/p_srate
echo 1 > functions/uac2.usb0/p_chmask

# Link function to configuration
mkdir -p configs/c.1
mkdir -p configs/c.1/strings/0x409
echo "Audio Config" > configs/c.1/strings/0x409/configuration
ln -s functions/uac2.usb0 configs/c.1/

# Enable Gadget on UDC
UDC_NAME=$(ls /sys/class/udc | head -n 1)
echo "$UDC_NAME" > UDC

echo "USB Audio Gadget active on $UDC_NAME. Plug USB-C into smartphone."
"""


class PiSidecarBridge:
    """
    Manages Raspberry Pi USB Audio Gadget and remote playback bridge.
    """

    @staticmethod
    def get_gadget_install_script() -> str:
        """Returns bash script to setup USB-C Audio Gadget on Raspberry Pi / Linux OTG."""
        return USB_GADGET_SETUP_SCRIPT

    @staticmethod
    def write_gadget_script_to_disk(output_path: str = "scripts/setup_usb_gadget.sh") -> Path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(USB_GADGET_SETUP_SCRIPT, encoding="utf-8")
        out.chmod(0o755)
        return out
