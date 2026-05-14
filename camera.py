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

# Ready pin from nRF (active high = ready for new image)
READY_PIN = 25  # GPIO25 (physical pin 22)

CHUNK_SIZE = 4096
MIN_DATA_SIZE = 8192
MAX_DATA_SIZE = 16384
JPEG_QUALITY = 60


def cleanup(signum=None, frame=None):
    global picam2, spi
    print("Cleaning up...")

    GPIO.cleanup()

    if picam2:
        try:
            picam2.stop()
        except:
            pass
        picam2.close()

    sys.exit(0)
# End function


def compress_image(img):
    """Compress JPEG image to desired size. Returns byte array"""
    global JPEG_QUALITY
    data = b"\x00"

    data_in_range = False
    max_retries = 5

    while not data_in_range and max_retries > 0:
        max_retries -= 1
        ret, jpeg = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        data = jpeg.tobytes()

        if len(data) > MAX_DATA_SIZE: # Image too big, reduce JPEG_QUALITY
            JPEG_QUALITY = max(JPEG_QUALITY - 10, 0)
        elif len(data) < MIN_DATA_SIZE: # Image too small, increase JPEG_QUALITY
            JPEG_QUALITY = min(JPEG_QUALITY + 10, 100)

        data_in_range = MIN_DATA_SIZE < len(data) < MAX_DATA_SIZE

    return data
# End function


def capture_jpeg():
    """Capture JPEG using array capture + cv2 encode (faster than capture_file)."""
    global picam2

    t0 = time.monotonic()
    array = picam2.capture_array()
    t_capture = time.monotonic()

    # picamera2 returns RGB, cv2 expects BGR
    bgr = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
    data = compress_image(bgr)

    t_encode = time.monotonic()

    print(f"Captured {len(data)} bytes "
          f"(capture: {(t_capture - t0) * 1000:.0f}ms, "
          f"encode: {(t_encode - t_capture) * 1000:.0f}ms)")
    return data
# End function


def main():
    global picam2

    # Initialize camera once, keep running
    picam2 = Picamera2()
    picam2.options["quality"] = JPEG_QUALITY
    picam2.configure(picam2.create_still_configuration(main={"size": (640, 480)}))
    picam2.start()
    time.sleep(1)  # One-time warmup

    counter = 1
    print(f"\n=== Round {counter} ===")
    t_round = time.monotonic()

    img_data = capture_jpeg()
    jpeg_as_np = np.frombuffer(img_data, dtype=np.uint8)
    img = cv2.imdecode(jpeg_as_np, flags=1)
    cv2.imwrite("test.jpg", img)

    total = time.monotonic() - t_round
    print(f"Total round time: {total * 1000:.0f}ms")

    counter += 1
# End main


if __name__ == "__main__":
    main()
