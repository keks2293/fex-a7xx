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
- RAM / swap (засекается в игре ~7.3 ГиБ + 3.1 ГиБ zram при 100%)
- CPU ~1.65 ядра из 8, GPU `cur_freq` до 680 МГц (по прошлым замам — ни один ресурс
  не загружен, кадр 75 мс → упор в память/latency, FEX-стекло в этом сценарии
  кандидат на источник)

## Статус

- [ ] A/B RE4: `default` vs `fast`
- [ ] A/B RE4: `default` vs `compatible` (изоляция Multiblock)
- [ ] WNO: фиксация базового прогона под FEX `default`
- [ ] Вывод: влияет ли Multiblock/TSO на просадки
