import time
import sys
import signal
import spidev
import cv2
import numpy as np
from picamera2 import Picamera2

picam2 = None
spi = None

def cleanup(signum=None, frame=None):
    print("Cleaning up...")
    if spi:
        spi.close()
    if picam2:
        try:
            picam2.stop()
        except:
            pass
        picam2.close()
    sys.exit(0)

signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)

# Initialize SPI once
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 8_000_000
spi.mode = 3

# Initialize camera once, keep running
picam2 = Picamera2()
picam2.configure(picam2.create_still_configuration(main={"size": (640, 480)}))
picam2.start()
time.sleep(1)  # One-time warmup

CHUNK_SIZE = 4096
MAX_DATA_SIZE = 32768
JPEG_QUALITY = 45

def capture_jpeg():
    t0 = time.monotonic()
    array = picam2.capture_array()
    t_capture = time.monotonic()

    # Convert RGB to BGR for cv2 (picamera2 returns RGB)
    bgr = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
    ret, jpeg = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    t_encode = time.monotonic()

    data = jpeg.tobytes()
    print(f"Captured {len(data)} bytes "
          f"(capture: {(t_capture-t0)*1000:.0f}ms, "
          f"encode: {(t_encode-t_capture)*1000:.0f}ms)")
    return data

def send_chunks(data):
    data_size = len(data)
    if data_size > MAX_DATA_SIZE:
        print(f"Image too large ({data_size} bytes), skipping")
        return

    no_chunks = (data_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"Sending {data_size} bytes in {no_chunks} chunks")

    t_start = time.monotonic()

    for i in range(no_chunks):
        chunk_start = i * CHUNK_SIZE
        chunk_end = min(chunk_start + CHUNK_SIZE, data_size)
        chunk = data[chunk_start:chunk_end]
        spi.xfer3(chunk)

    elapsed = time.monotonic() - t_start
    throughput = data_size / elapsed / 1024
    print(f"SPI transfer: {elapsed*1000:.0f}ms ({throughput:.1f} KB/s)")

counter = 1
while True:
    print(f"\n=== Round {counter} ===")
    t_round = time.monotonic()

    img_data = capture_jpeg()
    send_chunks(img_data)

    total = time.monotonic() - t_round
    print(f"Total round time: {total*1000:.0f}ms")

    counter += 1
