# Imports
import time
import os
import io
import sys
import signal
import numpy as np
import cv2 as cv
from picamera2 import Picamera2
import spidev

picam2 = None
spi = None


def cleanup(signum=None, frame=None):
	global picam2, spi
	print("Cleaning up..")
	
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
	

def capture_new_jpeg():
	# Start camera and warm up
	global picam2
	picam2.start(show_preview=True)
	time.sleep(1)
	
	# Capture image data
	img_data = io.BytesIO()
	picam2.capture_file(img_data, format="jpeg")

	# Get image bytes
	img_data = img_data.getbuffer().tobytes()
	data_size = len(img_data)
	print(f"Image data size in bytes: {data_size}")

	# Display the image
	picam2.stop_preview()
	picam2.stop()
	img_arr = np.frombuffer(img_data, dtype=np.uint8)
	img = cv.imdecode(img_arr, cv.IMREAD_COLOR)
	cv.imshow("Image", img)
	time.sleep(2)
	cv.destroyAllWindows()
	
	return img_data
# End of function


def send_chunks(data, chunk_size=4096, max_data_size=32768):
	global spi
	
	# Check size
	data_size = len(data)
	if data_size > max_data_size:
		print("Transfer aborted. Too large data.")
		return # Do not send data above threshold
	
	# Chunk setup
	data_size = len(data)
	no_chunks = (data_size + chunk_size - 1) // chunk_size
	print(f"\nSending {len(data)} bytes in {no_chunks} chunks")
	
	# SPI setup
	spi = spidev.SpiDev()
	spi.open(0, 0)
	spi.max_speed_hz = 8_000_000
	spi.mode = 3
	
	time.sleep(0.05)
	
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
		
		
		# Send chunk
		spi.xfer3(list(chunk))
	# End of loop
	
	spi.close()
	spi = None
		
	print("Transfer complete!")
	
	return
# End of function

	
# Main loop
# Signal setup
signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)

# Camera object init and preview start
picam2 = Picamera2()
picam2.options["quality"] = 45
capture_config = picam2.create_still_configuration({"format": "YUV420"})

counter = 1
while True:
	# Capture image using camera
	tx_data = capture_new_jpeg()
	
	print(f"\n=== Round {counter} ===")
	
	# Send image as data through SPI
	CHUNK_SIZE = 4096
	MAX_DATA_SIZE = 32768
	send_chunks(tx_data, CHUNK_SIZE, MAX_DATA_SIZE)
	
	counter += 1
	time.sleep(5)
