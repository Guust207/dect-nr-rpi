# Imports
import time
import sys
import signal
import spidev
import cv2
import numpy as np
import RPi.GPIO as GPIO
from picamera2 import Picamera2

picam2 = None
spi = None

# Ready pin from nRF (active high = ready for new image)
READY_PIN = 25  # GPIO25 (physical pin 22)

CHUNK_SIZE = 4096
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


def send_chunks(data):
    """Send image data over SPI in chunks, with per-chunk ready handshake."""
    global spi

    data_size = len(data)
    if data_size > MAX_DATA_SIZE:
        print(f"Image too large ({data_size} bytes), skipping")
        return

    no_chunks = (data_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"Sending {data_size} bytes in {no_chunks} chunks")

    t_start = time.monotonic()

    for i in range(no_chunks):
        # Wait for nRF ready before EVERY chunk
        if not wait_for_ready():
            print(f"nRF not ready for chunk {i+1}/{no_chunks}, aborting")
            return

        chunk_start = i * CHUNK_SIZE
        chunk_end = min(chunk_start + CHUNK_SIZE, data_size)
        chunk = data[chunk_start:chunk_end]
        spi.xfer3(chunk)

    elapsed = time.monotonic() - t_start
    throughput = data_size / elapsed / 1024
    print(f"SPI transfer: {elapsed * 1000:.0f}ms ({throughput:.1f} KB/s)")
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
        send_chunks(img_data)

        total = time.monotonic() - t_round
        print(f"Total round time: {total * 1000:.0f}ms")

        counter += 1
# End main


if __name__ == "__main__":
    main()
