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
MAX_DATA_SIZE = 16384
JPEG_QUALITY = 60
MAX_COMPRESS_ATTEMPTS = 7


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
    """Wait for ready pin to be HIGH (nRF armed for a new chunk)."""
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
        print(f"nRF ready after {waited * 1000:.0f}ms")
    return True
# End function


def wait_for_chunk_ack(timeout=2.0):
    """After sending a non-final chunk, wait for the nRF to lower then raise
    the ready pin — confirming it has processed the chunk and re-armed
    spi_transceive for the next one."""
    start = time.monotonic()

    # Wait for LOW: nRF signals it received the chunk and is processing
    while GPIO.input(READY_PIN) == 1:
        if time.monotonic() - start > timeout:
            print("WARNING: Chunk ack timeout waiting for LOW")
            return False
        time.sleep(0.0001)

    # Wait for HIGH: nRF has re-armed spi_transceive and is ready for next chunk
    while GPIO.input(READY_PIN) == 0:
        if time.monotonic() - start > timeout:
            print("WARNING: Chunk ack timeout waiting for HIGH")
            return False
        time.sleep(0.0001)

    return True
# End function


def compress_image(img):
    """Compress JPEG image to desired size. Returns byte array"""
    global JPEG_QUALITY
    compress_quality = JPEG_QUALITY
    data = b"\x00"
    data_in_range = False
    max_retries = MAX_COMPRESS_ATTEMPTS

    while not data_in_range and max_retries > 0:
        max_retries -= 1
        ret, jpeg = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, compress_quality])
        data = jpeg.tobytes()

        if len(data) > MAX_DATA_SIZE: # Image too big, reduce compress_quality
            compress_quality = max(compress_quality - 10, 0)

        data_in_range = len(data) < MAX_DATA_SIZE

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


def send_chunks(data):
    """Send image data over SPI in chunks with per-chunk flow control.

       Protocol:
         - Before the first chunk: wait for ready HIGH (nRF armed).
         - After each non-final chunk: wait for ready LOW then HIGH (nRF processed
           chunk and re-armed spi_transceive). This eliminates the race where the
           Pi sends the next chunk before the slave has re-armed.
         - After the final chunk: no wait — nRF will keep ready LOW until the
           image propagates through the pipeline and the flag is cleared.
   """
    global spi

    # Wait for nRF to be ready
    if not wait_for_ready():
        print("nRF not ready, skipping this image")
        return

    data_size = len(data)
    no_chunks = (data_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"Sending {data_size} bytes in {no_chunks} chunks")

    t_start = time.monotonic()

    for i in range(no_chunks):
        chunk_start = i * CHUNK_SIZE
        chunk_end = min(chunk_start + CHUNK_SIZE, data_size)
        chunk = data[chunk_start:chunk_end]

        spi.xfer3(chunk)

        # Wait for per-chunk acknowledgement on every chunk except the last.
        # After the last chunk the nRF finds the JPEG EOI and keeps ready LOW
        # until the image is consumed; the next send_chunks call handles that
        # via wait_for_ready at the top.
        if i < no_chunks - 1:
            if not wait_for_chunk_ack():
                print(f"WARNING: Chunk {i} ack failed, aborting transfer")
                return

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
