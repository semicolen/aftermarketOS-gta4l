"""Report GPS readiness and fix validity without printing coordinates or NMEA."""
import dbus
from datetime import datetime, timedelta, timezone
import json
import math

bus = dbus.SystemBus()
manager = bus.get_object("org.freedesktop.ModemManager1", "/org/freedesktop/ModemManager1")
objects = dbus.Interface(manager, "org.freedesktop.DBus.ObjectManager").GetManagedObjects()
interface = "org.freedesktop.ModemManager1.Modem.Location"
result = []
for path, interfaces in objects.items():
    if interface not in interfaces:
        continue
    properties = interfaces[interface]
    enabled = int(properties["Enabled"])
    obj = bus.get_object("org.freedesktop.ModemManager1", path)
    locations = dbus.Interface(obj, interface).GetLocation(timeout=10)
    raw = locations.get(2, {})
    nmea = str(locations.get(4, ""))
    raw_fix = all(name in raw and math.isfinite(float(raw[name])) for name in ("latitude", "longitude"))
    nmea_fix = False
    fix_age = None
    satellites = None
    hdop = None
    fix_sentence = None
    sentence_types = []
    valid_checksums = 0
    for line in nmea.splitlines():
        body, marker, checksum = line.partition("*")
        expected = 0
        for char in body.removeprefix("$"):
            expected ^= ord(char)
        try:
            checksum_valid = bool(marker) and int(checksum[:2], 16) == expected
        except ValueError:
            checksum_valid = False
        valid_checksums += int(checksum_valid)
        fields = body.split(",")
        sentence_types.append(fields[0].removeprefix("$")[-3:])
        if len(fields) > 6 and fields[0].endswith("GGA") and fields[6].isdigit():
            nmea_fix |= int(fields[6]) > 0
            if int(fields[6]) > 0 and checksum_valid and len(fields) > 8:
                now = datetime.now(timezone.utc)
                try:
                    seconds = float(fields[1][4:])
                    stamp = now.replace(hour=int(fields[1][:2]), minute=int(fields[1][2:4]),
                                        second=0, microsecond=0) + timedelta(seconds=seconds)
                    stamp = min((stamp - timedelta(days=1), stamp, stamp + timedelta(days=1)),
                                key=lambda value: abs((now - value).total_seconds()))
                    fix_age = round((now - stamp).total_seconds(), 2)
                    fix_sentence = "GGA"
                    satellites = int(fields[7])
                    hdop = float(fields[8])
                except ValueError:
                    pass
        if len(fields) > 2 and fields[0].endswith("RMC"):
            nmea_fix |= fields[2] == "A"
            if fields[2] == "A" and checksum_valid and len(fields) > 9:
                try:
                    clock, _, fraction = fields[1].partition(".")
                    stamp = datetime.strptime(fields[9] + clock, "%d%m%y%H%M%S").replace(tzinfo=timezone.utc)
                    if fraction:
                        stamp += timedelta(seconds=float("0." + fraction))
                    age = round((datetime.now(timezone.utc) - stamp).total_seconds(), 2)
                    if fix_age is None or abs(age) < abs(fix_age):
                        fix_age = age
                        fix_sentence = "RMC"
                except ValueError:
                    pass
    result.append({"modem": str(path), "gps_client_enabled": bool(enabled & 6),
                   "gps_raw_fix": raw_fix, "gps_nmea_valid_fix": nmea_fix,
                   "nmea_available": bool(nmea), "valid_nmea_checksums": valid_checksums,
                   "sentence_types": sorted(set(sentence_types)), "fix_sentence": fix_sentence,
                   "fix_age_seconds": fix_age, "satellites_in_use": satellites,
                   "horizontal_dilution": hdop,
                   "fresh_valid_nmea_fix": fix_age is not None and -2 <= fix_age < 60})
print(json.dumps(result, indent=2))
