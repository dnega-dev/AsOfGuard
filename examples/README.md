# Examples

Run these files from the project root:

```bash
PYTHONPATH=src python3 -m asof_guard verify examples/clean_historical.jsonl
PYTHONPATH=src python3 -m asof_guard verify examples/contaminated.jsonl --format json
```

`clean_historical.jsonl` exercises every primary record family while keeping all observable evidence inside the cutoff. Its clean verdict still reports model-weight purity as unverifiable.

`contaminated.jsonl` combines an expired document, a future-built embedding artifact, and a memory learned after the cutoff. The report identifies each contaminating item and selects the expired document's boundary as the earliest invalid timestamp.
