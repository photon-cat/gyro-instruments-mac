CFLAGS = -O2 -Wall
FRAMEWORKS = -framework IOKit -framework CoreFoundation

all: dgyro

dgyro: dgyro.c
	clang $(CFLAGS) $(FRAMEWORKS) -o $@ $<

run: dgyro
	uv run compass.py

clean:
	rm -f dgyro

.PHONY: all run clean
