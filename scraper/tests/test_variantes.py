from pathlib import Path
import importlib.util as util

spec = util.spec_from_file_location("moteur_variante", Path(__file__).resolve().parents[1] / "moteur_variante.py")
mv = util.module_from_spec(spec)
spec.loader.exec_module(mv)

class DummyElem:
    def __init__(self, text="v1"):
        self.text = text

class DummyDriver:
    def __init__(self):
        self.closed = False
    def get(self, url):
        self.url = url
    def find_element(self, by, value):
        return DummyElem("Title")
    def find_elements(self, by, value):
        return [DummyElem("Red"), DummyElem("Blue")]
    def quit(self):
        self.closed = True

class DummyWait:
    def __init__(self, driver, timeout):
        pass
    def until(self, cond):
        return True

class DummyEC:
    @staticmethod
    def presence_of_element_located(locator):
        return lambda d: True


def test_extract_variants(monkeypatch):
    monkeypatch.setattr(mv, "WebDriverWait", DummyWait)
    monkeypatch.setattr(mv, "EC", DummyEC)
    monkeypatch.setattr("driver_utils.setup_driver", lambda: DummyDriver())
    monkeypatch.setattr(mv, "setup_driver", lambda: DummyDriver())

    title, variants = mv.extract_variants("https://example.com")
    assert title == "Title"
    assert variants == ["Red", "Blue"]

    tmp = Path("tmp_variants.txt")
    mv.save_to_file(title, variants, tmp)
    assert tmp.read_text(encoding="utf-8").strip() == "Title\tRed, Blue"
    tmp.unlink()


class DummyVariantInput:
    def __init__(self, value, src, selected=False):
        self._value = value
        self._src = src
        self._selected = selected

    def get_attribute(self, name):
        if name == "value":
            return self._value
        if name == "checked":
            return "true" if self._selected else None

    def click(self):
        self._selected = True


class DummyImage:
    def __init__(self, src):
        self.src = src

    def get_attribute(self, name):
        if name == "src":
            return self.src


class DummyVariantContainer:
    def __init__(self, inputs):
        self.inputs = inputs

    def find_elements(self, by, value):
        return self.inputs


class DummyDriverImages:
    def __init__(self):
        self.closed = False
        self.inputs = [
            DummyVariantInput("Red", "red.png", selected=True),
            DummyVariantInput("Blue", "blue.png"),
        ]
        self.image = DummyImage("red.png")
        self.container = DummyVariantContainer(self.inputs)

    def get(self, url):
        self.url = url

    def find_element(self, by, value):
        if value == "h1":
            return DummyElem("Title")
        if value == ".variant-picker__option-values":
            return self.container
        if value == ".product-gallery__media.is-selected img":
            return self.image

    def execute_script(self, script, elem):
        self.image.src = elem._src
        elem.click()

    def quit(self):
        self.closed = True


class DummyWait2:
    def __init__(self, driver, timeout):
        self.driver = driver

    def until(self, cond):
        return cond(self.driver)


def test_extract_variants_with_images(monkeypatch):
    driver = DummyDriverImages()
    monkeypatch.setattr(mv, "WebDriverWait", DummyWait2)
    monkeypatch.setattr(mv, "EC", DummyEC)
    monkeypatch.setattr("driver_utils.setup_driver", lambda: driver)
    monkeypatch.setattr(mv, "setup_driver", lambda: driver)
    monkeypatch.setattr(mv.time, "sleep", lambda x: None)

    title, mapping = mv.extract_variants_with_images("https://example.com")
    assert title == "Title"
    assert mapping == {"Red": "red.png", "Blue": "blue.png"}

    tmp = Path("tmp_images.txt")
    mv.save_images_to_file(title, mapping, tmp)
    assert tmp.read_text(encoding="utf-8").strip().splitlines() == [
        "Title",
        "Red : red.png",
        "Blue : blue.png",
    ]
    tmp.unlink()
