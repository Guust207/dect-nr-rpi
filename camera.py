import time
import io
import sys
import signal
import spidev
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
picam2.options["quality"] = 45
picam2.start()
time.sleep(1)  # One-time warmup

CHUNK_SIZE = 4096
MAX_DATA_SIZE = 32768
INTER_CHUNK_DELAY = 0.005  # 5ms — tune this down if stable

def capture_jpeg():
    buf = io.BytesIO()
    picam2.capture_file(buf, format="jpeg")
    data = buf.getvalue()
    print(f"Captured {len(data)} bytes")
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

        spi.xfer3(chunk)  # bytes/bytearray works directly, no list conversion needed
        
        if i < no_chunks - 1:
            time.sleep(INTER_CHUNK_DELAY)

    elapsed = time.monotonic() - t_start
    throughput = data_size / elapsed / 1024
    print(f"Transfer complete: {elapsed*1000:.0f}ms ({throughput:.1f} KB/s)")

counter = 1
while True:
    print(f"\n=== Round {counter} ===")
    
    img_data = capture_jpeg()
    send_chunks(img_data)
    
    counter += 1
    time.sleep(5)  # Interval between captures — adjust as needed
