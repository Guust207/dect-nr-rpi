# Imports
import time
import os
import io
import numpy as np
import cv2 as cv
from picamera2 import Picamera2, Preview
import spidev

def send_chunks(data, chunk_size=4096):
	# Chunk setup
	no_chunks = (len(data) + chunk_size - 1) // chunk_size
	print(f"\nSending {len(data)} bytes in {no_chunks} chunks")
	
	for i in range(no_chunks):
		# Create chunk
		chunk_start = i * chunk_size
		chunk_end = min(chunk_start + chunk_size, len(data))
		chunk = bytearray(data[chunk_start:chunk_end])
		
		# Show what we're sending
		no_first_bytes = 16
		if len(chunk) < no_first_bytes:
			no_first_bytes = len(chunk)
			
		first_bytes = ' '.join(f'{b:02X}' for b in chunk[:no_first_bytes])
		print(f"Chunk {i+1}/{no_chunks} (bytes {chunk_start}-{chunk_end})")
		print(f"  First {no_first_bytes} bytes: {first_bytes}")
		
		# SPI setup
		spi = spidev.SpiDev()
		spi.open(0, 0)
		spi.max_speed_hz = 8_000_000
		spi.mode = 3
		spi.bits_per_word = 8
		
		# Send chunk
		spi.xfer3(list(chunk))
		
		# Close SPI and wait
		spi.close()
		time.sleep(0.5)
		
	print("Transfer complete!") 

# Camera object init and preview start
picam2 = Picamera2()
picam2.options["quality"] = 40
capture_config = picam2.create_still_configuration({"format": "YUV420"})
picam2.start(show_preview=True)
time.sleep(1)

# Capture image data
img_data = io.BytesIO()
picam2.capture_file(img_data, format="jpeg")

# Get image bytes
tx_data = img_data.getbuffer().tobytes()
tx_size = len(tx_data)
print(f"Image data size in bytes: {tx_size}")

# Display the image
picam2.stop_preview()
img_arr = np.frombuffer(img_data.getbuffer().tobytes(), dtype=np.uint8)
img = cv.imdecode(img_arr, cv.IMREAD_COLOR)
cv.imshow("Image", img)
cv.waitKey(0)
cv.destroyAllWindows()
	
# Main loop
counter = 1
while True:
	print(f"\n=== Round {counter} ===")
	CHUNK_SIZE = 4096	
	send_chunks(tx_data, CHUNK_SIZE)
	counter += 1
	time.sleep(5)
