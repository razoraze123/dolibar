from __future__ import annotations

"""Utility helpers for Selenium WebDriver management."""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from pathlib import Path
import json


def setup_driver(headless: bool | None = None, driver_path: str | None = None) -> webdriver.Chrome:
    """Return a configured Chrome WebDriver.

    Parameters
    ----------
    headless: bool | None
        Run Chrome in headless mode if True. If ``None``, the value is
        loaded from the settings file and defaults to ``True``.
    driver_path: optional str
        Path to a ChromeDriver binary to use. If absent or invalid,
        ``webdriver_manager`` is used to download a driver.
    """
    driver_path = driver_path or _load_driver_path_from_settings()
    if headless is None:
        headless = _load_headless_from_settings()

    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--disable-logging")
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-blink-features=AutomationControlled")

    if driver_path and Path(driver_path).is_file():
        service = Service(str(driver_path))
    else:
        service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # Hide webdriver flag
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver


def _load_headless_from_settings() -> bool:
    """Return headless flag from settings.json if available."""
    settings_file = Path("settings.json")
    if settings_file.is_file():
        try:
            data = json.loads(settings_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "headless" in data:
                return bool(data["headless"])
        except Exception:
            pass
    return True


def _load_driver_path_from_settings() -> str | None:
    """Return driver path from settings.json if available."""
    settings_file = Path("settings.json")
    if settings_file.is_file():
        try:
            data = json.loads(settings_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data.get("driver_path")
        except Exception:
            pass
    return None
