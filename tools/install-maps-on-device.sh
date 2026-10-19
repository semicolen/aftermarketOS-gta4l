#!/bin/sh
set -eu
# Cancel only queued/read-only update queries before taking over package work.
python3 - <<'PY'
import dbus
bus = dbus.SystemBus()
manager = bus.get_object('org.freedesktop.PackageKit', '/org/freedesktop/PackageKit')
paths = dbus.Interface(manager, 'org.freedesktop.PackageKit').GetTransactionList()
transactions = []
for path in paths:
    obj = bus.get_object('org.freedesktop.PackageKit', path)
    values = dbus.Interface(obj, 'org.freedesktop.DBus.Properties').GetAll('org.freedesktop.PackageKit.Transaction')
    if int(values['Role']) != 9 or not bool(values['AllowCancel']):
        raise RuntimeError('another package operation is active; leaving it alone')
    transactions.append(obj)
for obj in transactions:
    dbus.Interface(obj, 'org.freedesktop.PackageKit.Transaction').Cancel()
print('Cancelled read-only package update queries:', len(transactions))
PY
systemctl mask --runtime --now packagekit.service
cleanup() { systemctl unmask --runtime packagekit.service; }
trap cleanup EXIT
export DEBIAN_FRONTEND=noninteractive
apt-get -o DPkg::Lock::Timeout=90 update
apt-get -o DPkg::Lock::Timeout=90 install -y --no-install-recommends gnome-maps systemd-timesyncd libqmi-utils
dpkg --audit
systemctl is-active systemd-timesyncd
echo MAPS_AND_TIME_SYNC_INSTALLED
