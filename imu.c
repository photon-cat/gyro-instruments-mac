// imu.c: stream the MacBook's Bosch BMI282 gyro and accelerometer (no root needed).
//
// Both live on the AOP sensor hub as vendor HID devices (page 0xFF00; usage 9 =
// gyro, 3 = accel). They stay silent until their AppleSPUHIDDriver gets
// SensorPropertyReportingState/PowerState = 1 and a ReportInterval; setting
// ReportInterval back to 0 is what stops them. Each 22-byte report holds:
//   0..3 u32 sample counter, 6..17 i32 x/y/z, 18..21 i32 temperature,
// all fixed point * 65536 (deg/s for the gyro, g for the accel, degC).
//
// Python API (ctypes): imu_start(), imu_read(buf, max), imu_stop().

#include <IOKit/IOKitLib.h>
#include <IOKit/hid/IOHIDManager.h>
#include <mach/mach_time.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

enum { IMU_GYRO = 9, IMU_ACCEL = 3 };

typedef struct {
  double t;         // host time of arrival, seconds
  int32_t sensor;   // IMU_GYRO or IMU_ACCEL
  uint32_t seq;     // sensor's sample counter
  double x, y, z;   // deg/s or g
  double temp;      // degC
} imu_sample;

#define QUEUE 2048
static imu_sample queue[QUEUE];
static int head, count;
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_t thread;
static CFRunLoopRef loop;
static mach_timebase_info_data_t tb;

static void set_streaming(int usage, int interval_us) {
  io_iterator_t it;
  if (IOServiceGetMatchingServices(kIOMainPortDefault, IOServiceMatching("AppleSPUHIDDriver"), &it)) return;
  io_service_t s;
  while ((s = IOIteratorNext(it))) {
    int page = 0, u = 0, on = interval_us > 0;
    CFNumberRef n;
    if ((n = IORegistryEntryCreateCFProperty(s, CFSTR("PrimaryUsagePage"), 0, 0))) { CFNumberGetValue(n, kCFNumberIntType, &page); CFRelease(n); }
    if ((n = IORegistryEntryCreateCFProperty(s, CFSTR("PrimaryUsage"), 0, 0))) { CFNumberGetValue(n, kCFNumberIntType, &u); CFRelease(n); }
    if (page == 0xff00 && u == usage) {
      CFNumberRef v = CFNumberCreate(0, kCFNumberIntType, &on), iv = CFNumberCreate(0, kCFNumberIntType, &interval_us);
      IORegistryEntrySetCFProperty(s, CFSTR("SensorPropertyReportingState"), v);
      IORegistryEntrySetCFProperty(s, CFSTR("SensorPropertyPowerState"), v);
      IORegistryEntrySetCFProperty(s, CFSTR("ReportInterval"), iv);
      CFRelease(v); CFRelease(iv);
    }
    IOObjectRelease(s);
  }
  IOObjectRelease(it);
}

static void on_report(void *ctx, IOReturn r, void *sender, IOHIDReportType type, uint32_t id, uint8_t *b, CFIndex len) {
  if (len < 22) return;
  int32_t v[4];
  imu_sample s = {.t = (double)mach_absolute_time() * tb.numer / tb.denom / 1e9, .sensor = (int32_t)(intptr_t)ctx};
  memcpy(&s.seq, b, 4);
  memcpy(v, b + 6, 16);
  s.x = v[0] / 65536.0; s.y = v[1] / 65536.0; s.z = v[2] / 65536.0; s.temp = v[3] / 65536.0;
  pthread_mutex_lock(&lock);
  queue[(head + count) % QUEUE] = s;
  if (count < QUEUE) count++; else head = (head + 1) % QUEUE;  // full: drop oldest
  pthread_mutex_unlock(&lock);
}

static int listen(int usage) {
  int page = 0xff00;
  CFNumberRef p = CFNumberCreate(0, kCFNumberIntType, &page), u = CFNumberCreate(0, kCFNumberIntType, &usage);
  // Transport matters: the internal keyboard/trackpad also has a 0xFF00/3 interface
  const void *k[] = {CFSTR(kIOHIDPrimaryUsagePageKey), CFSTR(kIOHIDPrimaryUsageKey), CFSTR(kIOHIDTransportKey)};
  const void *v[] = {p, u, CFSTR("SPU")};
  CFDictionaryRef match = CFDictionaryCreate(0, k, v, 3, &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
  IOHIDManagerRef manager = IOHIDManagerCreate(kCFAllocatorDefault, 0);
  IOHIDManagerSetDeviceMatching(manager, match);
  IOHIDManagerOpen(manager, 0);
  CFSetRef set = IOHIDManagerCopyDevices(manager);
  CFRelease(match); CFRelease(p); CFRelease(u);
  if (!set || CFSetGetCount(set) < 1) return -1;
  IOHIDDeviceRef dev;
  CFSetGetValues(set, (const void **)&dev);
  uint8_t *buf = calloc(64, 1);
  IOHIDDeviceRegisterInputReportCallback(dev, buf, 64, on_report, (void *)(intptr_t)usage);
  IOHIDDeviceScheduleWithRunLoop(dev, loop, kCFRunLoopDefaultMode);
  return 0;
}

static void *run(void *started) {
  loop = CFRunLoopGetCurrent();
  int err = listen(IMU_GYRO) || listen(IMU_ACCEL);
  *(int *)started = err ? -1 : 1;
  if (!err) CFRunLoopRun();
  return 0;
}

// Start the gyro at 100 Hz and the accel at 200 Hz (asked for 100 Hz, the accel often stays silent).
int imu_start(void) {
  volatile int started = 0;
  mach_timebase_info(&tb);
  set_streaming(IMU_GYRO, 10000);
  set_streaming(IMU_ACCEL, 5000);
  pthread_create(&thread, 0, run, (void *)&started);
  while (!started) usleep(1000);
  return started > 0 ? 0 : -1;
}

// Copy up to max queued samples (oldest first) into out; returns how many.
int imu_read(imu_sample *out, int max) {
  pthread_mutex_lock(&lock);
  int n = count < max ? count : max;
  for (int i = 0; i < n; i++) out[i] = queue[(head + i) % QUEUE];
  head = (head + n) % QUEUE;
  count -= n;
  pthread_mutex_unlock(&lock);
  return n;
}

void imu_stop(void) {
  set_streaming(IMU_GYRO, 0);
  set_streaming(IMU_ACCEL, 0);
  if (loop) { CFRunLoopStop(loop); pthread_join(thread, 0); loop = 0; }
}
