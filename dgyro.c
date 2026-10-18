// Directional gyro: integrates the Bosch BMI282 yaw rate into a settable heading.
//
// Gyro is the AppleSPUHIDDevice at HID page 0xFF00 usage 9 (AOP endpoint "gyro").
// Streaming is off until SensorPropertyReportingState/PowerState are set on its
// AppleSPUHIDDriver. Input report (22 bytes):
//   0..3   u32 sample counter (+8 per sample)
//   6..17  i32 x, y, z rate, deg/s * 65536
//   18..21 i32 temperature, degC * 65536
//
// Usage: dgyro [-a x|y|z] [-s 1|-1] [-c secs] [-l]
//   -a  axis to integrate (default z)
//   -s  sign; +1 means positive rate = heading increases (default -1: CCW-positive
//       gyro to CW-positive compass heading)
//   -c  bias calibration time in seconds (default 3)
//   -l  log mode: CSV on stdout, no interactive display
// Interactive commands (type then Enter): <number> set heading, c recalibrate,
// r reverse direction, l level (zero x/y angles), q quit

#include <IOKit/IOKitLib.h>
#include <IOKit/hid/IOHIDManager.h>
#include <dispatch/dispatch.h>
#include <libproc.h>
#include <mach/mach_time.h>
#include <math.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define SCALE 65536.0

static mach_timebase_info_data_t tb;
static int axis = 2, logmode;
static double sign = -1, cal_secs = 3;

static double heading, bias[3], last_t, temp_c, rate_dps;
static double angle[3];  // raw integrated angle per axis since start (log mode)
static int calibrating;
static double cal_sum[3], cal_sq[3], cal_start;
static long cal_n, samples;

static double now(void) { return (double)mach_absolute_time() * tb.numer / tb.denom / 1e9; }

static double wrap(double h) { h = fmod(h, 360); return h < 0 ? h + 360 : h; }

static void set_driver_props(int on) {
  io_iterator_t it;
  if (IOServiceGetMatchingServices(kIOMainPortDefault, IOServiceMatching("AppleSPUHIDDriver"), &it)) return;
  io_service_t s;
  while ((s = IOIteratorNext(it))) {
    int usage = 0, page = 0;
    CFNumberRef u = IORegistryEntryCreateCFProperty(s, CFSTR("PrimaryUsage"), 0, 0);
    CFNumberRef p = IORegistryEntryCreateCFProperty(s, CFSTR("PrimaryUsagePage"), 0, 0);
    if (u) { CFNumberGetValue(u, kCFNumberIntType, &usage); CFRelease(u); }
    if (p) { CFNumberGetValue(p, kCFNumberIntType, &page); CFRelease(p); }
    if (page == 0xff00 && usage == 9) {
      int interval = on ? 10000 : 0;  // us; 0 is what actually stops the stream
      CFNumberRef v = CFNumberCreate(0, kCFNumberIntType, &on), iv = CFNumberCreate(0, kCFNumberIntType, &interval);
      IORegistryEntrySetCFProperty(s, CFSTR("SensorPropertyReportingState"), v);
      IORegistryEntrySetCFProperty(s, CFSTR("SensorPropertyPowerState"), v);
      IORegistryEntrySetCFProperty(s, CFSTR("ReportInterval"), iv);
      CFRelease(v); CFRelease(iv);
    }
    IOObjectRelease(s);
  }
  IOObjectRelease(it);
}

// Streaming is a global driver setting, so only turn it off if no other dgyro is using it
static int others_running(void) {
  pid_t pids[4096];
  int n = proc_listallpids(pids, sizeof pids), me = getpid();
  for (int i = 0; i < n; i++) {
    char name[64];
    if (pids[i] != me && proc_name(pids[i], name, sizeof name) > 0 && !strcmp(name, "dgyro")) return 1;
  }
  return 0;
}

static void shutdown_gyro(void) {
  if (!others_running()) set_driver_props(0);
}

static void start_cal(void) {
  calibrating = 1; cal_n = 0; cal_start = now();
  memset(cal_sum, 0, sizeof cal_sum); memset(cal_sq, 0, sizeof cal_sq);
  fprintf(stderr, "\ncalibrating bias, keep still for %.0f s...\n", cal_secs);
}

static void finish_cal(void) {
  double sd[3];
  for (int i = 0; i < 3; i++) {
    bias[i] = cal_sum[i] / cal_n;
    sd[i] = sqrt(fmax(0, cal_sq[i] / cal_n - bias[i] * bias[i]));
  }
  calibrating = 0;
  fprintf(stderr, "bias x %+.4f y %+.4f z %+.4f dps  (noise sd %.3f %.3f %.3f)%s\n",
          bias[0], bias[1], bias[2], sd[0], sd[1], sd[2],
          sd[axis] > 0.2 ? "  WARNING: moved during calibration, press c to redo" : "");
}

static void report_cb(void *ctx, IOReturn r, void *sender, IOHIDReportType type, uint32_t id, uint8_t *b, CFIndex len) {
  if (len < 22) return;
  int32_t raw[4];
  memcpy(raw, b + 6, 16);
  double t = now(), w[3];
  for (int i = 0; i < 3; i++) w[i] = raw[i] / SCALE;
  temp_c = raw[3] / SCALE;
  samples++;

  if (calibrating) {
    for (int i = 0; i < 3; i++) { cal_sum[i] += w[i]; cal_sq[i] += w[i] * w[i]; }
    cal_n++;
    if (t - cal_start >= cal_secs) finish_cal();
    last_t = t;
    return;
  }

  double dt = last_t ? t - last_t : 0;
  if (dt > 0.1) dt = 0.01;  // gap (sleep, stall): don't integrate garbage
  last_t = t;

  rate_dps = sign * (w[axis] - bias[axis]);
  heading = wrap(heading + rate_dps * dt);
  for (int i = 0; i < 3; i++) angle[i] += (w[i] - bias[i]) * dt;

  if (logmode)
    printf("%.4f,%.3f,%.4f,%.3f,%.3f,%.3f,%.2f\n", t, heading, rate_dps, angle[0], angle[1], angle[2], temp_c);
}

static void draw(void) {
  if (logmode || calibrating) return;
  static const char *pts[] = {"N", "NE", "E", "SE", "S", "SW", "W", "NW"};
  fprintf(stderr, "\r\033[K HDG %6.1f° %-2s   rate %+7.2f°/s   temp %4.1f°C   > ",
          heading, pts[(int)((heading + 22.5) / 45) % 8], rate_dps, temp_c);
}

static void handle_line(char *line) {
  while (*line == ' ') line++;
  line[strcspn(line, "\r\n")] = 0;
  if (!*line) return;
  if (line[0] == 'q') { shutdown_gyro(); exit(0); }
  if (line[0] == 'c') { start_cal(); return; }
  if (line[0] == 'r') { sign = -sign; fprintf(stderr, "direction reversed (sign %+.0f)\n", sign); return; }
  if (line[0] == 'l') { angle[0] = angle[1] = 0; fprintf(stderr, "levelled: x and y angles zeroed\n"); return; }
  char *end;
  double h = strtod(line, &end);
  if (end != line) { heading = wrap(h); fprintf(stderr, "heading set to %.1f°\n", heading); }
  else fprintf(stderr, "commands: <degrees> set heading, c recalibrate, r reverse, l level, q quit\n");
}

static void on_signal(int sig) { shutdown_gyro(); _exit(0); }

int main(int argc, char **argv) {
  int opt;
  while ((opt = getopt(argc, argv, "a:s:c:l")) != -1) {
    if (opt == 'a') axis = optarg[0] - 'x';
    else if (opt == 's') sign = atof(optarg) < 0 ? -1 : 1;
    else if (opt == 'c') cal_secs = atof(optarg);
    else if (opt == 'l') logmode = 1;
    else { fprintf(stderr, "usage: dgyro [-a x|y|z] [-s 1|-1] [-c secs] [-l]\n"); return 2; }
  }
  if (axis < 0 || axis > 2) { fprintf(stderr, "axis must be x, y or z\n"); return 2; }
  mach_timebase_info(&tb);
  setvbuf(stdout, 0, _IOLBF, 0);

  set_driver_props(1);
  signal(SIGINT, on_signal);
  signal(SIGTERM, on_signal);
  signal(SIGHUP, on_signal);

  IOHIDManagerRef m = IOHIDManagerCreate(kCFAllocatorDefault, 0);
  int page = 0xff00, usage = 9;
  CFNumberRef p = CFNumberCreate(0, kCFNumberIntType, &page), u = CFNumberCreate(0, kCFNumberIntType, &usage);
  const void *k[] = {CFSTR(kIOHIDPrimaryUsagePageKey), CFSTR(kIOHIDPrimaryUsageKey)}, *v[] = {p, u};
  IOHIDManagerSetDeviceMatching(m, CFDictionaryCreate(0, k, v, 2, &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks));
  IOHIDManagerOpen(m, 0);
  CFSetRef set = IOHIDManagerCopyDevices(m);
  if (!set || CFSetGetCount(set) < 1) { fprintf(stderr, "gyro not found\n"); return 1; }
  IOHIDDeviceRef dev;
  CFSetGetValues(set, (const void **)&dev);
  static uint8_t buf[64];
  IOHIDDeviceRegisterInputReportCallback(dev, buf, sizeof buf, report_cb, 0);
  IOHIDDeviceScheduleWithRunLoop(dev, CFRunLoopGetCurrent(), kCFRunLoopDefaultMode);

  if (logmode) printf("t,heading,rate_dps,ang_x,ang_y,ang_z,temp_c\n");
  start_cal();

  dispatch_source_t in = dispatch_source_create(DISPATCH_SOURCE_TYPE_READ, STDIN_FILENO, 0, dispatch_get_main_queue());
  dispatch_source_set_event_handler(in, ^{
    char line[128];
    if (fgets(line, sizeof line, stdin)) handle_line(line);
    else dispatch_source_cancel(in);  // stdin closed: keep running
  });
  dispatch_resume(in);

  dispatch_source_t ui = dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER, 0, 0, dispatch_get_main_queue());
  dispatch_source_set_timer(ui, DISPATCH_TIME_NOW, NSEC_PER_SEC / 10, NSEC_PER_SEC / 50);
  dispatch_source_set_event_handler(ui, ^{ draw(); });
  dispatch_resume(ui);

  CFRunLoopRun();
}
