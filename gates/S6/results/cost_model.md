| protocol variant | prompt tokens / game | uncached prompt tokens / game | output tokens / game | calls / game |
|---|---|---|---|---|
| S6_as_filed | 120,853 | 120,853 | 2,787 | 55 |
| S6_as_filed_cache | 120,853 | 18,625 | 2,787 | 55 |
| new_probes | 101,843 | 101,843 | 2,776 | 44 |
| new_probes_cache | 101,843 | 17,614 | 2,776 | 44 |

| stories (1 replicate) | variant | GPU h (mid) | total $ (low / mid / high) |
|---|---|---|---|
| 24 | S6_as_filed (sequential, no cache, all probes, Opus all games) | 25.7 | 81 |
| 24 | new probes (sequential, no cache) | 24.3 | 77 |
| 24 | new probes + prefix caching (sequential) | 19.0 | 64 |
| 24 | new probes + caching + batched | 5.5 | 33 / 30 / 29 |
| 24 | new probes + caching + batched, batch-invariant | 7.5 | 49 / 35 / 30 |
| 26 | S6_as_filed (sequential, no cache, all probes, Opus all games) | 28.0 | 88 |
| 26 | new probes (sequential, no cache) | 26.5 | 84 |
| 26 | new probes + prefix caching (sequential) | 20.8 | 70 |
| 26 | new probes + caching + batched | 6.2 | 37 / 33 / 32 |
| 26 | new probes + caching + batched, batch-invariant | 8.4 | 53 / 39 / 33 |
| 30 | S6_as_filed (sequential, no cache, all probes, Opus all games) | 32.3 | 102 |
| 30 | new probes (sequential, no cache) | 30.5 | 97 |
| 30 | new probes + prefix caching (sequential) | 24.0 | 80 |
| 30 | new probes + caching + batched | 7.1 | 42 / 38 / 36 |
| 30 | new probes + caching + batched, batch-invariant | 9.6 | 62 / 45 / 38 |
| 36 | S6_as_filed (sequential, no cache, all probes, Opus all games) | 38.5 | 122 |
| 36 | new probes (sequential, no cache) | 36.4 | 116 |
| 36 | new probes + prefix caching (sequential) | 28.5 | 96 |
| 36 | new probes + caching + batched | 8.3 | 50 / 46 / 43 |
| 36 | new probes + caching + batched, batch-invariant | 11.3 | 73 / 53 / 45 |
| 48 | S6_as_filed (sequential, no cache, all probes, Opus all games) | 51.3 | 162 |
| 48 | new probes (sequential, no cache) | 48.5 | 154 |
| 48 | new probes + prefix caching (sequential) | 38.0 | 128 |
| 48 | new probes + caching + batched | 11.1 | 66 / 61 / 58 |
| 48 | new probes + caching + batched, batch-invariant | 15.1 | 98 / 71 / 61 |
| 60 | S6_as_filed (sequential, no cache, all probes, Opus all games) | 64.2 | 203 |
| 60 | new probes (sequential, no cache) | 60.7 | 193 |
| 60 | new probes + prefix caching (sequential) | 47.5 | 160 |
| 60 | new probes + caching + batched | 13.8 | 83 / 76 / 72 |
| 60 | new probes + caching + batched, batch-invariant | 18.9 | 122 / 88 / 76 |
| 72 | S6_as_filed (sequential, no cache, all probes, Opus all games) | 77.0 | 244 |
| 72 | new probes (sequential, no cache) | 72.8 | 231 |
| 72 | new probes + prefix caching (sequential) | 57.0 | 192 |
| 72 | new probes + caching + batched | 16.6 | 100 / 91 / 86 |
| 72 | new probes + caching + batched, batch-invariant | 22.6 | 147 / 106 / 91 |
