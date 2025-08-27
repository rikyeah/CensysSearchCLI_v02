#!/usr/bin/env python3
"""
Standalone script to bypass Cloudflare Turnstile CAPTCHA on https://search.censys.io/.
Supports passive wait, Proof‑of‑Work (PoW) bypass with cloudscraper, and 2Captcha fallback.
Designed for automated fallback with robust error handling and analytics.
"""
import os
import json
from datetime import datetime
import pathlib
from playwright.sync_api import sync_playwright, TimeoutError
from twocaptcha import TwoCaptcha
import cloudscraper
from .analytics import Analytics

def attempt_pow_bypass(page):
    """
    Attempt Proof‑of‑Work (PoW) bypass using cloudscraper.

    Parameters
    ----------
    page : Playwright Page
        The page where the CAPTCHA is presented.

    Returns
    -------
    bool
        True if PoW bypass succeeds, False otherwise.
    """
    try:
        scraper = cloudscraper.create_scraper()
        # Attempt to fetch the page to trigger PoW; success if no CAPTCHA is presented
        scraper.get("https://search.censys.io/")
        token = page.input_value('input[name="cf-turnstile-response"]')
        return bool(token)
    except Exception:
        return False

def bypass_turnstile(page, analytics: Analytics = None):
    """
    Bypass Cloudflare Turnstile CAPTCHA using passive wait, PoW bypass, or 2Captcha fallback.

    Parameters
    ----------
    page : Playwright Page
        The page where the CAPTCHA is presented.
    analytics : Optional[Analytics]
        Collector for CAPTCHA bypass metrics.

    Raises
    ------
    ValueError
        If required environment variables for 2Captcha are missing.
    """
    try:
        # Try passive wait for automatic token generation
        page.input_value('input[name="cf-turnstile-response"]', timeout=10000)
        if analytics:
            analytics.log_success("passive", 0)
        return
    except TimeoutError:
        pass  # token not auto-resolved

    # Attempt PoW bypass
    if attempt_pow_bypass(page):
        if analytics:
            analytics.log_success("pow", 0)
        return

    # Fallback to 2Captcha
    api_key = os.environ.get("TWOCAPTCHA_API_KEY")
    if not api_key:
        raise ValueError("TWOCAPTCHA_API_KEY not set.")
    solver = TwoCaptcha(api_key)
    # Extract sitekey from page
    sitekey = page.locator('iframe[src*="challenges.cloudflare.com"]').get_attribute("src").split("k=")[-1]
    result = solver.turnstile(sitekey=sitekey, url=page.url)
    token = result.get("code")
    page.evaluate('''(token) => {
        document.querySelector('input[name="cf-turnstile-response"]').value = token;
    }''', token)
    if analytics:
        analytics.log_success("2captcha", 0)