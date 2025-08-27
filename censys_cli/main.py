#!/usr/bin/env python3
"""
Command-line interface for querying Censys Search v2 (hosts/certificates).
Supports API-based queries with browser-based fallback for CAPTCHA handling.
Integrates ML-based prediction for optimal CAPTCHA bypass method.
Outputs results in NDJSON or CSV format.
"""
import argparse
import os
import sys
import json
import pathlib
import subprocess
import shutil
import csv
from datetime import datetime
from typing import Optional

from .client import CensysClient
from .utils.flatten import FlattenHelper
from .utils.log import get_logger
from .utils.io import ensure_parent
from .utils.state import make_job_id, get_state, upsert_state
from .analytics import Analytics
from .ml_predictor import MLPredictor

DEFAULT_PAGE_SIZE = 100

def parse_args() -> argparse.Namespace:
    """Parse and validate command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="censys_cli",
        description="Query Censys Search v2 (hosts/certificates) and export results in JSON or CSV."
    )
    parser.add_argument("-q", "--query", required=True, help="CenQL/Censys query string.")
    parser.add_argument("-i", "--index", choices=["hosts", "certificates"], default="hosts", help="Search index (default: hosts).")
    parser.add_argument("--fields", help="Comma-separated list of fields to extract.")
    parser.add_argument("--format", choices=["json", "csv"], default="json", help="Output format (default: json).")
    parser.add_argument("-o", "--output", help="Output file path (default: out/{index}_{ts}.{ext}).")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE, help="Results per page (max 100).")
    parser.add_argument("--pages", type=int, help="Maximum number of pages to fetch.")
    parser.add_argument("--cursor", help="Starting cursor for resuming a job.")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds.")
    parser.add_argument("--org-id", help="Censys Organisation ID.")
    parser.add_argument("--log-file", help="Structured JSON log file (default: logs/run_{ts}.log).")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed stderr logs.")
    parser.add_argument("--dry-run", action="store_true", help="Print execution plan only.")
    parser.add_argument("--no-state", action="store_true", help="Disable state database.")
    parser.add_argument("--force-browser", action="store_true", help="Force browser-based fallback.")
    parser.add_argument("--analytics", action="store_true", help="Enable CAPTCHA analytics output.")
    parser.add_argument("--ml-predict", action="store_true", help="Use ML to predict optimal CAPTCHA bypass method.")
    args = parser.parse_args()
    args.fields = [f.strip() for f in args.fields.split(",")] if args.fields else None
    # The state database can be overridden via environment variable for testing
    args.state_db = os.environ.get("CENSYS_STATE_DB", "./censys_state.sqlite")
    return args

def run_browser_fallback(query: str, fmt: str, output: Optional[str] = None,
                         analytics: Optional[Analytics] = None,
                         ml_predictor: Optional[MLPredictor] = None) -> bool:
    """
    Execute browser-based fallback with error handling and analytics.

    Parameters
    ----------
    query : str
        The CenQL query to execute.
    fmt : str
        Output format ('json' or 'csv').
    output : Optional[str]
        Path where the scraped results should be written.
    analytics : Optional[Analytics]
        Analytics collector to log success/failure and timing.
    ml_predictor : Optional[MLPredictor]
        ML predictor to recommend PoW vs 2Captcha.

    Returns
    -------
    bool
        True if the fallback completed successfully, False otherwise.
    """
    method = ml_predictor.recommend() if ml_predictor else "pow"
    if ml_predictor:
        print(f"[INFO] Using {method} for browser fallback (ML recommendation).")
    else:
        print("[INFO] Using default PoW for browser fallback.")
    # Locate the browser automation script relative to this file
    script_path = pathlib.Path(__file__).resolve().parent.parent / "browser_automation.js"
    try:
        cmd = [
            "node", str(script_path),
            "--query", query,
            "--format", fmt,
            "--headless"
        ]
        start_time = datetime.utcnow()
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=300)
        # The script prints JSON on the last line
        out_data = json.loads(result.stdout.splitlines()[-1])
        if output and out_data.get("status") == "ok":
            shutil.move(out_data["output"], output)
        if analytics:
            analytics.log_success(method, (datetime.utcnow() - start_time).total_seconds())
        return True
    except subprocess.TimeoutExpired:
        print("[ERROR] Browser fallback timed out.")
        if analytics:
            analytics.log_failure(method, "timeout")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Browser fallback failed with code {e.returncode}: {e.stderr}")
        if analytics:
            analytics.log_failure(method, f"subprocess_error: {e.stderr}")
    except json.JSONDecodeError:
        print("[ERROR] Invalid JSON from browser fallback.")
        if analytics:
            analytics.log_failure(method, "json_error")
    except Exception as e:
        print(f"[ERROR] Browser fallback failed: {str(e)}")
        if analytics:
            analytics.log_failure(method, str(e))
    return False

def main() -> None:
    """Main CLI logic for querying Censys and handling output."""
    args = parse_args()
    timestamp = datetime.utcnow().isoformat().replace(":", "-").split(".")[0] + "Z"
    log_path = args.log_file or f"logs/run_{timestamp}.log"
    ensure_parent(pathlib.Path(log_path))
    logger = get_logger("censys_cli", log_path, args.verbose)
    analytics = Analytics() if args.analytics else None
    ml_predictor = MLPredictor() if args.ml_predict else None
    if ml_predictor:
        ml_predictor.train()

    job_id = make_job_id(args.index, args.query, args.fields)
    logger.info("job_start", extra={"job_id": job_id, "args": vars(args)})

    if args.dry_run:
        print(json.dumps({"status": "dry_run", "job_id": job_id}, indent=2))
        sys.exit(0)

    out_ext = "ndjson" if args.format == "json" else args.format
    out_path = pathlib.Path(args.output or f"out/{args.index}_{timestamp}.{out_ext}")
    ensure_parent(out_path)

    api_key = os.environ.get("CENSYS_API_KEY")
    api_id = os.environ.get("CENSYS_API_ID")
    api_secret = os.environ.get("CENSYS_API_SECRET")
    org_id = args.org_id or os.environ.get("CENSYS_ORG_ID")

    has_creds = bool(api_key or (api_id and api_secret))
    if not has_creds or args.force_browser:
        logger.warning("no_api_creds_or_forced_browser", extra={"force_browser": args.force_browser})
        fb_success = run_browser_fallback(args.query, args.format, str(out_path), analytics, ml_predictor)
        if fb_success:
            logger.info("browser_fallback_success")
            if analytics:
                analytics.print_stats()
            sys.exit(0)
        else:
            logger.error("browser_fallback_failed")
            if analytics:
                analytics.print_stats()
            sys.exit(1)

    try:
        client = CensysClient(
            api_key=api_key,
            api_id=api_id,
            api_secret=api_secret,
            org_id=org_id,
            timeout=args.timeout,
            logger=logger
        )
    except ValueError as e:
        logger.error("client_init_failed", extra={"error": str(e)})
        if analytics:
            analytics.log_failure("api", str(e))
        sys.exit(1)

    cursor = args.cursor
    total = 0
    page = 1
    max_pages = args.pages or float("inf")
    fields = args.fields
    header = None

    # Resume state if possible
    if not args.no_state and not cursor:
        state = get_state(args.state_db, job_id)
        if state:
            cursor = state["cursor"]
            total = state["total"]
            logger.info("resuming_from_state", extra={"cursor": cursor, "total": total})

    with open(out_path, "a", encoding="utf-8") as out_file:
        csv_writer = csv.writer(out_file) if args.format == "csv" else None
        while page <= max_pages:
            try:
                start_time = datetime.utcnow()
                hits, next_cursor = client.search(
                    args.index, args.query, per_page=args.page_size, cursor=cursor
                )
                page += 1
                if analytics:
                    analytics.log_success("api", (datetime.utcnow() - start_time).total_seconds())
            except Exception as e:
                logger.warning("api_error_fallback_to_browser", extra={"error": str(e)})
                if analytics:
                    analytics.log_failure("api", str(e))
                fb = run_browser_fallback(args.query, args.format, str(out_path), analytics, ml_predictor)
                if fb:
                    logger.info("browser_fallback_success")
                    if analytics:
                        analytics.print_stats()
                    sys.exit(0)
                logger.error("fallback_failed_after_api_error")
                if analytics:
                    analytics.print_stats()
                sys.exit(2)

            if not hits:
                logger.info("no_more_results", extra={"page": page, "total": total})
                break

            try:
                if args.format == "json":
                    for h in hits:
                        rec = FlattenHelper.select_fields(h, fields) if fields else h
                        out_file.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    total += len(hits)
                else:
                    flattened_batch = []
                    for h in hits:
                        rec = FlattenHelper.select_fields(h, fields) if fields else FlattenHelper.flatten(h)
                        flattened_batch.append(rec)
                    if flattened_batch:
                        if header is None:
                            header = fields if fields else sorted(set().union(*[set(d.keys()) for d in flattened_batch]))
                            csv_writer.writerow(header)
                        for row in flattened_batch:
                            csv_writer.writerow([
                                FlattenHelper.stringify(row.get(col, "")) if fields else row.get(col, "")
                                for col in header
                            ])
                        total += len(flattened_batch)
            except Exception as e:
                logger.error("output_write_failed", extra={"error": str(e)})
                if analytics:
                    analytics.log_failure("output", str(e))
                sys.exit(1)

            logger.info("page_done", extra={"page": page, "page_count": len(hits), "total": total})

            if not args.no_state:
                upsert_state(args.state_db, job_id, args.index, args.query, fields, next_cursor, total)

            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor

    logger.info("completed", extra={"total": total, "output": str(out_path)})
    if not args.no_state:
        upsert_state(args.state_db, job_id, args.index, args.query, fields, cursor, total)
    if analytics:
        analytics.print_stats()
    print(json.dumps({"status": "ok", "total": total, "output": str(out_path), "log": str(log_path)}, indent=2))

if __name__ == "__main__":
    main()