import time
import io
import fcntl
import spidev
from picamera2 import Picamera2

def main():
	# Lock the service
	lock = open("/tmp/camera_spi.lock", "w")
	fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
	
	# Setup camera
	cam = Picamera2()
	cam.configure(cam.create_still_configuration())
	cam.start()
	time.sleep(1)
	
	# Capture image data
	img_data = io.BytesIO()
	cam.capture_file(img_data, format="jpeg")
	cam.stop()
	
	# SPI setup
	spi = spidev.SpiDev()
	spi.open(0, 0)
	
	spi.max_speed_hz = 1_000_000
	spi.mode = 0
	spi.bits_per_word = 8
	
	# Transfer on SPI
	tx_data = img_data.getbuffer().tobytes()
	spi.xfer3(tx_data)
	spi.close()
	
if __name__ == "main":
	main()
