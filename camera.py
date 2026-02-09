# Imports
import time
import os
import io

import cv2 as cv
from picamera2 import Picamera2, Preview

# Camera object init and preview start
picam2 = Picamera2()
picam2.options["quality"] = 45
picam2.options["compress_level"] = 5
capture_config = picam2.create_still_configuration()
picam2.start(show_preview=True)
time.sleep(1)

# Capture image data
# JPEG
jpeg_data = io.BytesIO()
picam2.capture_file(jpeg_data, format="jpeg")
time.sleep(1)

# PNG
png_data = io.BytesIO()
picam2.switch_mode_and_capture_file(capture_config, png_data, format="png")
time.sleep(1)

# BMP
bmp_data = io.BytesIO()
picam2.switch_mode_and_capture_file(capture_config, bmp_data, format="bmp")
time.sleep(1)

# Print data size
print(f"JPEG: {jpeg_data.getbuffer().nbytes} B")
print(f"PNG: {png_data.getbuffer().nbytes} B")
print(f"BMP: {bmp_data.getbuffer().nbytes} B")

# Display the image
#cv.imshow("Image", jpeg_data)
#cv.waitKey(0)
#cv.destroyAllWindows()

