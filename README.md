# FEX Research — a7xx (RE4, WNO)

Изоляция влияния FEX (в первую очередь Multiblock) на просадки FPS в играх.
Основной стек Turnip-патчей живёт в `../turnip-a7xx-dx12/` и между прогонами FEX
не пересобирается: меняем только профиль FEX.

## Гипотеза

RE4 (DX12, vkd3d → Turnip, 13 fps в стоке и патче, упор в память) — просадки
могут быть именно в FEX. WNO — OpenGL, идёт через `kgsl_dri`, Turnip не участвует;
в WNO FEX тоже может быть упором, но Turnip-патчи там не работают.

## Профили FEX (`/usr/share/armada/fex-profiles.json`)

| профиль | TSOEnabled | Multiblock | X87ReducedPrecision | VectorTSO | MemcpySetTSO | HalfBarrierTSO |
|---|---|---|---|---|---|---|
| `default` | 1 | **1** | 1 | 0 | 0 | 1 |
| `fast` | 0 | **1** | 1 | 0 | 0 | 0 |
| `compatible` | 1 | **0** | 0 | 1 | 1 | 1 |

А/B: `default` vs `fast` (TSO и HalfBarrier) — изоляция TSO-стекла;
`default` vs `compatible` — изоляция самого Multiblock.

## Методика

1. RE4: `../turnip-a7xx-dx12/scripts/run-game.sh patched <sec>` (DX12, vkd3d → Turnip).
2. WNO: `../turnip-a7xx-dx12/scripts/run-wtno.sh` (OpenGL, Turnip не участвует).
3. Power-профиль `performance` — через `/usr/libexec/armada/armada-game-launch`
   (обёртка принимает только `COMMAND [ARGS...]`; профиль задаётся отдельно,
   `scaling_governor` у `root:wheel` rw — смена без sudo).
4. MangoHud CSV → `results/` (в `/tmp/opencode/mangologs` не держать — не переживает
   перезагрузку).
5. Один прогон на конфигурацию, минимум ~2 мин стабильного участка; при расхождении
   p95/min — повтор.
6. Не гонять сборку и игру одновременно. Остатки wine убивать по pid.

## Измерения

- mean / median / min / max fps
- frametime: median / p95 / max
- RAM / swap (в игре ~7 ГиБ RAM + до 4 ГиБ zram)
- MangoHud CSV содержит и gpu_load (kgsl ioctl, доля времени GPU-busy),
  cpu_load, ram/swap, gpu_core_clock по каждому интервалу 100 мс.

## Результаты RE4 (2026-10-02, драйвер patched, DX12)

A/B профилей FEX (`results/fps-fex-{default,fast,compatible}.csv`, по 180 с):

| профиль | Multiblock | TSO | fps med | fps p5 | ft med | ft p95 |
|---|---|---|---|---|---|---|
| default | 1 | 1 | 15.3 | 14.6 | 65.2 | 68.3 |
| fast | 1 | 0 | 15.6 | 15.1 | 64.2 | 66.2 |
| compatible | 0 | 1 | 15.6 | 15.2 | 64.2 | 65.8 |

Все три в пределах шума → **профиль FEX (Multiblock/TSO) на FPS RE4 не влияет**.

Где теряются кадры (`scripts/bn-sampler.py` + `scripts/align-correlate.py`,
прогон `default`, данные `results/bn-default.csv`):

- **Стедди-стейт (80% сэмплов, ft 45–150 мс): gpu_load = 98% при max-частоте
  680 МГц** (devfreq `simple_ondemand`, потолок 680). PSI memory/io ≈ 0,
  диск 0 МБ/с, swap стабилен (~4 ГиБ), CPU системы ~26%. **Кадр 64.6 мс
  лимитирован GPU** — согласуется с §13 основного репо (FPS не зависит от
  драйвера: патчи сокращают bandwidth, а GPU не bandwidth-упор).
- **Сталлы ≥200 мс — только в первые ~6 с после первого кадра** (загрузка
  уровня): USB exFAT-стриминг до 43 МБ/с, psi_mem до 51%, swap заполняется
  2.6→4.1 ГиБ. В последующие ~145 с геймплея сталлов не было вообще.
- «Быстрые» кадры <34 мс (меню/лёгкие сцены): gpu 43%, cpu 54% — там упор
  смещён в CPU (стриминг/декомпрессия/FEX).

Практические следствия:

1. Игра на USB exFAT (`/dev/sdg`), на внутреннем btrfs 202 ГиБ свободно —
   перенос RE4 на UFS сокращает загрузку уровней и стриминг-сталлы.
2. Стедди-стейт GPU-bound → рычаг: настройки графики RE4 (резолв/тени),
   не драйвер и не FEX.
3. FEX-профили трогать не нужно.

Ограничение: `top_threads` в bn-sampler пуст — поиск re4.exe по cmdline не
срабатывает (процесс proton/arm64ec cmdline не содержит `re4.exe`); для
тредовых данных нужен поиск по `/proc/<pid>/maps` (libarm64ecfex) + повторный
прогон.

## Статус

- [x] A/B RE4: `default` vs `fast` — в пределах шума
- [x] A/B RE4: `default` vs `compatible` (изоляция Multiblock) — в пределах шума
- [x] Вывод: Multiblock/TSO на просадки RE4 не влияют; упор — GPU (98%, max freq)
- [ ] WNO: фиксация базового прогона под FEX `default`
- [ ] (опц.) тредовые данные: починить поиск процесса, повторный прогон
