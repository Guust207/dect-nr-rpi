import spidev
import time

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1000000
spi.mode = 3

print("Starting SPI test...")

while True:
	data = [0xAA, 0x55, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06]
	print(f"Sending: {[hex(x) for x in data]}")
	response = spi.xfer2(data)
	print(f"Received: {[hex(x) for x in response]}")
	time.sleep(1)
