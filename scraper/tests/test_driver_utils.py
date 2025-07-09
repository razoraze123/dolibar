import importlib
from pathlib import Path

import driver_utils

class DummyOptions:
    def __init__(self):
        self.args = []
    def add_argument(self, arg):
        self.args.append(arg)
    def add_experimental_option(self, name, value):
        pass


def test_setup_driver_with_path(tmp_path, monkeypatch):
    chromedriver = tmp_path / "chromedriver"
    chromedriver.write_text("bin")

    calls = {}

    class DummyService:
        def __init__(self, path):
            calls["path"] = path

    class DummyDriver:
        def execute_cdp_cmd(self, *a, **k):
            pass

    class DummyCDM:
        def install(self):
            calls["install"] = True
            return "/tmp/cd"

    monkeypatch.setattr(driver_utils, "Service", DummyService)
    monkeypatch.setattr(driver_utils, "Options", DummyOptions)
    monkeypatch.setattr(driver_utils.webdriver, "Chrome", lambda service, options: DummyDriver(), raising=False)
    monkeypatch.setattr(driver_utils, "ChromeDriverManager", DummyCDM)

    driver = driver_utils.setup_driver(driver_path=str(chromedriver))

    assert isinstance(driver, DummyDriver)
    assert calls["path"] == str(chromedriver)
    assert "install" not in calls


def test_setup_driver_download(monkeypatch):
    calls = {}

    class DummyService:
        def __init__(self, path):
            calls["path"] = path

    class DummyCDM:
        def install(self):
            calls["install"] = True
            return "/tmp/cd"

    class DummyDriver:
        def execute_cdp_cmd(self, *a, **k):
            pass

    monkeypatch.setattr(driver_utils, "Service", DummyService)
    monkeypatch.setattr(driver_utils, "Options", DummyOptions)
    monkeypatch.setattr(driver_utils, "ChromeDriverManager", DummyCDM)
    monkeypatch.setattr(driver_utils.webdriver, "Chrome", lambda service, options: DummyDriver(), raising=False)

    driver = driver_utils.setup_driver(driver_path="/does/not/exist")

    assert isinstance(driver, DummyDriver)
    assert calls["install"] is True
    assert calls["path"] == "/tmp/cd"
