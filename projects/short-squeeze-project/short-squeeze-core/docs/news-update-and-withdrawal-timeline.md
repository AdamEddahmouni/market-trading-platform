# News Update and Withdrawal Timeline

The committed Phase 1G timeline uses 12 compatible Phase 1F observations plus three immutable `TESTA` news observations:

1. Original publication at 14:00, provider availability at 14:01, and local receipt at 14:02 UTC.
2. Update at 14:20, provider availability at 14:20:30, and local receipt at 14:21 UTC.
3. Withdrawal availability at 15:00 and local receipt at 15:01 UTC.

Six `as_of` boundaries prove that publication/availability cannot bypass receipt, an update cannot rewrite an earlier bundle, and withdrawal remains an additional lifecycle fact rather than deleting history.

```powershell
.\.venv\Scripts\python.exe -m squeeze_core build-evidence-timeline --input tests\fixtures\evidence\normalized_phase_1g_point_in_time.jsonl --symbol TESTA --as-of-file tests\fixtures\evidence\news_availability_timeline.json
```

