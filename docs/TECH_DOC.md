```
# Technical Notes

## Compliance Rationale: API vs. Scraping

- **Terms of Service**: Official APIs ensure authorised access, avoiding potential ToS violations from scraping.
- **Stability**: API schemas and pagination are versioned, unlike volatile HTML structures.
- **Rate Limits**: Proper handling of HTTP 429 and `Retry-After` ensures predictable throughput.
- **Auditability**: Authentication headers and structured logging enable traceability.

## Architecture

- **Transport**: Uses `requests` with timeouts and bounded retry/backoff (exponential with jitter).
- **Authentication**: Supports Bearer (`CENSYS_API_KEY`) or Basic (`CENSYS_API_ID/SECRET`).
- **Indexes**: Supports `hosts` and `certificates` with cursor-based pagination.
- **CLI**: Built with `argparse`, validates `page-size`, `index`, and `query`.
- **Output**:
  - NDJSON for lossless data ingestion.
  - CSV with deterministic flattening (dot notation, list indices) or explicit `--fields`.
- **Observability**: Structured JSON logs (`logs/run_<ts>.log`) and concise stderr logs (`--verbose`).
- **ML Integration**: Random Forest model (`ml_predictor.py`) predicts optimal CAPTCHA bypass method when `--ml-predict` is enabled.

## Usage Examples

### Queries

- **By Country**: `services.service_name: HTTP AND location.country_code: IT`
- **By ASN**: `autonomous_system.asn: 3356 AND services.service_name: HTTPS`
- **By Service**: `services.service_name: SSH AND services.port: 22`
- **By Domain**: `dns.names: "example.org"`

### Commands

```bash
# Hosts in Italy (NDJSON)
python main.py -q 'services.service_name: HTTP AND location.country_code: IT' -i hosts --format json -o out/it_http.ndjson

# SSH hosts (CSV, specific fields)
python main.py -q 'services.service_name: SSH' -i hosts --format csv --fields ip,location.country_code,services[0].port -o out/ssh.csv

# Certificates (first 2 pages)
python main.py -q 'subject_dn: "CN=example.org"' -i certificates --pages 2 --page-size 100

# ML-predicted bypass
python main.py -q 'services.service_name: HTTP' --force-browser --ml-predict
```