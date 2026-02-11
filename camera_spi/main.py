# Imports
import time
import os
import io
import signal
import numpy as np
from picamera2 import Picamera2
import spidev

# Camera global variable
picam2 = Picamera2()

def capture_new_jpeg():
	# Start camera and warm up
	picam2.start(show_preview=True)
	time.sleep(2)
	
	# Capture image data
	img_data = io.BytesIO()
	picam2.capture_file(img_data, format="jpeg")

	# Get image bytes
	img_data = img_data.getbuffer().tobytes()

	# Return image data
	picam2.stop_preview()
	return img_data
# End of function


def send_chunks(data, chunk_size=4096, max_data_size=32768):
	# Check size
	data_size = len(data)
	if data_size > max_data_size:
		return # Do not send data above threshold
	
	# Chunk setup
	data_size = len(data)
	no_chunks = (data_size + chunk_size - 1) // chunk_size
	
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
	# End of loop
	
	return
# End of function


def cleanup(signum, frame):
	if picam2:
		picam2.stop()
		picam2.close()
	sys.exit(0)
# End of function

def main():
	# Camera object init and preview start
	picam2.options["quality"] = 45
	capture_config = picam2.create_still_configuration({"format": "YUV420"})

	# Capture image using camera
	tx_data = capture_new_jpeg()
	
	# Send image as data through SPI
	CHUNK_SIZE = 4096
	MAX_DATA_SIZE = 32768	
	send_chunks(tx_data, CHUNK_SIZE, MAX_DATA_SIZE)
	
	# SIGTERM handling
	signal.signal(signal.SIGTERM, cleanup)
	signal.signal(signal.SIGINT, cleanup)
# End main

if __name__ == "__main__":
	main()
