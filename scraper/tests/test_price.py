import importlib.util as util
from pathlib import Path

spec = util.spec_from_file_location(
    "scrap_prix_produit",
    Path(__file__).resolve().parents[1] / "scrap_prix_produit.py",
)
sp = util.module_from_spec(spec)
spec.loader.exec_module(sp)


class DummyElement:
    def get_attribute(self, name):
        return " 42 \u20ac " if name == "innerText" else None


class DummyDriver:
    def get(self, url):
        self.url = url

    def find_element(self, by, value):
        return DummyElement()

    def quit(self):
        self.closed = True


class DummyWait:
    def __init__(self, driver, timeout):
        pass

    def until(self, condition):
        return True


class DummyEC:
    @staticmethod
    def presence_of_element_located(locator):
        return lambda d: True


def test_extract_price(monkeypatch):
    monkeypatch.setattr(sp, "WebDriverWait", DummyWait)
    monkeypatch.setattr(sp, "EC", DummyEC)
    monkeypatch.setattr("driver_utils.setup_driver", lambda: DummyDriver())
    monkeypatch.setattr(sp, "setup_driver", lambda: DummyDriver())

    price = sp.extract_price("https://example.com", "span")
    assert price == "42 \u20ac"


def test_save_price_to_file(tmp_path):
    dest = tmp_path / "price.txt"
    sp.save_price_to_file("10", dest)
    assert dest.exists()
    assert dest.read_text(encoding="utf-8") == "10"
