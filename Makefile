PORT ?= /dev/cu.usbmodem2113301
FILE ?= src/main.py
MICROPYTHON_DIR ?=
MICROPYTHON_BOARD ?= ESP32_GENERIC
MICROPYTHON_BOARD_VARIANT ?= SPIRAM
PYTHON ?= python3

## Flash MicroPython firmware via serial (erases all data first)
write-flash-micron-python:
	esptool --chip esp32 --port ${PORT} erase-flash
	esptool --chip esp32 --port ${PORT} write-flash 0x1000 bins/ESP32_GENERIC-SPIRAM-20260406-v1.28.0.bin

## Backup entire flash to backup.bin
backup-bin:
	esptool -p ${PORT} read-flash 0x0 0x400000 backup.bin

## Restore flash from origin.bin
restore-bin:
	esptool --chip esp32 --port ${PORT} write-flash 0x0000 backup.bin

## Reset the board via DTR
reboot:
	ampy --port ${PORT} reset

## Upload src/lib/* to /lib on device
put_lib:
	ampy --port ${PORT} put src/lib /lib

## Upload FILE to device root -- default src/main.py
put:
	ampy --port ${PORT} put $(FILE)

## Connect serial console -- exit with ctrl-a k
attach:
	echo "'ctrl-a k' to stop"
	sleep 2
	screen ${PORT} 115200

## Install required Python tools
install-deps:
	pip install esptool
	pip install adafruit-ampy

## List available targets with descriptions
help:
	@grep -B1 -E '^[a-zA-Z_-]+:' Makefile | grep -v '^--' | paste - - | sed 's/## //;s/\t/: /' | awk -F': ' '{printf "  \033[1m%-30s\033[0m %s\n", $$2, $$1}'

## Check that required tools are available
check-deps:
	@missing=""; \
	for cmd in esptool.py ampy screen; do \
		if ! command -v $$cmd >/dev/null 2>&1; then \
			missing="$$missing $$cmd"; \
		fi; \
	done; \
	if [ -n "$$missing" ]; then \
		echo "Missing:$$missing"; \
		exit 1; \
	else \
		echo "All dependencies satisfied."; \
	fi

.PHONY: build-c3d-firmware test-c3d

## Run C3D rasterizer and Python fallback tests on the host
test-c3d:
	$(PYTHON) native/c3d/tests/run_native_tests.py
	$(PYTHON) native/c3d/tests/test_python_fallback.py

## Build MicroPython v1.28.0 ESP32/SPIRAM firmware with the C3D renderer
build-c3d-firmware:
	@test -f "$(MICROPYTHON_DIR)/ports/esp32/Makefile" || { echo "Set MICROPYTHON_DIR to your MicroPython v1.28.0 source tree."; exit 2; }
	@command -v idf.py >/dev/null || { echo "Activate ESP-IDF v5.5.1 with export.sh first."; exit 2; }
	$(MAKE) -C "$(MICROPYTHON_DIR)/mpy-cross"
	$(MAKE) -C "$(MICROPYTHON_DIR)/ports/esp32" submodules BOARD=$(MICROPYTHON_BOARD) BOARD_VARIANT=$(MICROPYTHON_BOARD_VARIANT) USER_C_MODULES="$(CURDIR)/native/micropython.cmake"
	$(MAKE) -C "$(MICROPYTHON_DIR)/ports/esp32" BOARD=$(MICROPYTHON_BOARD) BOARD_VARIANT=$(MICROPYTHON_BOARD_VARIANT) USER_C_MODULES="$(CURDIR)/native/micropython.cmake"
