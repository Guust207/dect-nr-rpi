# Imports
import time
import os
import io

import numpy as np
import cv2 as cv
from picamera2 import Picamera2, Preview
import spidev

# Camera object init and preview start
picam2 = Picamera2()
capture_config = picam2.create_still_configuration()
picam2.start(show_preview=True)
time.sleep(1)

# Capture image data
img_data = io.BytesIO()
picam2.capture_file(img_data, format="jpeg")

# Print data size
print(f"JPEG: {img_data.getbuffer().nbytes} B")

# Display the image
img_arr = np.frombuffer(img_data.getbuffer().tobytes(), dtype=np.uint8)
img = cv.imdecode(img_arr, cv.IMREAD_COLOR)
cv.imshow("Image", img)
cv.waitKey(0)
cv.destroyAllWindows()

# SPI setup
spi = spidev.SpiDev()
tx_data = img_data.getbuffer().tobytes()
while True:
	spi.open(0, 0)

	spi.max_speed_hz = 1_000_000
	spi.mode = 0
	spi.bits_per_word = 8

	# SPI transfer
	print(f"Tx data: {tx_data[0]}")
	rx_data = spi.xfer3(tx_data)
	print(f"Rx data: {rx_data[0]}")
	
	# Close and wait
	spi.close()
	time.sleep(5)
