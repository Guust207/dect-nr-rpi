import time
import spidev

spi = spidev.SpiDev()

spi.open(0, 0)

spi.max_speed_hz = 500_000
spi.mode = 0
spi.bits_per_word = 8

tx_data = [0x01, 0x02, 0x03]
rx_data = spi.xfer2(tx_data)

print(f"Sent:		{tx_data}")
print(f"Received:	{rx_data}")

spi.close()


GNARRR

Wolf
