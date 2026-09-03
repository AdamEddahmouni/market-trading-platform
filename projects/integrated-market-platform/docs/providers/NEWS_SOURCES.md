# NewsAPI and Finnhub

NewsAPI and Finnhub are read-only company-news context providers. They are
aggregated with the existing Finviz news export, deduplicated by canonical URL
or normalized headline/date, and retain all contributing providers in
`source_provenance`.

## Configuration

Store keys in the ignored private provider file with the secure prompt:

```powershell
$env:PYTHONPATH = "src"
python tools/news/auth.py configure
```

The command prompts for `NEWSAPI_API_KEY` and `FINNHUB_API_KEY` without echoing
either value. Enable each provider independently:

```text
IMP_NEWSAPI_LIVE=1
IMP_FINNHUB_LIVE=1
```

The `.env.example` file documents these variables. Credentials must not be
placed in source, committed files, URLs in logs, or evidence.

## Validation

Run a bounded live probe after configuring the keys:

```powershell
$env:PYTHONPATH = "src"
python tools/news/probe.py --symbol AAPL
```

The probe writes a sanitized report under `.local/news/`. A provider failure
does not suppress successful Finviz or other provider results. No provider
creates orders or changes execution authority.

NewsAPI uses the `everything` endpoint with a seven-day default window.
Finnhub uses `company-news` with the same bounded window. Results are
current-only unless prospective captures are recorded; neither provider is
treated as a historical point-in-time source retroactively.
