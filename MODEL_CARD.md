# Model Card — EDA Assistant Power/Timing Regression Model

## Overview
A `GradientBoostingRegressor` (multi-output via `MultiOutputRegressor`) trained to predict **area**, **power**, and **critical-path delay** of synthesized RTL designs from Yosys gate-level features.

## Training Data
| Property | Value |
|---|---|
| Source | Open-source RTL benchmarks (MasterRTL, VerilogEval, RTLLM, AssertLLM) + `tests/verilog/` samples |
| Dataset size | 339 unique designs (after deduplication and successful Sky130 synthesis) |
| Ground-truth method | Calibrated SkyWater 130nm (`sky130_fd_sc_hd`) physical cell library mapping & layout-aware wire-load correction |

## Features
| Feature | Description |
|---|---|
| `total_cells` | Total synthesized cells (Yosys `stat`) |
| `ff_cells` | Flip-flop / DFF count |
| `logic_cells` | Combinational gate count |
| `mux_cells` | MUX cell count |
| `buf_cells` | Buffer / inverter count |
| `wires` | Wire count |
| `wire_bits` | Total wire bit-width |
| `memory_bits` | Memory array bit-width |
| `register_bits` | Reg declaration storage bits (complexity.py) |
| `clock_domains` | Clock domain count |
| `approx_cc` | Approximated cyclomatic complexity |
| `nesting_depth` | Max if/case nesting depth |
| `port_count` | Module port count |
| `always_blocks` | Number of always blocks |

## Targets
| Target | Unit |
|---|---|
| `area_um2` | Silicon area in μm² (Sky130 standard cells) |
| `power_uw` | Total power in μW (leakage + dynamic power @ 50MHz, 1.8V VDD) |
| `delay_ps` | Critical-path delay in ps |

## Model Architecture
- `sklearn.ensemble.GradientBoostingRegressor` wrapped in `MultiOutputRegressor`
- Preprocessing: `StandardScaler`
- Hyperparameters: `n_estimators=200`, `learning_rate=0.08`, `max_depth=4`, `subsample=0.8`

## Evaluation
The model evaluated on a held-out test set (20% of dataset, 68 designs) produces the following error metrics:

| Target | MAE | RMSE |
|---|---|---|
| `area_um2` | 2044.8969 | 12953.9215 |
| `power_uw` | 66.7966 | 443.3409 |
| `delay_ps` | 55.6804 | 135.7049 |

## Limitations & Disclaimer
> **This model is NOT a replacement for sign-off Static Timing Analysis (STA) or commercial power extraction tools.**
>
> It provides structural estimates for design-space exploration during RTL development. Ground truth is generated from a calibrated SkyWater 130nm library mapping and wire-load estimation model. For tapeout-grade accuracy, run a full physical implementation flow (e.g. OpenLane/OpenROAD).

## How to Retrain
```bash
python data_generation/generate_dataset.py   # re-generate dataset
python train_power_model.py                  # retrain model
```
