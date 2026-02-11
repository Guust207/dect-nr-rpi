import time
import os
import io
import numpy as np
import fcntl
import spidev
from picamera2 import Picamera2


def send_chunks(data, chunk_size=4096):
	# Chunk setup
	data_size = len(data)
	no_chunks = (data_size + chunk_size - 1) // chunk_size
	
	for i in range(no_chunks):
		# Create chunk
		chunk_start = i * chunk_size
		chunk_end = min(chunk_start + chunk_size, len(data))
		chunk = bytearray(data[chunk_start:chunk_end])
		
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
# End of function
	

def main():
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
	
	# Send data over SPI
	picam2.stop_preview()
	CHUNK_SIZE = 4096
	send_chunks(tx_data, CHUNK_SIZE)
# End of function
	
if __name__ == "main":
	main()
