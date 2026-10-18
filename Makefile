libimu.dylib: imu.c
	clang -O2 -Wall -dynamiclib -framework IOKit -framework CoreFoundation -o $@ $<

run: libimu.dylib
	uv run compass.py

clean:
	rm -f libimu.dylib

.PHONY: run clean
