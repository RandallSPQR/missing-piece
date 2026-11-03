| model | token agreement | options single | stop ids | repeats bit-identical | fallback | link: max |Δ| vs v1.2.0 (v1.2.0 restart Δ) |
|---|---|---|---|---|---|---|
| llama-3.1-8b-it | 55/55 | True | True | True | True | 0.0000 (0.1151) |
| gemma-2-9b-it | 55/55 | True | True | True | True | 0.0000 (0.0000) |
| qwen3.5-9b | 55/55 | True | True | True | True | 0.0013 (0.1235) |
| gemma-3-27b-it | 55/55 | True | True | True | True | 0.4967 (0.2498) |
| qwen3.5-27b | 55/55 | True | True | True | True | 0.1246 (0.2257) |

| mode | model | server up | C1 cache (max nats; pass) | C2 batching (max nats; pass) | C3 own Δ [95% CI] | s/game strict → mode |
|---|---|---|---|---|---|---|
| throughput | llama-3.1-8b-it | True | 0.125; False | 0.250; False | +0.094 [-0.055, +0.242] | 42.2 → 2.9 |
| throughput | gemma-2-9b-it | True | 0.125; False | 0.125; False | +0.031 [-0.117, +0.195] | 111.6 → 14.5 |
| throughput | qwen3.5-9b (EXCLUDED: v1.3.0 bug) | True | 0.000; True | 0.250; False | +0.016 [-0.094, +0.156] | 50.0 → 46.5 |
| throughput | gemma-3-27b-it | True | 0.375; False | 0.375; False | +0.055 [-0.156, +0.273] | 154.4 → 21.3 |
| throughput | qwen3.5-27b (EXCLUDED: v1.3.0 bug) | None | – | – | – | – |
| **throughput** | **pooled: gemma-2-9b-it, gemma-3-27b-it, llama-3.1-8b-it (24 quads)** | | | | **+0.060 [-0.047, +0.162]; KS p 0.25; pass False** | |
| throughput_invariant | llama-3.1-8b-it | True | 0.000; True | 0.000; True | +0.047 [-0.172, +0.266] | 42.2 → 4.9 |
| throughput_invariant | gemma-2-9b-it | True | 0.000; True | 0.000; True | +0.148 [-0.031, +0.336] | 111.6 → 24.6 |
| throughput_invariant | qwen3.5-9b (EXCLUDED: v1.3.0 bug) | None | – | – | – | – |
| throughput_invariant | gemma-3-27b-it | False | – | – | – | – |
| throughput_invariant | qwen3.5-27b (EXCLUDED: v1.3.0 bug) | None | – | – | – | – |
| **throughput_invariant** | **pooled: gemma-2-9b-it, llama-3.1-8b-it (16 quads)** | | | | **+0.098 [-0.043, +0.246]; KS p 0.31; pass False** | |
