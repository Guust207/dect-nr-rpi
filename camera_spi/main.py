# Imports
import time
import sys
import signal
import struct
import spidev
import cv2
import numpy as np
import RPi.GPIO as GPIO
from picamera2 import Picamera2

picam2 = None
spi = None

# Ready pin from nRF (active high = ready for new image)
READY_PIN = 25  # GPIO25 (physical pin 22)

HEADER_MAGIC = b'IMG\x00'
MAX_DATA_SIZE = 32768
JPEG_QUALITY = 45

def cleanup(signum=None, frame=None):
    global picam2, spi
    print("Cleaning up...")

    GPIO.cleanup()

    if spi:
        spi.close()

    if picam2:
        try:
            picam2.stop()
        except:
            pass
        picam2.close()

    sys.exit(0)
# End function


def wait_for_ready(timeout=5.0):
    start = time.monotonic()
    if GPIO.input(READY_PIN) == 0:
        print("Waiting for nRF ready...")
    while GPIO.input(READY_PIN) == 0:
        if time.monotonic() - start > timeout:
            print("WARNING: Ready timeout!")
            return False
        time.sleep(0.001)
    waited = time.monotonic() - start
    if waited > 0.01:
        print(f"nRF ready after {waited*1000:.0f}ms")
    return True
# End function


def capture_jpeg():
    """Capture JPEG using array capture + cv2 encode (faster than capture_file)."""
    global picam2

    t0 = time.monotonic()
    array = picam2.capture_array()
    t_capture = time.monotonic()

    # picamera2 returns RGB, cv2 expects BGR
    bgr = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
    ret, jpeg = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    t_encode = time.monotonic()

    data = jpeg.tobytes()
    print(f"Captured {len(data)} bytes "
          f"(capture: {(t_capture - t0) * 1000:.0f}ms, "
          f"encode: {(t_encode - t_capture) * 1000:.0f}ms)")
    return data
# End function


def send_image(data):
    """Send image using header-based protocol with ready pin handshake.
    
    Protocol:
      Phase 1: Wait for ready, send 8-byte header (magic 'IMG\\0' + uint32 LE size)
      Phase 2: Wait for ready, send entire image data in one transfer
    """
    global spi

    data_size = len(data)
    if data_size > MAX_DATA_SIZE:
        print(f"Image too large ({data_size} bytes), skipping")
        return

    t_start = time.monotonic()

    # Phase 1: Send header
    if not wait_for_ready():
        print("nRF not ready for header, skipping")
        return

    header = HEADER_MAGIC + struct.pack('<I', data_size)
    spi.xfer3(list(header))

    t_header = time.monotonic()
    print(f"Header sent: {data_size} bytes announced")

    # Phase 2: Send image data
    if not wait_for_ready():
        print("nRF not ready for image data, skipping")
        return

    spi.xfer3(data)

    elapsed = time.monotonic() - t_start
    throughput = data_size / elapsed / 1024
    print(f"Image sent: {data_size} bytes in {elapsed * 1000:.0f}ms "
          f"({throughput:.1f} KB/s, header: {(t_header - t_start) * 1000:.0f}ms)")
# End function


def main():
    global picam2, spi

    # Signal handling
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    # GPIO setup for ready pin
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(READY_PIN, GPIO.IN)

    # Initialize SPI once (keep open)
    spi = spidev.SpiDev()
    spi.open(0, 0)
    spi.max_speed_hz = 8_000_000
    spi.mode = 3

    # Initialize camera once, keep running
    picam2 = Picamera2()
    picam2.options["quality"] = JPEG_QUALITY
    picam2.configure(picam2.create_still_configuration(main={"size": (640, 480)}))
    picam2.start()
    time.sleep(1)  # One-time warmup

    counter = 1
    while True:
        print(f"\n=== Round {counter} ===")
        t_round = time.monotonic()

        img_data = capture_jpeg()
        send_image(img_data)

        total = time.monotonic() - t_round
        print(f"Total round time: {total * 1000:.0f}ms")

        counter += 1
# End main


if __name__ == "__main__":
    main()
