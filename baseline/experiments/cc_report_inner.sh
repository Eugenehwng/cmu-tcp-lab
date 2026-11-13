#!/usr/bin/env bash
# Run inside a privileged Linux container. Shapes loopback with tc netem,
# transfers a file, and writes the cwnd plot next to the log.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ "${SKIP_APT:-}" != 1 ]; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y build-essential iproute2 iptables python3 python3-matplotlib
fi

mkdir -p build
make clean
make server client

BYTES=4194304
dd if=/dev/urandom of=/tmp/payload.bin bs=1M count=4 status=none
OUT="$ROOT/cwnd_report"
mkdir -p "$OUT" /tmp/cc-server
rm -f "$OUT/cwnd_log.csv" /tmp/cc-server/cwnd_log.csv

# 5 Mbps and 10 ms. 0.3% is low enough that a full window usually loses at
# most one segment, so Reno fast-retransmits instead of timing out. A later
# drop shorter than one RTO (3 s) forces a single timeout: the retransmission
# goes out after the drop has ended.
tc qdisc del dev lo root 2>/dev/null || true
tc qdisc replace dev lo root netem delay 10ms rate 5mbit loss 0.3%
tc qdisc show dev lo

export serverport15441=15441
export nbytes="$BYTES"
(cd /tmp/cc-server && "$ROOT/server") >"$OUT/server.log" 2>&1 &
SERVER_PID=$!
sleep 0.4

(
  sleep 3
  tc qdisc replace dev lo root netem delay 10ms rate 5mbit loss 100%
  sleep 2.6
  tc qdisc replace dev lo root netem delay 10ms rate 5mbit loss 0.3%
) &
SHAPER_PID=$!

export server15441=127.0.0.1
export payload=/tmp/payload.bin
cd "$OUT"
set +e
"$ROOT/client" >"$OUT/client.log" 2>&1
CLIENT_RC=$?
set -e
wait "$SHAPER_PID" || true
kill "$SERVER_PID" 2>/dev/null || true
wait "$SERVER_PID" 2>/dev/null || true
tc qdisc del dev lo root 2>/dev/null || true

python3 "$ROOT/experiments/plot_cwnd.py" "$OUT/cwnd_log.csv" "$OUT/cwnd.png"

cat >"$OUT/scenario.txt" <<EOF
File size: $BYTES bytes (/tmp/payload.bin, 4 MiB of random data).
Sender: ./client (TCP_INITIATOR). Receiver: ./server (TCP_LISTENER).
Interface: lo, inside one Linux network namespace.

Steady configuration, equivalent to:
  sudo tcset lo --rate 5Mbps --delay 10ms --loss 0.3% --overwrite
Applied with:
  tc qdisc replace dev lo root netem delay 10ms rate 5mbit loss 0.3%

Timeout burst, from 3.0 s to 5.6 s after the client starts (shorter than the
3000 ms RTO, so the retransmission is not dropped too):
  tc qdisc replace dev lo root netem delay 10ms rate 5mbit loss 100%
Then the 0.3% configuration is restored.

Loss on lo affects both data and ACKs. The fixed RTO is DEFAULT_TIMEOUT (3000 ms).
Client exit code: $CLIENT_RC
Client output:
$(cat "$OUT/client.log")
Server output:
$(cat "$OUT/server.log")
EOF

echo "client_rc=$CLIENT_RC"
cat "$OUT/scenario.txt"
