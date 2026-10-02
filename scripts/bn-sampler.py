#!/usr/bin/env python3
"""Сэмплер «на чем теряем кадры»: PSI (дельты total), io.stat диска игры,
meminfo, топ-треды re4.exe по CPU. Интервал 100 мс. Вывод — CSV.

PSI total — накопленные мкс; дельта за интервал / интервал = доля времени
окна, когда задачи стояли (some = хотя бы одна, full = все).
"""
import csv
import glob
import os
import re
import sys
import time

INTERVAL = 0.1
GAME_DISK = "21:32"  # /dev/sdg2 (Z Slim, exFAT)
MAX_SECS = 420
IO_PATH = "/sys/fs/cgroup/io.stat"


def read_psu(path):
    tot = {"some": 0, "full": 0}
    try:
        with open(path) as f:
            for line in f:
                for kind in ("some", "full"):
                    if line.startswith(kind):
                        m = re.search(r"total=(\d+)", line)
                        if m:
                            tot[kind] = int(m.group(1))
    except OSError:
        pass
    return tot


def read_io():
    rb = wb = 0
    try:
        with open(IO_PATH) as f:
            for line in f:
                parts = line.split()
                if parts and parts[0] == GAME_DISK:
                    kv = dict(x.split("=", 1) for x in parts[1:])
                    rb = int(kv.get("rbytes", 0))
                    wb = int(kv.get("wbytes", 0))
    except (OSError, ValueError):
        pass
    return rb, wb


def read_meminfo():
    mi = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":", 1)
            mi[k] = int(v.strip().split()[0])
    return (mi.get("MemAvailable", 0), mi.get("SwapFree", 0),
            mi.get("SwapTotal", 0))


def find_re4_pid():
    best = None
    for p in glob.glob("/proc/[0-9]*"):
        try:
            with open(p + "/cmdline", "rb") as f:
                cmd = f.read().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        if "re4.exe" in cmd:
            best = int(p.split("/")[-1])
    return best


def thread_cpu(pid):
    """{tid: utime+stime} для всех тредов pid."""
    out = {}
    try:
        for t in glob.glob(f"/proc/{pid}/task/*/stat"):
            try:
                with open(t) as f:
                    data = f.read()
                # имя в скобках может содержать пробелы: парсим после последнего ')'
                body = data[data.rfind(")") + 2:].split()
                tid = int(t.split("/")[-1])
                out[tid] = int(body[11]) + int(body[12])  # utime+stime (clk_ticks)
            except (OSError, ValueError, IndexError):
                pass
    except OSError:
        pass
    return out


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "bn-sample.csv"
    clk = os.sysconf("SC_CLK_TCK")
    pids = {"mem": "/proc/pressure/memory", "cpu": "/proc/pressure/cpu",
            "io": "/proc/pressure/io"}
    prev_psu = {k: read_psu(v) for k, v in pids.items()}
    prev_io = read_io()
    prev_th = {}
    prev_th_pid = None
    start = time.time()
    t_next = start + INTERVAL
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t", "epoch", "psi_mem_some", "psi_mem_full", "psi_cpu_some",
                    "psi_cpu_full", "psi_io_some", "psi_io_full", "disk_r_mbs",
                    "disk_w_mbs", "mem_avail_kb", "swap_used_kb", "top_threads"])
        while time.time() - start < MAX_SECS:
            time.sleep(max(0, t_next - time.time()))
            now = time.time()
            el = now - start
            psu = {k: read_psu(v) for k, v in pids.items()}
            io = read_io()
            mem_avail, swap_free, swap_total = read_meminfo()
            pid = find_re4_pid()
            top = ""
            if pid and pid != prev_th_pid:
                prev_th = thread_cpu(pid)
                prev_th_pid = pid
                prev_th_t = now
            elif pid:
                th = thread_cpu(pid)
                dt = max(1e-6, now - prev_th_t)
                d = [(tid, (v - prev_th.get(tid, v)) / dt / clk * 100)
                     for tid, v in th.items() if tid in prev_th]
                d = [x for x in d if x[1] >= 1.0]
                d.sort(key=lambda x: -x[1])
                top = " ".join(f"{tid}:{p:.0f}%" for tid, p in d[:3])
                prev_th = th
                prev_th_t = now
            w.writerow([
                f"{el:.1f}", f"{now:.3f}",
                round((psu["mem"]["some"] - prev_psu["mem"]["some"]) / 1000.0, 1),
                round((psu["mem"]["full"] - prev_psu["mem"]["full"]) / 1000.0, 1),
                round((psu["cpu"]["some"] - prev_psu["cpu"]["some"]) / 1000.0, 1),
                round((psu["cpu"]["full"] - prev_psu["cpu"]["full"]) / 1000.0, 1),
                round((psu["io"]["some"] - prev_psu["io"]["some"]) / 1000.0, 1),
                round((psu["io"]["full"] - prev_psu["io"]["full"]) / 1000.0, 1),
                round((io[0] - prev_io[0]) / (now - (t_next - INTERVAL)) / 1e6, 1),
                round((io[1] - prev_io[1]) / (now - (t_next - INTERVAL)) / 1e6, 1),
                mem_avail,
                (swap_total or 0) - swap_free,
                top,
            ])
            prev_psu = psu
            prev_io = io
            f.flush()
            t_next += INTERVAL
    print(f"done: {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
