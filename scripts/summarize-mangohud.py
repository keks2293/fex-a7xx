#!/usr/bin/env python3
"""Сводка по MangoHud CSV: fps и frametime.

Использует столбцы frame_rate и frame_time (имена MangoHud; fallback по
содержанию заголовка). Печатает mean/median/min/max fps и median/p5/p95/max
frametime. Несколько CSV -> таблица.
"""
import csv
import sys


def cols(header):
    low = {h.strip().lower(): i for i, h in enumerate(header)}
    def find(*names):
        for n in names:
            for k, i in low.items():
                if n in k:
                    return i
        return None
    return find("frame_rate", "framerate", "fps"), find("frame_time", "frametime", "ft")


def fnum(s):
    try:
        return float(str(s).replace(",", "."))
    except (ValueError, AttributeError):
        return None


def summarize(path):
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        rows = list(csv.reader(f))
    if not rows:
        return None
    hdr, data = rows[0], rows[1:]
    fi, ti = cols(hdr)
    fps = [v for v in (fnum(r[fi]) for r in data if fi is not None and fi < len(r)) if v and v > 0]
    ft = [v for v in (fnum(r[ti]) for r in data if ti is not None and ti < len(r)) if v and v > 0]
    if not fps:
        return None
    fps_s = sorted(fps)
    ft_s = sorted(ft)
    n = len(fps_s)
    def pct(a, p):
        if not a:
            return float("nan")
        k = max(0, min(len(a) - 1, int(round((p / 100.0) * (len(a) - 1)))))
        return a[k]
    return {
        "n": n,
        "fps_mean": sum(fps_s) / n,
        "fps_med": fps_s[n // 2],
        "fps_min": fps_s[0],
        "fps_p5": pct(fps_s, 5),
        "fps_max": fps_s[-1],
        "ft_med": ft_s[len(ft_s) // 2] if ft_s else float("nan"),
        "ft_p95": pct(ft_s, 95),
        "ft_max": ft_s[-1] if ft_s else float("nan"),
    }


def main():
    for path in sys.argv[1:]:
        s = summarize(path)
        label = path.split("/")[-1]
        if not s:
            print(f"{label}: нет данных")
            continue
        print(
            f"{label}: n={s['n']} "
            f"fps mean={s['fps_mean']:.1f} med={s['fps_med']:.1f} "
            f"p5={s['fps_p5']:.1f} min={s['fps_min']:.1f} max={s['fps_max']:.1f} | "
            f"ft med={s['ft_med']:.1f} p95={s['ft_p95']:.1f} max={s['ft_max']:.1f} ms"
        )


if __name__ == "__main__":
    main()
