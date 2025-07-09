import sys
import types
from pathlib import Path
import importlib.util as util

class DummySignal:
    def __init__(self, *args, **kwargs):
        self._cbs = []
    def connect(self, cb):
        self._cbs.append(cb)
    def emit(self, *a, **k):
        for cb in self._cbs:
            cb(*a, **k)

class DummyWidget:
    def __init__(self, *args, **kwargs):
        pass

class DummyTextEdit:
    def __init__(self, *args, **kwargs):
        self._text = ""
    def append(self, txt):
        self._text += txt + "\n"
    def clear(self):
        self._text = ""
    def toPlainText(self):
        return self._text
    def setText(self, txt):
        self._text = txt

class DummyLineEdit:
    def __init__(self, txt=""):
        self._text = txt
    def setPlaceholderText(self, txt):
        pass
    def text(self):
        return self._text
    def setText(self, txt):
        self._text = txt

class DummyButton:
    def __init__(self, *args, **kwargs):
        self.clicked = DummySignal()

    def setEnabled(self, state):
        self.enabled = state

class DummyLayout:
    def __init__(self, *args, **kwargs):
        pass
    def addWidget(self, *args, **kwargs):
        pass
    def addLayout(self, *args, **kwargs):
        pass

class DummyLabel:
    def __init__(self, *args, **kwargs):
        pass

class DummyFileDialog:
    @staticmethod
    def getSaveFileName(*a, **k):
        return "", ""

class DummyMessageBox:
    last = []

    @staticmethod
    def critical(parent, title, text):
        DummyMessageBox.last.append(("critical", title, text))

    @staticmethod
    def warning(parent, title, text):
        DummyMessageBox.last.append(("warning", title, text))

    @staticmethod
    def information(parent, title, text):
        DummyMessageBox.last.append(("information", title, text))

def setup_pyside(monkeypatch):
    qtwidgets = types.ModuleType("PySide6.QtWidgets")
    for name, cls in {
        "QWidget": DummyWidget,
        "QVBoxLayout": DummyLayout,
        "QHBoxLayout": DummyLayout,
        "QLabel": DummyLabel,
        "QLineEdit": DummyLineEdit,
        "QPushButton": DummyButton,
        "QTextEdit": DummyTextEdit,
        "QMessageBox": DummyMessageBox,
        "QFileDialog": DummyFileDialog,
    }.items():
        setattr(qtwidgets, name, cls)

    class DummyThread:
        def __init__(self, *a, **k):
            self.started = DummySignal()
            self.finished = DummySignal()

        def start(self):
            self.started.emit()

        def quit(self):
            self.finished.emit()

        def wait(self):
            pass

        def deleteLater(self):
            pass

    class DummyQObject:
        def __init__(self, *a, **k):
            pass

        def moveToThread(self, thread):
            self._thread = thread

        def deleteLater(self):
            pass

    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.Qt = types.SimpleNamespace()
    qtcore.QThread = DummyThread
    qtcore.Signal = DummySignal
    qtcore.QObject = DummyQObject

    pyside = types.ModuleType("PySide6")
    pyside.QtWidgets = qtwidgets
    pyside.QtCore = qtcore

    monkeypatch.setitem(sys.modules, "PySide6", pyside)
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qtwidgets)
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", qtcore)


def load_module(monkeypatch):
    setup_pyside(monkeypatch)
    spec = util.spec_from_file_location(
        "alpha_engine", Path(__file__).resolve().parents[1] / "alpha_engine.py"
    )
    mod = util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_start_analysis_success(monkeypatch):
    mod = load_module(monkeypatch)

    def fake_extract(url):
        assert url == "http://ex"
        return "Title", {"Red": "https://a/red.jpg", "Blue": "https://a/blue.png"}

    monkeypatch.setattr(mod.moteur_variante, "extract_variants_with_images", fake_extract)

    eng = mod.AlphaEngine()
    eng.input_url.setText("http://ex")
    eng.input_domain.setText("https://wp")
    eng.input_date.setText("2024/05")
    eng.start_analysis()

    lines = eng.result_view.toPlainText().strip().splitlines()
    assert lines == [
        "Title",
        "Red -> https://wp/wp-content/uploads/2024/05/red.jpg",
        "Blue -> https://wp/wp-content/uploads/2024/05/blue.png",
        "Analyse terminée.",
    ]
    assert eng._export_rows == [
        {
            "Product": "Title",
            "Variant": "Red",
            "Image": "https://wp/wp-content/uploads/2024/05/red.jpg",
        },
        {
            "Product": "Title",
            "Variant": "Blue",
            "Image": "https://wp/wp-content/uploads/2024/05/blue.png",
        },
    ]


def test_start_analysis_error(monkeypatch):
    mod = load_module(monkeypatch)

    def fake_extract(url):
        raise ValueError("boom")

    monkeypatch.setattr(mod.moteur_variante, "extract_variants_with_images", fake_extract)

    eng = mod.AlphaEngine()
    eng.input_url.setText("http://ex")
    mod.QMessageBox.last.clear()
    eng.start_analysis()

    assert mod.QMessageBox.last[-1] == ("critical", "Erreur", "boom")


def test_build_wp_url_strip_digits(monkeypatch):
    mod = load_module(monkeypatch)

    url = mod.AlphaEngine._build_wp_url(
        "https://wp",
        "2024/05",
        "https://ex.com/img/bob-ficelle-outdoor-beige-453.png?x=1",
    )

    assert (
        url
        == "https://wp/wp-content/uploads/2024/05/bob-ficelle-outdoor-beige.png"
    )


def test_export_csv(monkeypatch, tmp_path):
    mod = load_module(monkeypatch)
    eng = mod.AlphaEngine()
    eng._export_rows = [
        {"Product": "T", "Variant": "V", "Image": "L"},
    ]

    def fake_get(*a, **k):
        return str(tmp_path / "out.csv"), ""

    monkeypatch.setattr(mod.QFileDialog, "getSaveFileName", staticmethod(fake_get))

    calls = {}

    class DummyPandas:
        class DataFrame:
            def __init__(self, data):
                calls["data"] = data
            def to_csv(self, path, index=False):
                calls["path"] = path
                calls["index"] = index

    monkeypatch.setitem(sys.modules, "pandas", DummyPandas)

    eng.export_csv()

    assert calls["data"] == eng._export_rows
    assert calls["path"] == str(tmp_path / "out.csv")
    assert calls["index"] is False
