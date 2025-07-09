import types
import sys
from pathlib import Path
import importlib.util as util

class DummySignal:
    def __init__(self, *args, **kwargs):
        self._cbs = []
    def connect(self, cb):
        self._cbs.append(cb)
    def emit(self, *args, **kwargs):
        for cb in self._cbs:
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
    qtcore.Qt = types.SimpleNamespace(NoPen=0, PointingHandCursor=1, KeepAspectRatio=1, SmoothTransformation=1)

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


def test_worker_parallel(monkeypatch, tmp_path):
    setup_pyside(monkeypatch)
    spec = util.spec_from_file_location(
        "interface_py", Path(__file__).resolve().parents[1] / "interface_py.py"
    )
    ip = util.module_from_spec(spec)
    spec.loader.exec_module(ip)

    calls = []
    def fake_download(url, **kwargs):
        cb = kwargs["progress_callback"]
        cb(1, 2)
        cb(2, 2)
        calls.append(url)
        return {"folder": tmp_path, "first_image": None}

    monkeypatch.setattr(ip.scraper_images, "download_images", fake_download)

    worker = ip.ScraperImagesWorker(
        ["http://a", "http://b"],
        tmp_path,
        "img",
        False,
        False,
        None,
        max_threads=1,
        max_jobs=2,
    )
    progress = []
    worker.progress.connect(lambda d, t: progress.append((d, t)))
    worker.run()

    assert sorted(calls) == ["http://a", "http://b"]
    assert progress[0] == (0, 0)
    assert progress[-1] == (4, 4)
    assert len(progress) == 5

