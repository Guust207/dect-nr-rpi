# Imports
import time
import os
import io
import numpy as np
from picamera2 import Picamera2, Preview
import spidev


def capture_new_jpeg(camera):
	# Start camera and warm up
	camera.start(show_preview=True)
	time.sleep(1)
	
	# Capture image data
	img_data = io.BytesIO()
	camera.capture_file(img_data, format="jpeg")

	# Get image bytes
	img_data = img_data.getbuffer().tobytes()

	# Return image data
	camera.stop_preview()
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
	# End of loop
		
	print("Transfer complete!")
	
	return
# End of function


def main():
	# Camera object init and preview start
	picam2 = Picamera2()
	picam2.options["quality"] = 45
	capture_config = picam2.create_still_configuration({"format": "YUV420"})

	# Capture image using camera
	tx_data = capture_new_jpeg(picam2)
	
	# Send image as data through SPI
	CHUNK_SIZE = 4096	
	send_chunks(tx_data, CHUNK_SIZE)
# End main

if __name__ == "__main__":
	main()
