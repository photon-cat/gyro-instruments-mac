// Polls the MagAlpha ma781 hinge sensor (HID page 0x20 usage 0x8A) and prints
// CSV: unix_time, angle_deg (report 1), angle_centideg (report 7)
#include <IOKit/hid/IOHIDManager.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/time.h>
#include <unistd.h>

static int get(IOHIDDeviceRef d, int id, uint8_t *buf, CFIndex *len) {
  return IOHIDDeviceGetReport(d, kIOHIDReportTypeInput, id, buf, len);
}

int main(int argc, char **argv) {
  int hz = argc > 1 ? atoi(argv[1]) : 50;
  IOHIDManagerRef m = IOHIDManagerCreate(kCFAllocatorDefault, 0);
  int page = 0x20, usage = 0x8a;
  CFNumberRef p = CFNumberCreate(0, kCFNumberIntType, &page), u = CFNumberCreate(0, kCFNumberIntType, &usage);
  const void *k[] = {CFSTR(kIOHIDPrimaryUsagePageKey), CFSTR(kIOHIDPrimaryUsageKey)}, *v[] = {p, u};
  IOHIDManagerSetDeviceMatching(m, CFDictionaryCreate(0, k, v, 2, &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks));
  IOHIDManagerOpen(m, 0);
  CFSetRef s = IOHIDManagerCopyDevices(m);
  if (!s || CFSetGetCount(s) < 1) { fprintf(stderr, "lid angle sensor not found\n"); return 1; }
  IOHIDDeviceRef d; CFSetGetValues(s, (const void **)&d);
  IOHIDDeviceOpen(d, 0);
  printf("t,angle_deg,angle_cdeg\n");
  for (;;) {
    uint8_t b1[8] = {0}, b7[8] = {0}; CFIndex l1 = sizeof b1, l7 = sizeof b7;
    struct timeval tv; gettimeofday(&tv, 0);
    if (get(d, 1, b1, &l1) == kIOReturnSuccess && get(d, 7, b7, &l7) == kIOReturnSuccess)
      printf("%.3f,%u,%u\n", tv.tv_sec + tv.tv_usec / 1e6, b1[1] | (b1[2] & 1) << 8, b7[1] | b7[2] << 8);
    fflush(stdout);
    usleep(1000000 / hz);
  }
}
