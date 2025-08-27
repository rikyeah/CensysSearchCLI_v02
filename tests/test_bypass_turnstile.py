"""
Unit tests for bypass_turnstile.py.
Covers passive wait, PoW bypass, 2Captcha fallback, and error cases.
"""
import pytest
from unittest.mock import Mock, patch
try:
    from playwright.sync_api import Page, TimeoutError  # type: ignore
except ImportError:
    Page = None  # type: ignore
    TimeoutError = Exception  # type: ignore
    pytest.skip("playwright is not installed; skipping bypass_turnstile tests", allow_module_level=True)
from censys_cli import bypass_turnstile

def test_bypass_turnstile_auto_resolved():
    """Test auto-resolution of Turnstile CAPTCHA."""
    page = Mock(spec=Page)
    page.frame_locator.return_value.locator.return_value.is_visible.side_effect = TimeoutError
    page.input_value.return_value = "mock_token"
    
    bypass_turnstile.bypass_turnstile(page)
    
    page.input_value.assert_called_once_with('input[name="cf-turnstile-response"]', timeout=10000)

@patch('censys_cli.bypass_turnstile.attempt_pow_bypass')
def test_bypass_turnstile_pow_success(mock_pow):
    """Test successful PoW bypass."""
    page = Mock(spec=Page)
    page.frame_locator.return_value.locator.return_value.is_visible.return_value = True
    page.input_value.side_effect = ["", "mock_token"]
    mock_pow.return_value = True
    
    bypass_turnstile.bypass_turnstile(page)
    
    mock_pow.assert_called_once_with(page)

@patch('censys_cli.bypass_turnstile.attempt_pow_bypass')
@patch('censys_cli.bypass_turnstile.TwoCaptcha')
def test_bypass_turnstile_2captcha_fallback(mock_twocaptcha, mock_pow):
    """Test 2Captcha fallback when PoW fails."""
    page = Mock(spec=Page)
    page.frame_locator.return_value.locator.return_value.is_visible.return_value = True
    page.input_value.return_value = ""
    page.locator.return_value.get_attribute.return_value = "mock_sitekey"
    mock_pow.return_value = False
    mock_solver = Mock()
    mock_solver.turnstile.return_value = {"code": "mock_token"}
    mock_twocaptcha.return_value = mock_solver
    
    with patch.dict('os.environ', {'TWOCAPTCHA_API_KEY': 'test_key'}):
        bypass_turnstile.bypass_turnstile(page)
    
    mock_twocaptcha.assert_called_once_with('test_key')
    mock_solver.turnstile.assert_called_once_with(sitekey="mock_sitekey", url=page.url)
    page.evaluate.assert_called_once()

def test_bypass_turnstile_no_api_key():
    """Test error handling for missing 2Captcha API key."""
    page = Mock(spec=Page)
    page.frame_locator.return_value.locator.return_value.is_visible.return_value = True
    page.input_value.return_value = ""
    
    with pytest.raises(ValueError, match="TWOCAPTCHA_API_KEY not set."):
        with patch.dict('os.environ', {}, clear=True):
            bypass_turnstile.bypass_turnstile(page)