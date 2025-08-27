```
# Censys Search CLI

A command-line interface (CLI) for querying Censys Search v2 (`hosts` or `certificates`) using official APIs, with a browser-based fallback to bypass Cloudflare Turnstile CAPTCHA on https://search.censys.io/. Integrates ML-based prediction for optimal CAPTCHA bypass. Outputs results in NDJSON or CSV format. Designed for compliance, scalability, and robustness with comprehensive error handling and analytics.

## Project Structure
```
CensysSearchCLI_v1/
├── browser_automation.js
├── bypass_turnstile.py
├── Dockerfile
├── LICENSE
├── main.py
├── package.json
├── README.md
├── requirements.txt
├── censys_cli/
│   ├── __init__.py
│   ├── analytics.py
│   ├── client.py
│   ├── ml_predictor.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── flatten.py
│   │   ├── io.py
│   │   ├── log.py
│   │   ├── state.py
├── docs/
│   ├── BYPASS.md
│   ├── SCALING.md
│   ├── TECH_DOC.md
├── tests/
│   ├── test_browser_automation.js
│   ├── test_bypass_turnstile.py
│   ├── test_main.py
│   ├── test_ml_predictor.py
├── out/                     # run-time created
├── logs/                    # run-time created
└── analytics.sqlite         # run-time created

```

## Setup

1. **Install Dependencies**
   ```bash
   python -m venv .venv && . .venv/bin/activate
   pip install -r requirements.txt
   playwright install  # Installs Chromium for browser automation
   npm install  # Installs Node.js dependencies
```

2. **Configure Environment Variables:** Set the following in your shell or `.env` file:

   ```bash
   # Censys API credentials (choose one)
   export CENSYS_API_KEY="your_pat_key"  # Preferred: Bearer token
   # OR
   export CENSYS_API_ID="your_id"
   export CENSYS_API_SECRET="your_secret"
   
   # Optional: Organisation ID
   export CENSYS_ORG_ID="your_org_id"
   
   # For browser fallback login (if required)
   export SITE_USER="your_email"
   export SITE_PASS="your_password"
   
   # For Turnstile CAPTCHA bypass (2Captcha fallback)
   export TWOCAPTCHA_API_KEY="your_2captcha_key"
   ```

3. **Verify Installation:** Ensure Python 3.8+, Node.js 20+, and SQLite are installed:

   ```bash
   python --version
   node --version
   sqlite3 --version
   ```

## Usage

Run API-based queries, browser fallback, or ML-predicted CAPTCHA bypass:

```bash
# Query hosts (NDJSON output)
python main.py -q 'services.service_name: HTTP AND location.country_code: IT' -i hosts --format json -o out/it_http.ndjson

# Query hosts (CSV output, specific fields)
python main.py -q 'services.service_name: SSH' -i hosts --format csv --fields ip,location.country_code,services[0].port -o out/ssh.csv

# Limit to 3 pages
python main.py -q 'location.country_code: DE' --pages 3 --page-size 100

# Resume from cursor
python main.py -q 'services.service_name: HTTP' --cursor "eyJwYWdlIjoxfQ=="

# Force browser fallback
python main.py -q 'services.service_name: HTTP AND location.country_code: IT' --force-browser

# Use ML prediction for bypass
python main.py -q 'services.service_name: HTTP' --force-browser --ml-predict

# Standalone Turnstile bypass
python bypass_turnstile.py

# Enable analytics
python main.py -q 'services.service_name: HTTP' --force-browser --analytics
```

## Options

- `-q/--query` (required): CenQL query string.
- `-i/--index`: `hosts` | `certificates` (default: `hosts`).
- `--fields`: Comma-separated fields (supports dot notation, e.g., `services[0].port`).
- `--format`: `json` (NDJSON) | `csv` (flattened, default: `json`).
- `-o/--output`: Output file path (default: `out/{index}_{timestamp}.{ext}`).
- `--page-size`: Results per page (max 100, default: 100).
- `--pages`: Maximum pages to fetch.
- `--cursor`: Resume from a specific cursor.
- `--timeout`: HTTP timeout in seconds (default: 30).
- `--org-id`: Censys Organisation ID.
- `--log-file`: Structured JSON log file (default: `logs/run_{timestamp}.log`).
- `--verbose`: Enable detailed logs.
- `--dry-run`: Print execution plan without running.
- `--no-state`: Disable state persistence.
- `--force-browser`: Force browser-based fallback.
- `--analytics`: Display CAPTCHA bypass analytics.
- `--ml-predict`: Use ML to predict optimal CAPTCHA bypass method.

## ML Prediction

The `--ml-predict` flag enables a Random Forest model to recommend the optimal CAPTCHA bypass method (PoW or 2Captcha) based on historical data in `analytics.sqlite`. Features include:

- IP reputation (inferred from proxy or historical data).
- User-agent.
- Response time.
- Error types.

The model outputs probabilities for each method and selects the best one for browser fallback.

## Running Tests

Unit tests ensure code reliability:

```bash
# Python tests
pytest tests/

# Node.js tests
npm test
```

## Docker

Build and run in a container for scalability:

```bash
# Build
docker build -t censys-cli:latest .

# Run
docker run --rm -e CENSYS_API_KEY=$CENSYS_API_KEY \
  -e SITE_USER=$SITE_USER -e SITE_PASS=$SITE_PASS -e TWOCAPTCHA_API_KEY=$TWOCAPTCHA_API_KEY \
  -v "$(pwd)/out:/app/out" -v "$(pwd)/logs:/app/logs" -v "$(pwd)/censys_state.sqlite:/app/censys_state.sqlite" \
  censys-cli:latest -q 'services.service_name: HTTP AND location.country_code: IT' -i hosts --pages 2 --format json
```

## Turnstile CAPTCHA Bypass

The browser fallback (`browser_automation.js`) and standalone script (`bypass_turnstile.py`) bypass Cloudflare Turnstile CAPTCHA without human interaction:

- **Methods**: Passive wait (auto-resolution), Proof-of-Work (PoW) via browser context or `cloudscraper`, 2Captcha fallback.
- **Tools**: Playwright, cloudscraper, 2Captcha, Chrome DevTools.
- **Details**: See `docs/BYPASS.md`.

## Analytics

Enable with `--analytics` to track CAPTCHA bypass metrics (success rate, response time) in `analytics.sqlite`. Outputs a table with recommendations for optimal bypass method.

## FAQ

- **Why does the PoW bypass fail?**
  - Possible headless detection or IP reputation issues. Try `--no-headless` or a proxy (see `docs/SCALING.md`).
- **What if TWOCAPTCHA_API_KEY is not set?**
  - The script will attempt PoW bypass or fail with a clear error. Obtain a key from https://2captcha.com/.
- **How to debug failures?**
  - Check `logs/run_{timestamp}.log` for structured JSON logs. Enable `--verbose` for detailed stderr output.
- **How to scale the CLI?**
  - See `docs/SCALING.md` for proxy rotation, multi-instance deployment, and queue systems.

## Security Notes

- Store secrets in environment variables or a secret manager.
- Rotate API keys regularly and use least-privilege scopes.
- Ensure compliance with Censys Terms of Service when using APIs.

## License

MIT (see `LICENSE`).

```
