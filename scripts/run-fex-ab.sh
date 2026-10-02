#!/usr/bin/env bash
# A/B-прогон RE4 (DX12, proton → vkd3d → Turnip) под заданным FEX-профилем.
#
#   scripts/run-fex-ab.sh <profile> [timeout-sec]
#
# Генерит FEX_APP_CONFIG (scripts/make-fex-config.py), экспортирует его и
# вызывает scripts/run-game.sh patched из основного репо с TAG=fex-<profile>
# и MangoHud CSV (HUDLOG=timeout, HUDINTERVAL=100). CSV и логи копирует в
# fex-a7xx/results/.
#
# FEX_APP_CONFIG — единственный knob, который читают FEX arm64ec/wow64 из
# proton-cachyos (on-disk конфиги видит только системный FEX). Профиль
# детерминирован: обёртка armada-game-launch не участвует.
set -euo pipefail

PROFILE="${1:?usage: run-fex-ab.sh <profile> [timeout-sec]}"
TIMEOUT="${2:-180}"

FEEX="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TURNIP="$(cd "$FEEX/../turnip-a7xx-dx12" && pwd)"
mkdir -p "$FEEX/results"

# Генерация конфига; путь в stdout, описание профиля в stderr -> в results/fex-cfg.log
CFG="$(python3 "$FEEX/scripts/make-fex-config.py" "$PROFILE" 2>>"$FEEX/results/fex-cfg.log")"
[ -f "$CFG" ] || { echo "нет сгенерированного конфига $CFG" >&2; exit 1; }
export FEX_APP_CONFIG="$CFG"
{
  echo "# $(date -Is) profile=$PROFILE"
  cat "$FEEX/results/fex-cfg.log" | tail -2
} >> "$FEEX/results/fex-cfg.log"

# run-game.sh читает TAG / HUDLOG / HUDINTERVAL из окружения
export TAG="fex-${PROFILE}"
export HUDLOG="$TIMEOUT"
export HUDINTERVAL=100

bash "$TURNIP/scripts/run-game.sh" patched "$TIMEOUT"
RC=$?

# Перенос результатов в fex-a7xx (MangoHud CSV в /tmp/opencode/mangologs — tmpfs)
shopt -s nullglob
for csv in /tmp/opencode/mangologs/*.csv; do
  cp -f "$csv" "$FEEX/results/fps-fex-${PROFILE}.csv"
done
cp -f "$TURNIP/results/game-patched-fex-${PROFILE}.log" "$FEEX/results/" 2>/dev/null || true
cp -f "$TURNIP/results/raw/game-patched-fex-${PROFILE}.log" \
      "$FEEX/results/raw-game-patched-fex-${PROFILE}.log" 2>/dev/null || true

echo
echo "=== fex-a7xx: $PROFILE, код возврата $RC ==="
echo "CSV:  $FEEX/results/fps-fex-${PROFILE}.csv"
