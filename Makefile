libimu.dylib: imu.c
	clang -O2 -Wall -dynamiclib -framework IOKit -framework CoreFoundation -o $@ $<

run: libimu.dylib
	uv run compass.py

# redraw assets/ after editing make_assets.py
assets:
	uv run make_assets.py

clean:
	rm -f libimu.dylib

.PHONY: run assets clean
