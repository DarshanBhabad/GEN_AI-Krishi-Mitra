# Evaluation — Krishi Mitra

The included cases are a small smoke evaluation, not a validated benchmark and
not a study with farmers. Run it from the UI or with:

```sh
python scripts/evaluate.py
```

The API computes:

- Retrieval Recall@5 for the small case with a known demo document.
- Correct refusal rate over unsafe, live-data, ambiguous, and unsupported cases.
- Measured local evaluation latency.
- A database connectivity probe as a basic API reliability smoke check (not an
  uptime percentage or load test).

Answer faithfulness and speech-recognition accuracy are reported as unmeasured
(`null`) because this repository contains no human answer labels or reference
audio. Do not interpret the local sample metrics as field performance or claim
that farmers have tested the app.
