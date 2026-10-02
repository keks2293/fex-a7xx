#!/usr/bin/env python3
"""Где теряются кадры: распределение frametime + корреляция с gpu/cpu/ram/swap.

MangoHud CSV: 2 строки метаданных, затем заголовок
fps,frametime,cpu_load,cpu_power,gpu_load,cpu_temp,gpu_temp,gpu_core_clock,
gpu_mem_clock,gpu_vram_used,gpu_power,ram_used,swap_used,process_rss,cpu_mhz,elapsed
и данные (по строке на интервал, 100 мс).
"""
import csv
import sys


def fnum(s):
    try:
        v = float(str(s).replace(",", "."))
        return v
    except (ValueError, AttributeError):
        return None


def load(path):
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        rows = list(csv.reader(f))
    hdr_i = None
    for i, r in enumerate(rows):
        low = [h.strip().lower() for h in r]
        if "fps" in low and "frametime" in low:
            hdr_i = i
            break
    if hdr_i is None:
        return None
    low = [h.strip().lower() for h in rows[hdr_i]]
    idx = {k: low.index(k) for k in low if k in (
        "fps", "frametime", "cpu_load", "gpu_load", "ram_used", "swap_used",
        "gpu_core_clock", "gpu_power", "cpu_power", "process_rss", "elapsed")}
    data = []
    for r in rows[hdr_i + 1:]:
        rec = {}
        for k, i in idx.items():
            if i < len(r):
                rec[k] = fnum(r[i])
        if rec.get("frametime"):
            data.append(rec)
    return data


def main():
    for path in sys.argv[1:]:
        d = load(path)
        if not d:
            print(f"{path}: нет данных")
            continue
        print(f"=== {path.split('/')[-1]}  (n={len(d)}) ===")
        ft = [r["frametime"] for r in d if r["frametime"] < 5000]  # выбросы-артефакты отбрасываем
        ft_s = sorted(ft)
        n = len(ft_s)
        def pct(p):
            k = max(0, min(n - 1, int(round((p / 100.0) * (n - 1)))))
            return ft_s[k]
        # гистограмма по интервалам
        buckets = [(0, 33.4), (33.4, 45), (45, 60), (60, 80), (80, 120), (120, 200), (200, 10**9)]
        total = n
        for lo, hi in buckets:
            c = sum(1 for v in ft if lo <= v < hi)
            hi_s = "∞" if hi > 10**8 else f"{hi:.0f}"
            print(f"  {lo:6.1f}–{hi_s:>5} мс: {c:5d}  ({100.0 * c / total:5.1f}%)  "
                  + "#" * int(40 * c / total))
        print(f"  ft: med={pct(50):.1f} p90={pct(90):.1f} p95={pct(95):.1f} p99={pct(99):.1f} ms")
        # доля времени в «столбах» (>200 мс = явный stall)
        stall = [v for v in ft if v >= 200]
        if stall:
            print(f"  STALLS >=200мс: {len(stall)} шт, суммарно {sum(stall) / 1000:.1f} с, "
                  f"макс {max(stall):.0f} мс")
        # корреляция gpu_load с frametime
        g = [(r["frametime"], r["gpu_load"]) for r in d
             if r.get("gpu_load") is not None and r["frametime"] < 5000]
        if g:
            import statistics as st
            gm = st.mean(x[1] for x in g)
            slow = [x[1] for x in g if x[0] > 80]
            fast = [x[1] for x in g if x[0] < 50]
            print(f"  gpu_load: среднее={gm:.0f}% | при ft>80мс={st.mean(slow):.0f}% (n={len(slow)}) "
                  f"| при ft<50мс={st.mean(fast) if fast else float('nan'):.0f}% (n={len(fast)})" if fast else
                  f"  gpu_load: среднее={gm:.0f}% | при ft>80мс={st.mean(slow):.0f}% (n={len(slow)})")
        c = [r["cpu_load"] for r in d if r.get("cpu_load") is not None and r["frametime"] < 5000]
        if c:
            import statistics as st
            print(f"  cpu_load: среднее={st.mean(c):.0f}% max={max(c):.0f}%")
        # ram/swap тренд (у этого MangoHud единицы — ГиБ)
        if d and d[0].get("ram_used") is not None:
            print(f"  ram_used: {d[0]['ram_used']:.2f} -> {d[-1]['ram_used']:.2f} ГиБ; "
                  f"swap_used: {d[0].get('swap_used', float('nan')):.2f} -> {d[-1].get('swap_used', float('nan')):.2f} ГиБ")
        gc = [r["gpu_core_clock"] for r in d if r.get("gpu_core_clock")]
        if gc:
            print(f"  gpu_core_clock: min={min(gc):.0f} max={max(gc):.0f} МГц")
        print()


if __name__ == "__main__":
    main()
