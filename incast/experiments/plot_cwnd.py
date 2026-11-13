#!/usr/bin/env python3
"""Plot cwnd versus time from cwnd_log.csv for the checkpoint-2 report."""

import csv
import sys
from collections import OrderedDict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

STATE_COLOR = {
    "slow_start": "#9ecae1",
    "congestion_avoidance": "#a1d99b",
    "fast_recovery": "#fdae6b",
}

STATE_LABEL = {
    "slow_start": "slow start",
    "congestion_avoidance": "congestion avoidance",
    "fast_recovery": "fast recovery",
}


def load(path):
    rows = []
    with open(path, newline="") as fp:
        for rec in csv.DictReader(fp):
            rows.append(
                {
                    "t": float(rec["time"]),
                    "cwnd": int(rec["cwnd"]),
                    "ssthresh": int(rec["ssthresh"]),
                    "state": rec["state"],
                    "event": rec["event"],
                }
            )
    if not rows:
        raise SystemExit("cwnd log is empty")
    t0 = rows[0]["t"]
    for row in rows:
        row["t"] -= t0
    return rows


def shade_states(ax, rows):
    seen = set()
    start = rows[0]["t"]
    state = rows[0]["state"]
    for row in rows[1:]:
        if row["state"] == state:
            continue
        label = None
        if state in STATE_LABEL and state not in seen:
            label = STATE_LABEL[state]
            seen.add(state)
        ax.axvspan(start, row["t"], color=STATE_COLOR.get(state, "#dddddd"), alpha=0.45, label=label, lw=0)
        start = row["t"]
        state = row["state"]
    label = None
    if state in STATE_LABEL and state not in seen:
        label = STATE_LABEL[state]
    ax.axvspan(start, rows[-1]["t"], color=STATE_COLOR.get(state, "#dddddd"), alpha=0.45, label=label, lw=0)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "cwnd_log.csv"
    dst = sys.argv[2] if len(sys.argv) > 2 else "cwnd.png"
    rows = load(src)

    fig, ax = plt.subplots(figsize=(11, 5.5))
    shade_states(ax, rows)
    ax.step([r["t"] for r in rows], [r["cwnd"] for r in rows], where="post", color="#222222", lw=1.4, label="cwnd")

    marked = set()
    for row in rows:
        if row["event"] == "triple_dup_ack":
            label = "3 dup ACK" if "triple_dup_ack" not in marked else None
            marked.add("triple_dup_ack")
            ax.scatter(row["t"], row["cwnd"], marker="v", s=46, color="#d94801", zorder=5, label=label)
        elif row["event"] == "timeout":
            label = "timeout" if "timeout" not in marked else None
            marked.add("timeout")
            ax.scatter(row["t"], row["cwnd"], marker="X", s=58, color="#a50f15", zorder=5, label=label)

    # One legend entry per label, in first-seen order.
    handles, labels = ax.get_legend_handles_labels()
    uniq = OrderedDict()
    for handle, label in zip(handles, labels):
        if label and label not in uniq:
            uniq[label] = handle
    ax.legend(uniq.values(), uniq.keys(), loc="upper right")
    ax.set_xlabel("time since connection start (s)")
    ax.set_ylabel("cwnd (bytes)")
    ax.set_title("CMU-TCP Reno congestion window")
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(dst, dpi=150)
    print(f"wrote {dst}")
    print(
        "events",
        "triple_dup_ack",
        sum(r["event"] == "triple_dup_ack" for r in rows),
        "timeout",
        sum(r["event"] == "timeout" for r in rows),
        "duration",
        f"{rows[-1]['t']:.2f}",
    )


if __name__ == "__main__":
    main()
