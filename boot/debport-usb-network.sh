#!/bin/sh
set -eu
iface=''
for candidate in usb0 rndis0; do
    if [ -d "/sys/class/net/$candidate" ]; then iface=$candidate; break; fi
done
[ -n "$iface" ] || { echo 'USB gadget interface missing' >&2; exit 1; }
ip link set "$iface" up
ip address replace 172.16.42.1/24 dev "$iface"
exec /usr/lib/debport-init/ld-musl-aarch64.so.1 \
    /usr/lib/debport-init/unudhcpd -i "$iface" -s 172.16.42.1 -c 172.16.42.2
