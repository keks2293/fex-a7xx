#!/usr/bin/env python3
"""Совмещение MangoHud-CSV и bn-sampler по wall-времени и корреляция.

Стенография времени (проверено по первому прогону):
- MangoHud `elapsed` — наносекунды от инициализации HUD;
- `frametime[0]` — секунды от boot до первого кадра;
- wall(i) = boot_epoch + ft0 + (elapsed[i] - elapsed[0]) / 1e9.
boot_epoch = now - /proc/uptime.
"""
import bisect
import csv
import sys


def fnum(s):
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def load_mango(path, boot_epoch):
    rows = list(csv.reader(open(path, newline="", errors="replace")))
    hdr_i = next(i for i, r in enumerate(rows)
                 if "fps" in r and "frametime" in r)
    idx = {k: i for i, k in enumerate(rows[hdr_i])}
    data = rows[hdr_i + 1:]
    out = []
    el0 = None
    ft0 = None  # frametime первого кадра = секунды от boot до первого кадра
    for r in data:
        ft = fnum(r[idx["frametime"]])
        if ft is None:
            continue
        el = fnum(r[idx["elapsed"]])
        if el0 is None:
            el0 = el
            ft0 = ft / 1000.0
        wall = boot_epoch + ft0 + (el - el0) / 1e9
        out.append({
            "wall": wall, "fps": fnum(r[idx["fps"]]) or 0.0,
            "ft": ft, "gpu_load": fnum(r[idx["gpu_load"]]),
            "cpu_load": fnum(r[idx["cpu_load"]]),
            "swap_used": fnum(r[idx["swap_used"]]),
        })
    return out


def load_sampler(path):
    rows = list(csv.reader(open(path, newline="", errors="replace")))
    idx = {k: i for i, k in enumerate(rows[0])}
    out = []
    for r in rows[1:]:
        if len(r) < len(idx) or not r[idx["epoch"]]:
            continue
        rec = {"epoch": fnum(r[idx["epoch"]])}
        for k in idx:
            if k in ("t", "epoch", "top_threads"):
                continue
            rec[k] = fnum(r[idx[k]])
        rec["top_threads"] = r[idx["top_threads"]] if idx["top_threads"] < len(r) else ""
        out.append(rec)
    out.sort(key=lambda x: x["epoch"])
    return out


def pearson(a, b):
    n = min(len(a), len(b))
    if n < 10:
        return float("nan")
    a, b = a[:n], b[:n]
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = sum((x - ma) ** 2 for x in a) ** 0.5
    vb = sum((y - mb) ** 2 for y in b) ** 0.5
    return cov / (va * vb) if va and vb else float("nan")


def main():
    import time
    boot = time.time() - float(open("/proc/uptime").read().split()[0])
    mango_path, samp_path = sys.argv[1], sys.argv[2]
    mango = load_mango(mango_path, boot)
    samp = load_sampler(samp_path)
    epochs = [s["epoch"] for s in samp]
    print(f"mango n={len(mango)}  sampler n={len(samp)}  "
          f"mango[{mango[0]['wall']:.1f}..{mango[-1]['wall']:.1f}]  "
          f"sampler[{epochs[0]:.1f}..{epochs[-1]:.1f}]")

    def nearest(wall):
        i = bisect.bisect_left(epochs, wall)
        if i <= 0:
            return samp[0]
        if i >= len(samp):
            return samp[-1]
        return samp[i - 1] if wall - epochs[i - 1] < epochs[i] - wall else samp[i]

    # совмещаем
    for m in mango:
        m["s"] = nearest(m["wall"])

    keys = ("psi_mem_some", "psi_mem_full", "psi_cpu_some", "psi_io_some",
            "disk_r_mbs", "disk_w_mbs", "mem_avail_kb", "swap_used_kb")
    steady = [m for m in mango if 45 < m["ft"] < 150]
    fast = [m for m in mango if m["ft"] < 34]
    stalls = [m for m in mango if m["ft"] >= 200]
    print(f"\nsteady(45-150мс) n={len(steady)}  fast(<34мс) n={len(fast)}  "
          f"stalls(>=200мс) n={len(stalls)}")

    def avg(ms, k):
        vs = [m["s"].get(k) for m in ms if m["s"].get(k) is not None]
        return sum(vs) / len(vs) if vs else float("nan")

    print("\n--- средние в steady-state (45-150 мс) ---")
    print(f"  ft={sum(m['ft'] for m in steady) / len(steady):.1f}мс  "
          f"gpu_load={sum(m['gpu_load'] for m in steady if m['gpu_load'] is not None) / len([m for m in steady if m['gpu_load'] is not None]):.0f}%")
    for k in keys:
        print(f"  {k:16s} = {avg(steady, k):.1f}")

    print("\n--- корреляция ft с метриками (steady) ---")
    fts = [m["ft"] for m in steady]
    for k in keys:
        vs = [m["s"].get(k) or 0 for m in steady]
        print(f"  pearson(ft, {k:15s}) = {pearson(fts, vs):+.2f}")

    print("\n--- STALLS >=200мс (по одному) ---")
    for m in stalls:
        s = m["s"]
        print(f"  wall={m['wall']:.1f} ft={m['ft']:.0f}мс gpu={m['gpu_load']:.0f}% | "
              f"psi_mem={s.get('psi_mem_some'):.0f}/{s.get('psi_mem_full'):.0f} "
              f"psi_io={s.get('psi_io_some'):.0f} disk_r={s.get('disk_r_mbs'):.0f}МБ/с "
              f"swap={s.get('swap_used_kb', 0) / 1024 / 1024:.2f}ГиБ "
              f"thr=[{s.get('top_threads', '')}]")

    # топ-треды за весь steady
    from collections import Counter
    cnt = Counter()
    for m in steady:
        for tok in (m["s"].get("top_threads") or "").split():
            cnt[tok] += 1
    print("\n--- топ-треды re4.exe в steady (частота попадания в top-3) ---")
    for tok, c in cnt.most_common(8):
        print(f"  {tok:14s} {c}")

    # память: тренд swap
    sw = [m["swap_used"] for m in mango if m["swap_used"] is not None]
    if sw:
        print(f"\n--- swap_used (MangoHud, ГиБ): start={sw[0]:.2f} end={sw[-1]:.2f} "
              f"max={max(sw):.2f}")
    mem = [m["s"].get("mem_avail_kb") for m in mango if m["s"].get("mem_avail_kb")]
    if mem:
        print(f"--- mem_avail (MB): start={mem[0] / 1024:.0f} end={mem[-1] / 1024:.0f} "
              f"min={min(mem) / 1024:.0f}")


if __name__ == "__main__":
    main()
