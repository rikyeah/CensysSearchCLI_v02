```
# Scalability and Orchestration

## Checkpointing and Resumption (SQLite)

- Jobs are identified by a `job_id` (SHA1 hash of index, query, and fields).
- State (cursor, total records) is stored in `--state-db` (default: `./censys_state.sqlite`).
- Automatic resumption occurs if no `--cursor` is provided and state exists.
- Disable with `--no-state`.

### Examples

```bash
# Initial run (saves cursor)
python main.py -q 'services.service_name: HTTP' --pages 5 --page-size 100

# Resume from saved state
python main.py -q 'services.service_name: HTTP' --pages 5 --page-size 100

# Inspect state database
sqlite3 censys_state.sqlite 'select job_id, substr(cursor,1,24)||"...", total, updated_at from job_state;'
```

## Docker

### Build

```bash
docker build -t censys-cli:latest .
```

### Run

```bash
docker run --rm -e CENSYS_API_KEY=$CENSYS_API_KEY \
  -e SITE_USER=$SITE_USER -e SITE_PASS=$SITE_PASS -e TWOCAPTCHA_API_KEY=$TWOCAPTCHA_API_KEY \
  -v "$(pwd)/out:/app/out" -v "$(pwd)/logs:/app/logs" -v "$(pwd)/censys_state.sqlite:/app/censys_state.sqlite" \
  censys-cli:latest -q 'services.service_name: HTTP AND location.country_code: IT' -i hosts --pages 2 --format json
```

## Scheduling

- **Cron**: Schedule container execution via host cron or Kubernetes CronJob.
- **Batch Rotation**: Segment queries by `country_code`, `ASN`, or `domain` to manage API quotas.

## Throughput and Quota Management

- Handles HTTP 429 responses with `Retry-After` and exponential backoff with jitter.
- Use `--pages` and `--page-size` to control batch size and quota consumption.
```