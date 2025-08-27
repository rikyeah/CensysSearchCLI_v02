"""
Integration tests for the CLI entry points.

These tests verify the argument parser and ensure that running the CLI
with ``--dry-run`` exits early without invoking network calls. Because
API calls require live credentials and network access, we rely on mocks
to simulate success conditions.
"""
import os
import sys
from unittest import mock

import pytest

from censys_cli import main as cli_main


def test_parse_args_defaults():
    """Ensure default values are set when optional arguments are omitted."""
    # Simulate command line: only query provided
    test_argv = ["prog", "-q", "services.service_name: HTTP"]
    with mock.patch.object(sys, "argv", test_argv):
        args = cli_main.parse_args()
    assert args.query == "services.service_name: HTTP"
    assert args.index == "hosts"
    assert args.format == "json"
    # fields should be None when not supplied
    assert args.fields is None
    # state_db should default to local file unless env var overrides
    assert args.state_db == "./censys_state.sqlite"


def test_parse_args_custom():
    """Verify that custom arguments are parsed correctly."""
    test_argv = [
        "prog",
        "-q",
        "foo",
        "-i",
        "certificates",
        "--format",
        "csv",
        "--page-size",
        "50",
        "--pages",
        "2",
        "--fields",
        "ip,location.country_code",
    ]
    with mock.patch.object(sys, "argv", test_argv):
        args = cli_main.parse_args()
    assert args.query == "foo"
    assert args.index == "certificates"
    assert args.format == "csv"
    assert args.page_size == 50
    assert args.pages == 2
    assert args.fields == ["ip", "location.country_code"]


def test_main_dry_run():
    """Running with --dry-run should exit without calling the API or browser."""
    test_argv = ["prog", "-q", "dummy", "--dry-run"]
    with mock.patch.object(sys, "argv", test_argv):
        # Mock out CensysClient and browser fallback to ensure they are not called
        with mock.patch("censys_cli.main.CensysClient") as mock_client:
            with mock.patch("censys_cli.main.run_browser_fallback") as mock_browser:
                with pytest.raises(SystemExit):
                    cli_main.main()
        mock_client.assert_not_called()
        mock_browser.assert_not_called()


def test_main_api_invocation(tmp_path):
    """Ensure that the API client is invoked and output is written when not dry-run."""
    # Set up environment and temporary output
    tmp_output = tmp_path / "out.json"
    test_argv = ["prog", "-q", "dummy", "--format", "json", "-o", str(tmp_output)]
    # Provide fake API key so that CLI attempts API path
    os.environ["CENSYS_API_KEY"] = "dummy"
    with mock.patch.object(sys, "argv", test_argv):
        # Mock the CensysClient.search method to return a synthetic response
        fake_client = mock.MagicMock()
        fake_client.search.return_value = ({"hits": [{"ip": "1.2.3.4"}]}, None)
        with mock.patch("censys_cli.main.CensysClient", return_value=fake_client):
            cli_main.main()
        # After execution, the file should exist and contain JSON lines
        assert tmp_output.exists()
        contents = tmp_output.read_text().strip().split("\n")
        assert contents  # at least one line
