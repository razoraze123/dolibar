"""Utility to find a CSS selector for product links in an HTML snippet."""

from __future__ import annotations

import re
import sys
from typing import Iterable

from bs4 import BeautifulSoup

try:
    from PySide6.QtWidgets import (
        QApplication,
        QMainWindow,
        QWidget,
        QVBoxLayout,
        QLabel,
        QPlainTextEdit,
        QLineEdit,
        QPushButton,
    )
except Exception:  # noqa: BLE001
    QApplication = None  # type: ignore

# Patterns of classes considered too generic or dynamic to use in a selector
_BLACKLIST_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"^v-stack$",
        r"^h-stack$",
        r"^gap-",
        r"^grid$",
        r"^grid-",
        r"^w-full$",
        r"^h-full$",
    )
]


def _clean_classes(classes: Iterable[str] | None) -> list[str]:
    if not classes:
        return []
    return [c for c in classes if not any(pat.search(c) for pat in _BLACKLIST_PATTERNS)]


def _build_selector(a_tag) -> str:
    parts: list[str] = ["a"]
    for parent in a_tag.parents:
        if parent.name == "[document]":
            break
        classes = _clean_classes(parent.get("class"))
        if parent.get("id"):
            parts.append(f"{parent.name}#{parent['id']}")
            break
        if classes:
            parts.append(f"{parent.name}." + ".".join(classes))
            break
    return " ".join(reversed(parts))


def find_best_css_selector(html: str) -> str:
    """Return a CSS selector to locate product links in *html*.

    The selector targets ``<a>`` elements that contain text and an ``href``
    attribute. The function tries to keep the selector short while avoiding
    overly generic classes.
    """

    soup = BeautifulSoup(html, "html.parser")
    anchors = [
        a
        for a in soup.find_all("a")
        if a.get("href") and a.get_text(strip=True)
    ]
    if not anchors:
        raise ValueError("No valid <a> tags found")

    candidates = { _build_selector(a) for a in anchors }
    return sorted(candidates, key=len)[0]


def run_gui() -> None:
    """Launch the PySide6 interface to test selectors."""

    if QApplication is None:
        raise RuntimeError("PySide6 is not installed")

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("CSS Selector Tester")

            container = QWidget()
            layout = QVBoxLayout(container)
            self.setCentralWidget(container)

            layout.addWidget(QLabel("HTML input"))
            self.input_html = QPlainTextEdit()
            self.input_html.setPlaceholderText("Paste HTML snippet here...")
            layout.addWidget(self.input_html)

            self.button = QPushButton("Find selector")
            layout.addWidget(self.button)

            layout.addWidget(QLabel("Best selector"))
            self.output = QLineEdit()
            self.output.setReadOnly(True)
            layout.addWidget(self.output)

            self.status = QLabel()
            layout.addWidget(self.status)

            self.button.clicked.connect(self.on_click)

        def on_click(self) -> None:
            html = self.input_html.toPlainText().strip()
            if not html:
                self.status.setText("Please provide HTML")
                self.output.clear()
                return
            try:
                selector = find_best_css_selector(html)
            except Exception as exc:  # noqa: BLE001
                self.status.setText(str(exc))
                self.output.clear()
            else:
                self.output.setText(selector)
                self.status.setText("")

    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(600, 400)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate a CSS selector for product links from HTML input",
    )
    parser.add_argument("file", nargs="?", help="Path to an HTML file")
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the graphical interface instead of reading a file",
    )
    args = parser.parse_args()

    if args.gui:
        run_gui()
    else:
        if args.file:
            with open(args.file, "r", encoding="utf-8") as fh:
                content = fh.read()
        else:
            content = sys.stdin.read()
        print(find_best_css_selector(content))

