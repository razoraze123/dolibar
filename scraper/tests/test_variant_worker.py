import types
import sys
from pathlib import Path
import importlib.util as util

class DummySignal:
    def __init__(self, *args, **kwargs):
        self._callbacks = []
    def connect(self, cb):
        self._callbacks.append(cb)
    def emit(self, *args, **kwargs):
        for cb in self._callbacks:
            cb(*args, **kwargs)

def setup_pyside(monkeypatch):
    qtwidgets = types.ModuleType("PySide6.QtWidgets")
    for name in [
        "QApplication","QMainWindow","QWidget","QListWidget","QStackedWidget",
        "QHBoxLayout","QVBoxLayout","QLineEdit","QComboBox","QPushButton",
        "QPlainTextEdit","QLabel","QProgressBar","QFileDialog","QCheckBox",
        "QSpinBox","QFontComboBox","QTextEdit","QGroupBox","QMessageBox",
        "QToolBar","QToolButton","QScrollArea","QSizePolicy","QFrame",
    ]:
        setattr(qtwidgets, name, type(name, (), {}))

    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.QThread = type("QThread", (), {})
    qtcore.Signal = DummySignal
    qtcore.QObject = type("QObject", (), {"moveToThread": lambda self, t: None, "deleteLater": lambda self: None})
    qtcore.QPropertyAnimation = object
    qtcore.Property = lambda t, fget, fset: property(fget, fset)
    qtcore.QRect = object
    qtcore.QTimer = type("QTimer", (), {})
    qtcore.Qt = types.SimpleNamespace(NoPen=0, PointingHandCursor=1)

    qtgui = types.ModuleType("PySide6.QtGui")
    for name in ["QFont", "QPainter", "QColor", "QPixmap", "QClipboard"]:
        setattr(qtgui, name, type(name, (), {}))

    pyside = types.ModuleType("PySide6")
    pyside.QtWidgets = qtwidgets
    pyside.QtCore = qtcore
    pyside.QtGui = qtgui

    monkeypatch.setitem(sys.modules, "PySide6", pyside)
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qtwidgets)
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", qtgui)


def test_scrap_variant_worker_run(monkeypatch, tmp_path):
    setup_pyside(monkeypatch)
    spec = util.spec_from_file_location(
        "interface_py", Path(__file__).resolve().parents[1] / "interface_py.py"
    )
    ip = util.module_from_spec(spec)
    spec.loader.exec_module(ip)

    calls = []
    def fake_extract(url):
        calls.append(("extract", url))
        return "title", {"v": "img"}
    def fake_save(title, mapping, path):
        calls.append(("save", title, mapping, path))
    monkeypatch.setattr(ip.moteur_variante, "extract_variants_with_images", fake_extract)
    monkeypatch.setattr(ip.moteur_variante, "save_images_to_file", fake_save)

    worker = ip.ScrapVariantWorker("http://ex", "sel", tmp_path / "o.txt")
    worker.run()

    assert calls == [
        ("extract", "http://ex"),
        ("save", "title", {"v": "img"}, tmp_path / "o.txt"),
    ]
