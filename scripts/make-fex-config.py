#!/usr/bin/env python3
"""Сгенерировать FEX_APP_CONFIG для A/B-прогона.

Воспроизводит логику /usr/libexec/armada/armada-game-launch (apply_fex):
берёт /usr/share/fex-emu/Config.json, выбрасывает RootFS/ThunkHostLibs/
ThunkGuestLibs (чтобы не затоптать rootfs Steam-FEX), поверх кладёт профиль
из /usr/share/armada/fex-profiles.json и пишет в файл.

Путь к файлу печатается в stdout — его экспортируют как FEX_APP_CONFIG.
arm64ec/wow64 FEX (proton-cachyos) читают именно эту переменную; on-disk
конфиги видит только системный FEX.
"""
import json
import sys
from pathlib import Path

BASE = Path("/usr/share/fex-emu/Config.json")
PROFILES = Path("/usr/share/armada/fex-profiles.json")
OUTDIR = Path("/tmp/opencode/fex-cfg")


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <profile>", file=sys.stderr)
        print(f"доступно: {list(json.load(open(PROFILES))['profiles'].keys())}", file=sys.stderr)
        sys.exit(1)
    profile = sys.argv[1]

    contract = json.load(open(PROFILES, encoding="utf-8"))
    profiles = contract["profiles"]
    if profile not in profiles:
        print(f"нет профиля {profile!r}; доступно: {list(profiles)}", file=sys.stderr)
        sys.exit(1)

    config = json.load(open(BASE, encoding="utf-8"))
    for key in ("RootFS", "ThunkGuestLibs", "ThunkHostLibs"):
        config.get("Config", {}).pop(key, None)
    allowed = set().union(*(p["config"].keys() for p in profiles.values()))
    fex = profiles[profile]["config"]
    config.setdefault("Config", {}).update({k: v for k, v in fex.items() if k in allowed})

    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = OUTDIR / f"fex-{profile}.json"
    out.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # только ключи профиля, для лога
    active = {k: v for k, v in config["Config"].items() if k in allowed}
    print(f"FEX_PROFILE={profile}", file=sys.stderr)
    print(f"FEX_CONFIG_KEYS={json.dumps(active, sort_keys=True)}", file=sys.stderr)
    print(out)


if __name__ == "__main__":
    main()
