import importlib.util as util
from pathlib import Path
import json

spec = util.spec_from_file_location(
    "scrap_lien_collection",
    Path(__file__).resolve().parents[1] / "scrap_lien_collection.py",
)
slc = util.module_from_spec(spec)
spec.loader.exec_module(slc)


class DummyElement:
    def __init__(self, name, url):
        self._name = name
        self._url = url

    def get_attribute(self, attr):
        if attr == "innerText":
            return self._name
        if attr == "href":
            return self._url
        return None


class DummyDriver:
    def get(self, url):
        self.url = url

    def find_elements(self, by, selector):
        return [DummyElement("A", "/a"), DummyElement("B", "http://b")] 

    def find_element(self, by, selector):
        raise Exception("no next")

    @property
    def current_url(self):
        return "http://example.com"

    def quit(self):
        self.closed = True


class DummyWait:
    def __init__(self, driver, timeout):
        pass

    def until(self, cond):
        return True


class DummyEC:
    @staticmethod
    def presence_of_all_elements_located(locator):
        return lambda d: True


def setup_dummy(monkeypatch):
    monkeypatch.setattr(slc, "setup_driver", lambda: DummyDriver())
    monkeypatch.setattr(slc, "WebDriverWait", DummyWait)
    monkeypatch.setattr(slc, "EC", DummyEC)


def test_output_json(tmp_path, monkeypatch):
    setup_dummy(monkeypatch)
    dest = tmp_path / "out.json"
    slc.scrape_collection("http://example.com", dest, output_format="json")
    data = json.loads(dest.read_text(encoding="utf-8"))
    assert data[0]["name"] == "A"
    assert data[0]["url"] == "http://example.com/a"


def test_output_csv(tmp_path, monkeypatch):
    setup_dummy(monkeypatch)
    dest = tmp_path / "out.csv"
    slc.scrape_collection("http://example.com", dest, output_format="csv")
    lines = dest.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "name,url"
    assert lines[1].startswith("A,http://example.com/a")


def test_output_txt(tmp_path, monkeypatch):
    setup_dummy(monkeypatch)
    dest = tmp_path / "out.txt"
    slc.scrape_collection("http://example.com", dest)
    content = dest.read_text(encoding="utf-8-sig").splitlines()
    assert content[0].startswith("A - http://example.com/a")

