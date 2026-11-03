| protocol variant | prompt tokens / game | uncached prompt tokens / game | output tokens / game | calls / game |
|---|---|---|---|---|
| S6_as_filed | 120,853 | 120,853 | 2,787 | 55 |
| S6_as_filed_cache | 120,853 | 18,625 | 2,787 | 55 |
| new_probes | 98,648 | 98,648 | 2,775 | 43 |
| new_probes_cache | 98,648 | 18,680 | 2,775 | 43 |

| stories (1 replicate) | variant | GPU h (mid) | total $ (low / mid / high) |
|---|---|---|---|
| 24 | S6_as_filed (sequential, no cache, all probes, Opus all games) | 25.7 | 81 |
| 24 | new probes (sequential, no cache) | 24.1 | 63 |
| 24 | new probes + prefix caching (sequential) | 19.0 | 51 |
| 24 | new probes + caching + batched | 5.6 | 20 / 17 / 16 |
| 24 | new probes + caching + batched, batch-invariant | 7.7 | 36 / 23 / 17 |
| 26 | S6_as_filed (sequential, no cache, all probes, Opus all games) | 28.0 | 88 |
| 26 | new probes (sequential, no cache) | 26.3 | 69 |
| 26 | new probes + prefix caching (sequential) | 20.8 | 56 |
| 26 | new probes + caching + batched | 6.3 | 22 / 19 / 18 |
| 26 | new probes + caching + batched, batch-invariant | 8.5 | 40 / 25 / 19 |
| 30 | S6_as_filed (sequential, no cache, all probes, Opus all games) | 32.3 | 102 |
| 30 | new probes (sequential, no cache) | 30.3 | 80 |
| 30 | new probes + prefix caching (sequential) | 24.0 | 64 |
| 30 | new probes + caching + batched | 7.2 | 26 / 22 / 20 |
| 30 | new probes + caching + batched, batch-invariant | 9.8 | 46 / 29 / 22 |
| 36 | S6_as_filed (sequential, no cache, all probes, Opus all games) | 38.5 | 122 |
| 36 | new probes (sequential, no cache) | 36.1 | 95 |
| 36 | new probes + prefix caching (sequential) | 28.6 | 76 |
| 36 | new probes + caching + batched | 8.4 | 30 / 26 / 24 |
| 36 | new probes + caching + batched, batch-invariant | 11.5 | 54 / 34 / 26 |
| 48 | S6_as_filed (sequential, no cache, all probes, Opus all games) | 51.3 | 162 |
| 48 | new probes (sequential, no cache) | 48.1 | 127 |
| 48 | new probes + prefix caching (sequential) | 38.1 | 102 |
| 48 | new probes + caching + batched | 11.2 | 41 / 35 / 32 |
| 48 | new probes + caching + batched, batch-invariant | 15.3 | 72 / 45 / 35 |
| 60 | S6_as_filed (sequential, no cache, all probes, Opus all games) | 64.2 | 203 |
| 60 | new probes (sequential, no cache) | 60.1 | 158 |
| 60 | new probes + prefix caching (sequential) | 47.6 | 127 |
| 60 | new probes + caching + batched | 14.0 | 51 / 43 / 39 |
| 60 | new probes + caching + batched, batch-invariant | 19.1 | 90 / 56 / 43 |
| 72 | S6_as_filed (sequential, no cache, all probes, Opus all games) | 77.0 | 244 |
| 72 | new probes (sequential, no cache) | 72.2 | 190 |
| 72 | new probes + prefix caching (sequential) | 57.1 | 153 |
| 72 | new probes + caching + batched | 16.8 | 61 / 52 / 47 |
| 72 | new probes + caching + batched, batch-invariant | 23.0 | 108 / 68 / 52 |
