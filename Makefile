CFLAGS = -O2 -Wall
FRAMEWORKS = -framework IOKit -framework CoreFoundation

all: dgyro lidlog

dgyro: dgyro.c
	clang $(CFLAGS) $(FRAMEWORKS) -o $@ $<

lidlog: lidlog.c
	clang $(CFLAGS) $(FRAMEWORKS) -o $@ $<

run: dgyro
	uv run compass.py

clean:
	rm -f dgyro lidlog

.PHONY: all run clean
