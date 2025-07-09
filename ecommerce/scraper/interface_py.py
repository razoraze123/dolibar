import sys
import logging
import io
import os
import shutil
import subprocess
import time
import re
from pathlib import Path
from typing import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QListWidget,
    QStackedWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QPlainTextEdit,
    QLabel,
    QProgressBar,
    QFileDialog,
    QCheckBox,
    QSpinBox,
    QFontComboBox,
    QTextEdit,
    QGroupBox,
    QMessageBox,
    QToolBar,
    QToolButton,
    QScrollArea,
    QSizePolicy,
    QFrame,
)
from PySide6.QtCore import (
    QThread,
    Signal,
    Qt,
    QPropertyAnimation,
    Property,
    QRect,
    QTimer,
)
from PySide6.QtGui import QFont, QPainter, QColor, QPixmap, QClipboard

# QSplitter might not be available in all test environments
try:
    from PySide6.QtWidgets import QSplitter
except Exception:  # pragma: no cover - used only for stub environments
    class QSplitter:
        def __init__(self, *args, **kwargs):
            pass

        def addWidget(self, *args, **kwargs):
            pass

        def setStretchFactor(self, *args, **kwargs):
            pass

from alpha_engine import AlphaEngine

import scrap_lien_collection
import scraper_images
import scrap_description_produit
import scrap_prix_produit
import moteur_variante
from settings_manager import SettingsManager, apply_settings
from site_profile_manager import SiteProfileManager


try:
    from PySide6.QtCore import QSize  # type: ignore
except Exception:  # pragma: no cover - fallback for tests
    class QSize:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            pass

try:
    from PySide6.QtGui import QIcon  # type: ignore
except Exception:  # pragma: no cover - fallback for tests
    class QIcon:  # type: ignore
        def __init__(self, *args, **kwargs) -> None:
            pass


ICONS_DIR = Path(__file__).resolve().parent / "icons"


def load_stylesheet(path: str = "style.qss") -> None:
    """Apply the application's stylesheet if available."""
    app = QApplication.instance()
    if app is None:
        return
    qss_path = Path(path)
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))


class QtLogHandler(logging.Handler):
    """Forward logging records to a Qt signal."""

    def __init__(self, signal):
        super().__init__()
        self._signal = signal

    def emit(self, record):
        msg = self.format(record)
        self._signal.emit(msg)


class ToggleSwitch(QCheckBox):
    """Simple ON/OFF switch widget."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._offset = 2
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(120)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(40, 20)
        QCheckBox.setChecked(self, False)
        self.setStyleSheet("QCheckBox::indicator { width:0; height:0; }")

    def offset(self) -> int:  # type: ignore[override]
        return self._offset

    def setOffset(self, value: int) -> None:  # type: ignore[override]
        self._offset = value
        self.update()

    offset = Property(int, offset, setOffset)

    def mouseReleaseEvent(self, event) -> None:  # noqa: D401
        super().mouseReleaseEvent(event)
        self.setChecked(not self.isChecked())

    def setChecked(self, checked: bool) -> None:  # type: ignore[override]
        start = self._offset
        end = self.width() - self.height() + 2 if checked else 2
        self._anim.stop()
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.start()
        super().setChecked(checked)

    def paintEvent(self, event) -> None:  # noqa: D401
        radius = self.height() / 2
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#4cd964" if self.isChecked() else "#bbbbbb"))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), radius, radius)
        painter.setBrush(QColor("white"))
        painter.drawEllipse(QRect(self._offset, 2, self.height() - 4, self.height() - 4))


class CollapsibleSection(QWidget):
    """Simple collapsible section used for the sidebar."""

    def __init__(self, title: str, icon: QIcon, callback) -> None:
        super().__init__()
        self._title = title
        self._callback = callback
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.header = QToolButton()
        self.header.setText(f"\u25B6 {title}")
        self.header.setIcon(icon)
        self.header.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.header.clicked.connect(self.toggle)
        layout.addWidget(self.header)

        self.container = QWidget()
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(20, 0, 0, 0)
        self.page_button = QToolButton(text=title)
        self.page_button.setIcon(icon)
        self.page_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.page_button.setCheckable(True)
        self.page_button.clicked.connect(callback)
        container_layout.addWidget(self.page_button)
        layout.addWidget(self.container)
        self.container.setVisible(False)

    def toggle(self) -> None:
        visible = not self.container.isVisible()
        self.container.setVisible(visible)
        arrow = "\u25BC" if visible else "\u25B6"
        self.header.setText(f"{arrow} {self._title}")

class ScrapLienWorker(QThread):
    log = Signal(str)
    finished = Signal()

    def __init__(
        self,
        url: str,
        output: Path,
        selector: str,
        log_level: str,
        output_format: str,
    ):
        super().__init__()
        self.url = url
        self.output = output
        self.selector = selector
        self.log_level = log_level
        self.output_format = output_format

    def run(self) -> None:
        logger = logging.getLogger()
        logger.setLevel(getattr(logging, self.log_level, logging.INFO))
        handler = QtLogHandler(self.log)
        formatter = logging.Formatter("%(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        stream = io.StringIO()
        stream_handler = logging.StreamHandler(stream)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        try:
            scrap_lien_collection.scrape_collection(
                self.url,
                self.output,
                self.selector,
                scrap_lien_collection.DEFAULT_NEXT_SELECTOR,
                self.output_format,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("%s", exc)
        finally:
            logger.removeHandler(handler)
            logger.removeHandler(stream_handler)
            self.finished.emit()


class ScraperImagesWorker(QThread):
    """Background worker to download images using scraper_images."""

    log = Signal(str)
    progress = Signal(int, int)
    finished = Signal()
    preview_path = Signal(str)

    def __init__(
        self,
        urls: list[str],
        parent_dir: Path,
        selector: str,
        open_folder: bool,
        show_preview: bool,
        alt_json: str | None,
        max_threads: int = 4,
        max_jobs: int = 1,
    ):
        super().__init__()
        self.urls = urls
        self.parent_dir = parent_dir
        self.selector = selector
        self.open_folder = open_folder
        self.show_preview = show_preview
        self.alt_json = alt_json
        self.max_threads = max_threads
        self.max_jobs = max_jobs

    def run(self) -> None:
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        handler = QtLogHandler(self.log)
        formatter = logging.Formatter("%(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        try:
            images_done = 0
            total_images = 0
            lock = threading.Lock()

            def make_cb() -> Callable[[int, int], None]:
                first = True

                def cb(i: int, t: int) -> None:
                    nonlocal first, images_done, total_images
                    with lock:
                        if first:
                            total_images += t
                            first = False
                        images_done += 1
                        self.progress.emit(images_done, total_images)

                return cb

            self.progress.emit(0, 0)

            preview_sent = False
            with ThreadPoolExecutor(max_workers=self.max_jobs) as executor:
                future_to_url = {
                    executor.submit(
                        scraper_images.download_images,
                        url,
                        css_selector=self.selector,
                        parent_dir=self.parent_dir,
                        progress_callback=make_cb(),
                        alt_json_path=self.alt_json,
                        max_threads=self.max_threads,
                    ): url
                    for url in self.urls
                }

                for fut in as_completed(future_to_url):
                    url = future_to_url[fut]
                    try:
                        info = fut.result()
                        folder = info["folder"]
                        if (
                            self.show_preview
                            and not preview_sent
                            and info.get("first_image")
                        ):
                            self.preview_path.emit(str(info["first_image"]))
                            preview_sent = True
                        if self.open_folder:
                            scraper_images._open_folder(folder)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("%s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.error("%s", exc)
        finally:
            logger.removeHandler(handler)
            self.finished.emit()


class ScrapDescriptionWorker(QThread):
    """Background worker to extract and save product descriptions."""

    log = Signal(str)
    finished = Signal()

    def __init__(self, url: str, selector: str, output: Path):
        super().__init__()
        self.url = url
        self.selector = selector
        self.output = output

    def run(self) -> None:
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        handler = QtLogHandler(self.log)
        formatter = logging.Formatter("%(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        try:
            scrap_description_produit.scrape_description(
                self.url, self.selector, self.output
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("%s", exc)
        finally:
            logger.removeHandler(handler)
            self.finished.emit()


class ScrapPriceWorker(QThread):
    """Background worker to extract and save product price."""

    log = Signal(str)
    finished = Signal()

    def __init__(self, url: str, selector: str, output: Path) -> None:
        super().__init__()
        self.url = url
        self.selector = selector
        self.output = output

    def run(self) -> None:
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        handler = QtLogHandler(self.log)
        formatter = logging.Formatter("%(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        try:
            scrap_prix_produit.scrape_price(self.url, self.selector, self.output)
        except Exception as exc:  # noqa: BLE001
            logger.error("%s", exc)
        finally:
            logger.removeHandler(handler)
            self.finished.emit()


class ScrapVariantWorker(QThread):
    """Background worker to extract and save product variants."""

    log = Signal(str)
    finished = Signal()

    def __init__(self, url: str, selector: str, output: Path) -> None:
        super().__init__()
        self.url = url
        self.selector = selector
        self.output = output

    def run(self) -> None:
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        handler = QtLogHandler(self.log)
        formatter = logging.Formatter("%(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        try:
            title, mapping = moteur_variante.extract_variants_with_images(self.url)
            moteur_variante.save_images_to_file(title, mapping, self.output)
        except Exception as exc:  # noqa: BLE001
            logger.error("%s", exc)
        finally:
            logger.removeHandler(handler)
            self.finished.emit()


class VariantFetchWorker(QThread):
    """Fetch product variants with images and emit results."""

    log = Signal(str)
    result = Signal(str, dict)
    finished = Signal()

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url

    def run(self) -> None:
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        handler = QtLogHandler(self.log)
        formatter = logging.Formatter("%(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        try:
            title, mapping = moteur_variante.extract_variants_with_images(self.url)
            self.result.emit(title, mapping)
        except Exception as exc:  # noqa: BLE001
            logger.error("%s", exc)
        finally:
            logger.removeHandler(handler)
            self.finished.emit()


class PageProfiles(QWidget):
    """Manage site profiles (selectors)."""

    def __init__(self, profile_manager: SiteProfileManager, main_window) -> None:
        super().__init__()
        self.profile_manager = profile_manager
        self.main_window = main_window

        layout = QVBoxLayout(self)

        self.combo_profiles = QComboBox()
        layout.addWidget(QLabel("Profils existants"))
        layout.addWidget(self.combo_profiles)

        self.input_name = QLineEdit()
        layout.addWidget(QLabel("Nom du profil"))
        layout.addWidget(self.input_name)

        self.input_images = QLineEdit()
        layout.addWidget(QLabel("Sélecteur Images"))
        layout.addWidget(self.input_images)

        self.input_desc = QLineEdit()
        layout.addWidget(QLabel("Sélecteur Description"))
        layout.addWidget(self.input_desc)

        self.input_collection = QLineEdit()
        layout.addWidget(QLabel("Sélecteur Collection"))
        layout.addWidget(self.input_collection)

        alt_json_layout = QHBoxLayout()
        self.input_alt_json = QLineEdit()
        alt_json_layout.addWidget(self.input_alt_json)
        self.button_alt_json = QPushButton("\U0001F4C1 Choisir un fichier json")
        self.button_alt_json.clicked.connect(self.browse_alt_json)
        alt_json_layout.addWidget(self.button_alt_json)
        layout.addWidget(QLabel("Fichier ALT JSON"))
        layout.addLayout(alt_json_layout)

        file_urls_layout = QHBoxLayout()
        self.input_urls_images = QLineEdit()
        file_urls_layout.addWidget(self.input_urls_images)
        self.button_urls_images = QPushButton("\U0001F4C1 Choisir un fichier txt")
        self.button_urls_images.clicked.connect(self.browse_urls_images)
        file_urls_layout.addWidget(self.button_urls_images)
        layout.addWidget(QLabel("Fichier URLs Images"))
        layout.addLayout(file_urls_layout)

        urls_desc_layout = QHBoxLayout()
        self.input_urls_desc = QLineEdit()
        urls_desc_layout.addWidget(self.input_urls_desc)
        self.button_urls_desc = QPushButton("\U0001F4C1 Choisir un fichier txt")
        self.button_urls_desc.clicked.connect(self.browse_urls_desc)
        urls_desc_layout.addWidget(self.button_urls_desc)
        layout.addWidget(QLabel("Fichier URLs Description"))
        layout.addLayout(urls_desc_layout)

        self.checkbox_auto = QCheckBox("Appliquer automatiquement après chargement")
        layout.addWidget(self.checkbox_auto)

        btn_layout = QHBoxLayout()
        self.button_new = QPushButton("Nouveau")
        self.button_save = QPushButton("Sauvegarder")
        self.button_load = QPushButton("Charger")
        self.button_delete = QPushButton("Supprimer")
        for b in [self.button_new, self.button_save, self.button_load, self.button_delete]:
            btn_layout.addWidget(b)
        layout.addLayout(btn_layout)
        layout.addStretch()

        self.button_new.clicked.connect(self.new_profile)
        self.button_save.clicked.connect(self.save_profile)
        self.button_load.clicked.connect(self.load_selected_profile)
        self.button_delete.clicked.connect(self.delete_profile)
        self.combo_profiles.currentIndexChanged.connect(self.populate_from_selected)

        self.refresh_profiles()

    # Utility methods
    def profile_path(self, name: str) -> Path:
        return self.profile_manager.dir / f"{name}.json"

    def refresh_profiles(self) -> None:
        self.combo_profiles.blockSignals(True)
        self.combo_profiles.clear()
        for f in sorted(self.profile_manager.dir.glob("*.json")):
            self.combo_profiles.addItem(f.stem)
        self.combo_profiles.blockSignals(False)
        if self.combo_profiles.count() > 0:
            self.combo_profiles.setCurrentIndex(0)
            self.populate_from_selected()

    def populate_from_selected(self) -> None:
        name = self.combo_profiles.currentText()
        if not name:
            return
        data = self.profile_manager.load_profile(self.profile_path(name))
        self.fill_fields(data)
        if self.checkbox_auto.isChecked():
            self.profile_manager.apply_profile_to_ui(data, self.main_window)

    def fill_fields(self, data: dict) -> None:
        self.input_name.setText(data.get("nom", ""))
        selectors = data.get("selectors", {})
        self.input_images.setText(selectors.get("images", ""))
        self.input_desc.setText(selectors.get("description", ""))
        self.input_collection.setText(selectors.get("collection", ""))
        self.input_alt_json.setText(data.get("sentences_file", ""))
        self.input_urls_images.setText(data.get("urls_file", ""))
        self.input_urls_desc.setText(data.get("desc_urls_file", ""))

    def new_profile(self) -> None:
        self.input_name.clear()
        self.input_images.clear()
        self.input_desc.clear()
        self.input_collection.clear()
        self.input_alt_json.clear()
        self.input_urls_images.clear()
        self.input_urls_desc.clear()

    def save_profile(self) -> None:
        name = self.input_name.text().strip()
        if not name:
            return
        data = {
            "nom": name,
            "selectors": {
                "images": self.input_images.text().strip(),
                "description": self.input_desc.text().strip(),
                "collection": self.input_collection.text().strip(),
            },
            "sentences_file": self.input_alt_json.text().strip(),
            "urls_file": self.input_urls_images.text().strip(),
            "desc_urls_file": self.input_urls_desc.text().strip(),
        }
        path = self.profile_path(name)
        self.profile_manager.save_profile(path, data)
        self.refresh_profiles()

    def load_selected_profile(self) -> None:
        name = self.combo_profiles.currentText()
        if not name:
            return
        data = self.profile_manager.load_profile(self.profile_path(name))
        self.fill_fields(data)
        self.profile_manager.apply_profile_to_ui(data, self.main_window)

    def delete_profile(self) -> None:
        name = self.combo_profiles.currentText()
        if not name:
            return
        path = self.profile_path(name)
        try:
            path.unlink()
        except Exception:
            pass
        self.refresh_profiles()

    def browse_urls_images(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner un fichier", "", "Text Files (*.txt)"
        )
        if file_path:
            self.input_urls_images.setText(file_path)

    def browse_urls_desc(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner un fichier", "", "Text Files (*.txt)"
        )
        if file_path:
            self.input_urls_desc.setText(file_path)

    def browse_alt_json(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner un fichier", "", "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            self.input_alt_json.setText(file_path)


class PageScrapLienCollection(QWidget):
    def __init__(self, manager: SettingsManager):
        super().__init__()
        self.manager = manager
        layout = QVBoxLayout(self)

        self.input_url = QLineEdit(manager.settings.get("scrap_lien_url", ""))
        self.input_url.setPlaceholderText("URL de la collection")
        layout.addWidget(QLabel("URL de la collection"))
        layout.addWidget(self.input_url)

        self.input_output = QLineEdit(manager.settings.get("scrap_lien_output", "products.txt"))
        layout.addWidget(QLabel("Fichier de sortie"))
        layout.addWidget(self.input_output)

        self.combo_format = QComboBox()
        self.combo_format.addItems(["txt", "json", "csv"])
        self.combo_format.setCurrentText(manager.settings.get("scrap_lien_format", "txt"))
        layout.addWidget(QLabel("Format"))
        layout.addWidget(self.combo_format)

        self.input_selector = QLineEdit(
            manager.settings.get(
                "scrap_lien_selector", scrap_lien_collection.DEFAULT_SELECTOR
            )
        )
        # Champ géré via l'onglet Profils – non ajouté au layout
        label_selector = QLabel("Sélecteur CSS")
        self.input_selector.hide()
        label_selector.hide()

        self.combo_log = QComboBox()
        self.combo_log.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.combo_log.setCurrentText("INFO")
        layout.addWidget(QLabel("Niveau de log"))
        layout.addWidget(self.combo_log)

        self.button_start = QPushButton("Lancer le scraping")
        layout.addWidget(self.button_start)
        self.button_start.clicked.connect(self.start_worker)

        self.button_toggle_console = QPushButton("Masquer la console")
        self.button_toggle_console.clicked.connect(self.toggle_console)
        layout.addWidget(self.button_toggle_console)


        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)

        layout.addStretch()

        self.worker: ScrapLienWorker | None = None

        for widget in [self.input_url, self.input_output, self.input_selector]:
            widget.editingFinished.connect(self.save_fields)
        self.combo_format.currentIndexChanged.connect(self.save_fields)

    def start_worker(self) -> None:
        url = self.input_url.text().strip()
        output = Path(self.input_output.text().strip() or "products.txt")
        selector = self.input_selector.text().strip() or scrap_lien_collection.DEFAULT_SELECTOR
        log_level = self.combo_log.currentText()
        output_format = self.combo_format.currentText()

        if not url:
            self.log_view.appendPlainText("Veuillez renseigner l'URL.")
            return

        self.button_start.setEnabled(False)
        self.log_view.clear()

        self.save_fields()

        self.worker = ScrapLienWorker(url, output, selector, log_level, output_format)
        self.worker.log.connect(self.log_view.appendPlainText)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_finished(self) -> None:
        self.button_start.setEnabled(True)
        QMessageBox.information(self, "Terminé", "Le scraping des liens est terminé.")

    def toggle_console(self) -> None:
        visible = self.log_view.isVisible()
        self.log_view.setVisible(not visible)
        self.button_toggle_console.setText(
            "Afficher la console" if visible else "Masquer la console"
        )

    def save_fields(self) -> None:
        self.manager.save_setting("scrap_lien_url", self.input_url.text())
        self.manager.save_setting("scrap_lien_output", self.input_output.text())
        self.manager.save_setting("scrap_lien_selector", self.input_selector.text())
        self.manager.save_setting("scrap_lien_format", self.combo_format.currentText())


class PageScraperImages(QWidget):
    def __init__(self, manager: SettingsManager):
        super().__init__()
        self.manager = manager
        layout = QVBoxLayout(self)
        self.input_source = QLineEdit(manager.settings.get("images_url", ""))
        self.input_source.setPlaceholderText("URL unique")
        layout.addWidget(QLabel("URL unique"))
        layout.addWidget(self.input_source)

        file_layout = QHBoxLayout()
        self.input_urls_file = QLineEdit(manager.settings.get("images_file", ""))
        file_layout.addWidget(self.input_urls_file)
        self.button_file = QPushButton("\U0001F4C1 Choisir un fichier txt")
        self.button_file.clicked.connect(self.browse_file)
        file_layout.addWidget(self.button_file)
        # Champ géré via l'onglet Profils – non ajouté au layout
        label_urls = QLabel("Fichier d'URLs")
        self.input_urls_file.hide()
        self.button_file.hide()
        label_urls.hide()

        dir_layout = QHBoxLayout()
        self.input_dest = QLineEdit(manager.settings.get("images_dest", "images"))
        dir_layout.addWidget(self.input_dest)
        self.button_dir = QPushButton("\U0001F4C2 Choisir dossier")
        self.button_dir.clicked.connect(self.browse_dir)
        dir_layout.addWidget(self.button_dir)
        layout.addWidget(QLabel("Dossier parent"))
        layout.addLayout(dir_layout)

        self.input_options = QLineEdit(manager.settings.get("images_selector", ""))
        # Champ géré via l'onglet Profils – non ajouté au layout
        label_options = QLabel("Sélecteur CSS")
        self.input_options.hide()
        label_options.hide()

        self.input_alt_json = QLineEdit(
            manager.settings.get("images_alt_json", "product_sentences.json")
        )
        # Champ géré via l'onglet Profils – non ajouté au layout
        label_alt_json = QLabel("Fichier ALT JSON")
        self.input_alt_json.hide()
        label_alt_json.hide()

        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, 32)
        self.spin_threads.setValue(manager.settings.get("images_max_threads", 4))
        layout.addWidget(QLabel("Threads parall\xc3\xa8les"))
        layout.addWidget(self.spin_threads)

        self.checkbox_preview = QCheckBox("Afficher le dossier après téléchargement")
        self.switch_preview = ToggleSwitch()
        switch_label = QLabel("Aperçu")

        checkbox_layout = QHBoxLayout()
        checkbox_layout.addWidget(self.checkbox_preview)
        checkbox_layout.addWidget(switch_label)
        checkbox_layout.addWidget(self.switch_preview)
        layout.addLayout(checkbox_layout)

        self.button_start = QPushButton("Scraper")
        layout.addWidget(self.button_start)

        self.button_delete = QPushButton("Supprimer dossiers")
        layout.addWidget(self.button_delete)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)

        self.label_timer = QLabel("Temps restant : ...")
        layout.addWidget(self.label_timer)

        self.images_done = 0
        self.total_images = 0

        self.label_preview = QLabel(alignment=Qt.AlignCenter)
        self.label_preview.setVisible(False)
        self.switch_preview.toggled.connect(self.label_preview.setVisible)
        layout.addWidget(self.label_preview)

        self.button_toggle_console = QPushButton("Masquer la console")
        self.button_toggle_console.clicked.connect(self.toggle_console)
        layout.addWidget(self.button_toggle_console)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)
        layout.addStretch()

        self.worker: ScraperImagesWorker | None = None

        self.button_start.clicked.connect(self.start_worker)
        self.button_delete.clicked.connect(self.delete_folders)

        for widget in [
            self.input_source,
            self.input_urls_file,
            self.input_dest,
            self.input_options,
            self.input_alt_json,
        ]:
            widget.editingFinished.connect(self.save_fields)
        self.spin_threads.valueChanged.connect(self.save_fields)

    def start_worker(self) -> None:
        url = self.input_source.text().strip()
        file_path = self.input_urls_file.text().strip()
        dest = Path(self.input_dest.text().strip() or "images")
        selector = self.input_options.text().strip() or scraper_images.DEFAULT_CSS_SELECTOR

        urls_list: list[str] = []
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as fh:
                    urls_list = [line.strip() for line in fh if line.strip()]
            except OSError as exc:
                self.log_view.appendPlainText(f"Impossible de lire {file_path}: {exc}")
                return

        if not urls_list:
            if not url:
                self.log_view.appendPlainText("Veuillez renseigner l'URL ou choisir un fichier.")
                return
            urls_list = [url]

        self.button_start.setEnabled(False)
        self.progress.setValue(0)
        self.log_view.clear()

        self.save_fields()

        open_folder = self.checkbox_preview.isChecked()
        show_preview = self.switch_preview.isChecked()

        alt_json = self.input_alt_json.text().strip() or None
        self.worker = ScraperImagesWorker(
            urls_list,
            dest,
            selector,
            open_folder,
            show_preview,
            alt_json,
            self.spin_threads.value(),
        )
        self.worker.log.connect(self.log_view.appendPlainText)
        self.worker.progress.connect(self.update_progress)
        self.worker.preview_path.connect(self.display_preview)
        self.worker.finished.connect(self.on_finished)
        self.label_preview.clear()
        self.label_preview.setVisible(False)
        self.images_done = 0
        self.total_images = 0
        self.start_time = time.perf_counter()
        self.worker.start()

    def browse_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Sélectionner un fichier", "", "Text Files (*.txt)")
        if file_path:
            self.input_urls_file.setText(file_path)
            self.save_fields()

    def browse_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier")
        if directory:
            self.input_dest.setText(directory)
            self.save_fields()

    def update_progress(self, done: int, total: int) -> None:
        self.images_done = done
        self.total_images = total
        value = int(done / total * 100) if total else 0
        self.progress.setValue(value)
        if done == 0 or total == 0:
            self.label_timer.setText("Temps restant : ...")
            return
        elapsed = time.perf_counter() - self.start_time
        average = elapsed / done
        remaining = (total - done) * average
        if remaining >= 60:
            minutes = int(remaining / 60 + 0.5)
            self.label_timer.setText(
                f"Temps restant : {minutes} minute(s)"
            )
        else:
            seconds = int(remaining + 0.5)
            self.label_timer.setText(
                f"Temps restant : {seconds} seconde(s)"
            )

    def toggle_console(self) -> None:
        visible = self.log_view.isVisible()
        self.log_view.setVisible(not visible)
        self.button_toggle_console.setText(
            "Afficher la console" if visible else "Masquer la console"
        )

    def on_finished(self) -> None:
        self.button_start.setEnabled(True)
        self.label_timer.setText("Temps restant : 0 seconde(s)")
        QMessageBox.information(
            self,
            "Terminé",
            "Le téléchargement des images est terminé.",
        )
        self.progress.setValue(0)

    def delete_folders(self) -> None:
        dest = Path(self.input_dest.text().strip() or "images")
        if not dest.exists():
            QMessageBox.information(self, "Info", "Le dossier spécifié n'existe pas.")
            return
        reply = QMessageBox.question(
            self,
            "Confirmer la suppression",
            f"Supprimer tout le contenu de {dest} ?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            for child in dest.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
            QMessageBox.information(self, "Supprimé", "Les dossiers ont été supprimés.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la suppression : {exc}")

    def save_fields(self) -> None:
        self.manager.save_setting("images_url", self.input_source.text())
        self.manager.save_setting("images_file", self.input_urls_file.text())
        self.manager.save_setting("images_dest", self.input_dest.text())
        self.manager.save_setting("images_selector", self.input_options.text())
        self.manager.save_setting("images_alt_json", self.input_alt_json.text())
        self.manager.save_setting("images_max_threads", self.spin_threads.value())

    def display_preview(self, path: str) -> None:
        if not self.switch_preview.isChecked():
            return
        pix = QPixmap(path)
        if pix.isNull():
            return
        pix = pix.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.label_preview.setPixmap(pix)
        self.label_preview.setVisible(True)


class PageScrapDescription(QWidget):
    def __init__(self, manager: SettingsManager) -> None:
        super().__init__()
        self.manager = manager
        layout = QVBoxLayout(self)

        self.input_url = QLineEdit(manager.settings.get("desc_url", ""))
        self.input_url.setPlaceholderText("URL du produit")
        layout.addWidget(QLabel("URL du produit"))
        layout.addWidget(self.input_url)

        self.input_selector = QLineEdit(
            manager.settings.get("desc_selector", scrap_description_produit.DEFAULT_SELECTOR)
        )
        # Champ géré via l'onglet Profils – non ajouté au layout
        label_selector = QLabel("Sélecteur CSS")
        self.input_selector.hide()
        label_selector.hide()

        self.input_output = QLineEdit(manager.settings.get("desc_output", "description.html"))
        layout.addWidget(QLabel("Fichier de sortie"))
        layout.addWidget(self.input_output)

        self.button_start = QPushButton("Extraire")
        layout.addWidget(self.button_start)

        self.button_toggle_console = QPushButton("Masquer la console")
        self.button_toggle_console.clicked.connect(self.toggle_console)
        layout.addWidget(self.button_toggle_console)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)
        layout.addStretch()

        self.worker: ScrapDescriptionWorker | None = None
        self.button_start.clicked.connect(self.start_worker)

        for widget in [self.input_url, self.input_selector, self.input_output]:
            widget.editingFinished.connect(self.save_fields)

    def start_worker(self) -> None:
        url = self.input_url.text().strip()
        selector = self.input_selector.text().strip() or scrap_description_produit.DEFAULT_SELECTOR
        output = Path(self.input_output.text().strip() or "description.html")

        if not url:
            self.log_view.appendPlainText("Veuillez renseigner l'URL.")
            return

        self.button_start.setEnabled(False)
        self.log_view.clear()

        self.save_fields()

        self.worker = ScrapDescriptionWorker(url, selector, output)
        self.worker.log.connect(self.log_view.appendPlainText)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_finished(self) -> None:
        self.button_start.setEnabled(True)
        QMessageBox.information(
            self,
            "Terminé",
            "L'extraction de la description est terminée.",
        )

    def toggle_console(self) -> None:
        visible = self.log_view.isVisible()
        self.log_view.setVisible(not visible)
        self.button_toggle_console.setText(
            "Afficher la console" if visible else "Masquer la console"
        )

    def save_fields(self) -> None:
        self.manager.save_setting("desc_url", self.input_url.text())
        self.manager.save_setting("desc_selector", self.input_selector.text())
        self.manager.save_setting("desc_output", self.input_output.text())


class PageScrapPrice(QWidget):
    def __init__(self, manager: SettingsManager) -> None:
        super().__init__()
        self.manager = manager
        layout = QVBoxLayout(self)

        self.input_url = QLineEdit(manager.settings.get("price_url", ""))
        self.input_url.setPlaceholderText("URL du produit")
        layout.addWidget(QLabel("URL du produit"))
        layout.addWidget(self.input_url)

        self.input_selector = QLineEdit(
            manager.settings.get("price_selector", scrap_prix_produit.DEFAULT_SELECTOR)
        )
        label_selector = QLabel("Sélecteur CSS")
        self.input_selector.hide()
        label_selector.hide()

        self.input_output = QLineEdit(manager.settings.get("price_output", "price.txt"))
        layout.addWidget(QLabel("Fichier de sortie"))
        layout.addWidget(self.input_output)

        self.button_start = QPushButton("Extraire")
        layout.addWidget(self.button_start)

        self.button_toggle_console = QPushButton("Masquer la console")
        self.button_toggle_console.clicked.connect(self.toggle_console)
        layout.addWidget(self.button_toggle_console)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)
        layout.addStretch()

        self.worker: ScrapPriceWorker | None = None
        self.button_start.clicked.connect(self.start_worker)

        for widget in [self.input_url, self.input_selector, self.input_output]:
            widget.editingFinished.connect(self.save_fields)

    def start_worker(self) -> None:
        url = self.input_url.text().strip()
        selector = self.input_selector.text().strip() or scrap_prix_produit.DEFAULT_SELECTOR
        output = Path(self.input_output.text().strip() or "price.txt")

        if not url:
            self.log_view.appendPlainText("Veuillez renseigner l'URL.")
            return

        self.button_start.setEnabled(False)
        self.log_view.clear()

        self.save_fields()

        self.worker = ScrapPriceWorker(url, selector, output)
        self.worker.log.connect(self.log_view.appendPlainText)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_finished(self) -> None:
        self.button_start.setEnabled(True)
        QMessageBox.information(
            self,
            "Terminé",
            "L'extraction du prix est terminée.",
        )

    def toggle_console(self) -> None:
        visible = self.log_view.isVisible()
        self.log_view.setVisible(not visible)
        self.button_toggle_console.setText(
            "Afficher la console" if visible else "Masquer la console"
        )

    def save_fields(self) -> None:
        self.manager.save_setting("price_url", self.input_url.text())
        self.manager.save_setting("price_selector", self.input_selector.text())
        self.manager.save_setting("price_output", self.input_output.text())


class PageVariantScraper(QWidget):
    def __init__(self, manager: SettingsManager) -> None:
        super().__init__()
        self.manager = manager
        layout = QVBoxLayout(self)

        self.input_url = QLineEdit(manager.settings.get("variant_url", ""))
        self.input_url.setPlaceholderText("URL du produit")
        layout.addWidget(QLabel("URL du produit"))
        layout.addWidget(self.input_url)

        self.input_selector = QLineEdit(
            manager.settings.get("variant_selector", moteur_variante.DEFAULT_SELECTOR)
        )
        label_selector = QLabel("Sélecteur CSS")
        self.input_selector.hide()
        label_selector.hide()

        file_layout = QHBoxLayout()
        self.input_output = QLineEdit(manager.settings.get("variant_output", "variants.txt"))
        file_layout.addWidget(self.input_output)
        self.button_output = QPushButton("\U0001F4C1 Choisir fichier")
        self.button_output.clicked.connect(self.browse_output)
        file_layout.addWidget(self.button_output)
        layout.addWidget(QLabel("Fichier de sortie"))
        layout.addLayout(file_layout)

        self.button_start = QPushButton("Extraire variantes")
        layout.addWidget(self.button_start)

        self.button_toggle_console = QPushButton("Masquer la console")
        self.button_toggle_console.clicked.connect(self.toggle_console)
        layout.addWidget(self.button_toggle_console)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)
        layout.addStretch()

        self.worker: ScrapVariantWorker | None = None
        self.button_start.clicked.connect(self.start_worker)

        for w in [self.input_url, self.input_selector, self.input_output]:
            w.editingFinished.connect(self.save_fields)

    def browse_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Fichier de sortie",
            "variants.txt",
            "Text Files (*.txt);;CSV Files (*.csv)",
        )
        if path:
            self.input_output.setText(path)

    def start_worker(self) -> None:
        url = self.input_url.text().strip()
        selector = self.input_selector.text().strip() or moteur_variante.DEFAULT_SELECTOR
        output = Path(self.input_output.text().strip() or "variants.txt")
        if not url:
            self.log_view.appendPlainText("Veuillez renseigner l'URL.")
            return
        self.button_start.setEnabled(False)
        self.log_view.clear()
        self.save_fields()
        self.worker = ScrapVariantWorker(url, selector, output)
        self.worker.log.connect(self.log_view.appendPlainText)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_finished(self) -> None:
        self.button_start.setEnabled(True)
        QMessageBox.information(self, "Terminé", "L'extraction des variantes est terminée.")

    def toggle_console(self) -> None:
        visible = self.log_view.isVisible()
        self.log_view.setVisible(not visible)
        self.button_toggle_console.setText(
            "Afficher la console" if visible else "Masquer la console"
        )

    def save_fields(self) -> None:
        self.manager.save_setting("variant_url", self.input_url.text())
        self.manager.save_setting("variant_selector", self.input_selector.text())
        self.manager.save_setting("variant_output", self.input_output.text())


class PageLinkGenerator(QWidget):
    """Generate image URLs for WooCommerce uploads from a local folder."""

    def __init__(self, manager: SettingsManager) -> None:
        super().__init__()
        self.manager = manager
        layout = QVBoxLayout(self)

        self.input_base_url = QLineEdit(manager.settings.get("linkgen_base_url", "https://www.planetebob.fr"))
        layout.addWidget(QLabel("Domaine WooCommerce"))
        layout.addWidget(self.input_base_url)

        self.input_date = QLineEdit(manager.settings.get("linkgen_date", "2025/07"))
        layout.addWidget(QLabel("Date (format YYYY/MM)"))
        layout.addWidget(self.input_date)

        self.button_folder = QPushButton("Choisir le dossier d'images")
        self.button_folder.clicked.connect(self.choose_folder)
        layout.addWidget(self.button_folder)

        self.output_links = QTextEdit()
        self.output_links.setPlaceholderText("Les URLs g\u00e9n\u00e9r\u00e9es s'afficheront ici.")
        layout.addWidget(self.output_links)

        actions = QHBoxLayout()
        self.button_generate = QPushButton("G\u00e9n\u00e9rer")
        self.button_generate.clicked.connect(self.generate_links)
        actions.addWidget(self.button_generate)

        self.button_copy = QPushButton("Copier les liens")
        self.button_copy.clicked.connect(self.copy_to_clipboard)
        actions.addWidget(self.button_copy)

        self.button_export = QPushButton("Exporter en .txt")
        self.button_export.clicked.connect(self.export_to_txt)
        actions.addWidget(self.button_export)

        layout.addLayout(actions)
        layout.addStretch()

        self.folder_path = manager.settings.get("linkgen_folder", "")
        if self.folder_path:
            self.button_folder.setText(f"Dossier : {os.path.basename(self.folder_path)}")

        for widget in [self.input_base_url, self.input_date]:
            widget.editingFinished.connect(self.save_fields)

    def choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "S\u00e9lectionner un dossier")
        if folder:
            self.folder_path = folder
            self.button_folder.setText(f"Dossier : {os.path.basename(folder)}")
            self.save_fields()

    def generate_links(self) -> None:
        if not self.folder_path:
            QMessageBox.warning(self, "Erreur", "Veuillez choisir un dossier.")
            return

        base_url = self.input_base_url.text().strip().rstrip("/")
        date_path = self.input_date.text().strip()

        links: list[str] = []
        for root, _, files in os.walk(self.folder_path):
            for fname in files:
                if fname.lower().endswith((
                    ".webp",
                    ".jpg",
                    ".jpeg",
                    ".png",
                )):
                    file_url = (
                        f"{base_url}/wp-content/uploads/{date_path}/{fname}"
                    )
                    links.append(file_url)

        if links:
            self.output_links.setText("\n".join(links))
        else:
            self.output_links.setText("Aucune image valide trouv\u00e9e dans le dossier.")
        QMessageBox.information(self, "Terminé", "La génération des liens est terminée.")

    def copy_to_clipboard(self) -> None:
        clipboard: QClipboard = QApplication.clipboard()
        clipboard.setText(self.output_links.toPlainText())
        QMessageBox.information(self, "Copi\u00e9", "Les liens ont \u00e9t\u00e9 copi\u00e9s dans le presse-papiers.")

    def export_to_txt(self) -> None:
        if not self.output_links.toPlainText():
            QMessageBox.warning(self, "Erreur", "Aucun lien \u00e0 exporter.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer sous", "liens_images.txt", "Fichier texte (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.output_links.toPlainText())
            QMessageBox.information(self, "Export\u00e9", "Les liens ont \u00e9t\u00e9 enregistr\u00e9s avec succ\u00e8s.")

    def save_fields(self) -> None:
        self.manager.save_setting("linkgen_base_url", self.input_base_url.text())
        self.manager.save_setting("linkgen_date", self.input_date.text())
        self.manager.save_setting("linkgen_folder", self.folder_path)


class Alpha2Widget(QWidget):
    """Scrape images then variants using a single URL."""

    def __init__(self, manager: SettingsManager) -> None:
        super().__init__()
        self.manager = manager
        self._export_rows: list[dict[str, str]] = []

        main_layout = QVBoxLayout(self)

        # --- Inputs -----------------------------------------------------
        group_inputs = QGroupBox("Entrées utilisateur")
        inputs_layout = QVBoxLayout(group_inputs)

        self.input_url = QLineEdit(manager.settings.get("alpha2_url", ""))
        self.input_url.setPlaceholderText("URL du produit")
        inputs_layout.addWidget(QLabel("URL du produit"))
        inputs_layout.addWidget(self.input_url)

        dir_layout = QHBoxLayout()
        self.input_dir = QLineEdit(manager.settings.get("alpha2_parent", "images"))
        dir_layout.addWidget(self.input_dir)
        self.button_dir = QPushButton("\U0001F4C2 Choisir dossier")
        self.button_dir.clicked.connect(self.browse_dir)
        dir_layout.addWidget(self.button_dir)
        inputs_layout.addWidget(QLabel("Dossier parent"))
        inputs_layout.addLayout(dir_layout)

        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, 32)
        self.spin_threads.setValue(manager.settings.get("alpha2_threads", 3))
        inputs_layout.addWidget(QLabel("Threads parallèles"))
        inputs_layout.addWidget(self.spin_threads)
        inputs_layout.addStretch()

        # --- Actions ----------------------------------------------------
        group_actions = QGroupBox("Actions")
        actions_layout = QVBoxLayout(group_actions)
        self.button_start = QPushButton("Lancer le Scraping complet")
        self.button_start.clicked.connect(self.start_full_scraping)
        self.button_delete = QPushButton("Supprimer les dossiers")
        self.button_delete.clicked.connect(self.delete_folders)
        actions_layout.addWidget(self.button_start)
        actions_layout.addWidget(self.button_delete)
        actions_layout.addStretch()

        # --- State & Console -------------------------------------------
        group_state = QGroupBox("État & Console")
        state_layout = QVBoxLayout(group_state)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        state_layout.addWidget(self.progress)
        self.label_timer = QLabel("Temps restant : ...")
        state_layout.addWidget(self.label_timer)
        self.button_toggle_console = QPushButton("Masquer la console")
        self.button_toggle_console.clicked.connect(self.toggle_console)
        state_layout.addWidget(self.button_toggle_console)
        self.log_view = QPlainTextEdit(readOnly=True)
        state_layout.addWidget(self.log_view)
        state_layout.addStretch()

        # --- Export -----------------------------------------------------
        group_export = QGroupBox("Export")
        export_layout = QVBoxLayout(group_export)
        self.button_export = QPushButton("Exporter Excel")
        self.button_export.clicked.connect(self.export_excel)
        export_layout.addWidget(self.button_export)
        export_layout.addStretch()

        main_layout.addWidget(group_inputs)
        main_layout.addWidget(group_actions)
        main_layout.addWidget(group_state)
        main_layout.addWidget(group_export)
        main_layout.addStretch()

        self.images_worker: ScraperImagesWorker | None = None
        self.variant_worker: VariantFetchWorker | None = None

        for w in [self.input_url, self.input_dir]:
            w.editingFinished.connect(self.save_fields)
        self.spin_threads.valueChanged.connect(self.save_fields)

    # --- Slots ---------------------------------------------------------
    def browse_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier")
        if directory:
            self.input_dir.setText(directory)
            self.save_fields()

    def start_full_scraping(self) -> None:
        url = self.input_url.text().strip()
        if not url:
            self.log_view.appendPlainText("Veuillez renseigner l'URL.")
            return

        dest = Path(self.input_dir.text().strip() or "images")
        selector = self.manager.settings.get(
            "images_selector",
            scraper_images.DEFAULT_CSS_SELECTOR,
        )

        self.button_start.setEnabled(False)
        self.progress.setValue(0)
        self.log_view.clear()

        self.save_fields()

        self.images_worker = ScraperImagesWorker(
            [url],
            dest,
            selector,
            False,
            False,
            None,
            self.spin_threads.value(),
        )
        self.images_worker.log.connect(self.log_view.appendPlainText)
        self.images_worker.progress.connect(self.update_progress)
        self.images_worker.finished.connect(self.start_variant_phase)

        self.images_done = 0
        self.total_images = 0
        self.start_time = time.perf_counter()
        self.images_worker.start()

    def start_variant_phase(self) -> None:
        url = self.input_url.text().strip()
        self.variant_worker = VariantFetchWorker(url)
        self.variant_worker.log.connect(self.log_view.appendPlainText)
        self.variant_worker.result.connect(self.process_variants)
        self.variant_worker.finished.connect(self.on_variant_finished)
        self.variant_worker.start()

    def process_variants(self, title: str, mapping: dict) -> None:
        domain = self.manager.settings.get("linkgen_base_url", "https://example.com")
        date_path = self.manager.settings.get("linkgen_date", "2025/07")
        self._export_rows = []
        self.log_view.appendPlainText(title)
        for name, img in mapping.items():
            wp_url = self._build_wp_url(domain, date_path, img)
            self.log_view.appendPlainText(f"{name} -> {wp_url}")
            self._export_rows.append({"Product": title, "Variant": name, "Image": wp_url})

    def update_progress(self, done: int, total: int) -> None:
        self.images_done = done
        self.total_images = total
        value = int(done / total * 100) if total else 0
        self.progress.setValue(value)
        if done == 0 or total == 0:
            self.label_timer.setText("Temps restant : ...")
            return
        elapsed = time.perf_counter() - self.start_time
        average = elapsed / done
        remaining = (total - done) * average
        if remaining >= 60:
            minutes = int(remaining / 60 + 0.5)
            self.label_timer.setText(f"Temps restant : {minutes} minute(s)")
        else:
            seconds = int(remaining + 0.5)
            self.label_timer.setText(f"Temps restant : {seconds} seconde(s)")

    def toggle_console(self) -> None:
        visible = self.log_view.isVisible()
        self.log_view.setVisible(not visible)
        self.button_toggle_console.setText(
            "Afficher la console" if visible else "Masquer la console"
        )

    def on_variant_finished(self) -> None:
        self.button_start.setEnabled(True)
        self.label_timer.setText("Temps restant : 0 seconde(s)")
        QMessageBox.information(self, "Terminé", "Le scraping complet est terminé.")
        self.progress.setValue(0)

    def delete_folders(self) -> None:
        dest = Path(self.input_dir.text().strip() or "images")
        if not dest.exists():
            QMessageBox.information(self, "Info", "Le dossier spécifié n'existe pas.")
            return
        reply = QMessageBox.question(
            self,
            "Confirmer la suppression",
            f"Supprimer tout le contenu de {dest} ?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            for child in dest.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
            QMessageBox.information(self, "Supprimé", "Les dossiers ont été supprimés.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la suppression : {exc}")

    def export_excel(self) -> None:
        if not self._export_rows:
            QMessageBox.warning(self, "Erreur", "Aucune donnée à exporter.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer sous", "resultats.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        import pandas as pd

        df = pd.DataFrame(self._export_rows)
        try:
            df.to_excel(path, index=False)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erreur", str(exc))
        else:
            QMessageBox.information(self, "Exporté", "Fichier enregistré")

    def save_fields(self) -> None:
        self.manager.save_setting("alpha2_url", self.input_url.text())
        self.manager.save_setting("alpha2_parent", self.input_dir.text())
        self.manager.save_setting("alpha2_threads", self.spin_threads.value())

    @staticmethod
    def _build_wp_url(domain: str, date_path: str, img_url: str) -> str:
        filename = img_url.split("/")[-1].split("?")[0]
        filename = re.sub(r"-\d+(?=\.\w+$)", "", filename)
        domain = domain.rstrip("/")
        date_path = date_path.strip("/")
        return f"{domain}/wp-content/uploads/{date_path}/{filename}"



class PageSettings(QWidget):
    """UI page allowing the user to customise the application."""

    def __init__(self, manager: SettingsManager, apply_cb) -> None:
        super().__init__()
        self.manager = manager
        self.apply_cb = apply_cb
        layout = QVBoxLayout(self)

        self.input_button_bg = QLineEdit(manager.settings["button_bg_color"])
        layout.addWidget(QLabel("Couleur de fond des boutons"))
        layout.addWidget(self.input_button_bg)

        self.input_button_text = QLineEdit(manager.settings["button_text_color"])
        layout.addWidget(QLabel("Couleur du texte des boutons"))
        layout.addWidget(self.input_button_text)

        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["clair", "sombre"])
        self.combo_theme.setCurrentIndex(1 if manager.settings["theme"] == "dark" else 0)
        layout.addWidget(QLabel("Th\u00e8me global"))
        layout.addWidget(self.combo_theme)

        self.spin_radius_button = QSpinBox()
        self.spin_radius_button.setRange(0, 30)
        self.spin_radius_button.setValue(manager.settings["button_radius"])
        layout.addWidget(QLabel("Radius des boutons"))
        layout.addWidget(self.spin_radius_button)

        self.spin_radius_input = QSpinBox()
        self.spin_radius_input.setRange(0, 30)
        self.spin_radius_input.setValue(manager.settings["lineedit_radius"])
        layout.addWidget(QLabel("Radius des champs de saisie"))
        layout.addWidget(self.spin_radius_input)

        self.spin_radius_console = QSpinBox()
        self.spin_radius_console.setRange(0, 30)
        self.spin_radius_console.setValue(manager.settings["console_radius"])
        layout.addWidget(QLabel("Radius de la console"))
        layout.addWidget(self.spin_radius_console)

        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(manager.settings["font_family"]))
        layout.addWidget(QLabel("Police"))
        layout.addWidget(self.font_combo)

        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(6, 30)
        self.spin_font_size.setValue(manager.settings["font_size"])
        layout.addWidget(QLabel("Taille de police"))
        layout.addWidget(self.spin_font_size)

        self.checkbox_anim = QCheckBox("Activer les animations")
        self.checkbox_anim.setChecked(manager.settings["animations"])
        layout.addWidget(self.checkbox_anim)

        self.checkbox_update = QCheckBox("Autoriser la mise à jour (git pull)")
        self.checkbox_update.setChecked(manager.settings.get("enable_update", True))
        layout.addWidget(self.checkbox_update)

        self.checkbox_headless = QCheckBox("Exécuter Selenium en mode headless")
        self.checkbox_headless.setChecked(manager.settings.get("headless", True))
        layout.addWidget(self.checkbox_headless)

        self.input_driver_path = QLineEdit(manager.settings.get("driver_path", ""))
        layout.addWidget(QLabel("Chemin ChromeDriver"))
        layout.addWidget(self.input_driver_path)

        self.input_user_agent = QLineEdit(
            manager.settings.get("user_agent", scraper_images.USER_AGENT)
        )
        layout.addWidget(QLabel("User-Agent"))
        layout.addWidget(self.input_user_agent)

        self.button_reset = QPushButton("R\u00e9initialiser les param\u00e8tres")
        layout.addWidget(self.button_reset)

        self.button_update = QPushButton("\ud83d\udd04 Mettre \u00e0 jour l'app (Git Pull)")
        layout.addWidget(self.button_update)

        layout.addStretch()

        for w in [
            self.input_button_bg,
            self.input_button_text,
            self.combo_theme,
            self.spin_radius_button,
            self.spin_radius_input,
            self.spin_radius_console,
            self.font_combo,
            self.spin_font_size,
            self.checkbox_anim,
            self.checkbox_update,
            self.checkbox_headless,
            self.input_driver_path,
            self.input_user_agent,
        ]:
            if isinstance(w, QLineEdit):
                w.editingFinished.connect(self.update_settings)
            elif isinstance(w, QComboBox):
                w.currentIndexChanged.connect(self.update_settings)
            elif isinstance(w, QSpinBox):
                w.valueChanged.connect(self.update_settings)
            elif isinstance(w, QCheckBox):
                w.stateChanged.connect(self.update_settings)
            elif isinstance(w, QFontComboBox):
                w.currentFontChanged.connect(self.update_settings)

        self.button_reset.clicked.connect(self.reset_settings)
        self.button_update.clicked.connect(self.update_and_restart)

    def update_settings(self) -> None:
        s = self.manager.settings
        s["button_bg_color"] = self.input_button_bg.text() or s["button_bg_color"]
        s["button_text_color"] = self.input_button_text.text() or s["button_text_color"]
        s["theme"] = "dark" if self.combo_theme.currentIndex() == 1 else "light"
        s["button_radius"] = self.spin_radius_button.value()
        s["lineedit_radius"] = self.spin_radius_input.value()
        s["console_radius"] = self.spin_radius_console.value()
        s["font_family"] = self.font_combo.currentFont().family()
        s["font_size"] = self.spin_font_size.value()
        s["animations"] = self.checkbox_anim.isChecked()
        s["enable_update"] = self.checkbox_update.isChecked()
        s["headless"] = self.checkbox_headless.isChecked()
        s["driver_path"] = self.input_driver_path.text().strip()
        s["user_agent"] = self.input_user_agent.text().strip() or scraper_images.USER_AGENT
        self.manager.save_setting("headless", s["headless"])
        self.manager.save_setting("user_agent", s["user_agent"])
        self.manager.save()
        self.apply_cb()

    def reset_settings(self) -> None:
        self.manager.reset()
        self.input_button_bg.setText(self.manager.settings["button_bg_color"])
        self.input_button_text.setText(self.manager.settings["button_text_color"])
        self.combo_theme.setCurrentIndex(1 if self.manager.settings["theme"] == "dark" else 0)
        self.spin_radius_button.setValue(self.manager.settings["button_radius"])
        self.spin_radius_input.setValue(self.manager.settings["lineedit_radius"])
        self.spin_radius_console.setValue(self.manager.settings["console_radius"])
        self.font_combo.setCurrentFont(QFont(self.manager.settings["font_family"]))
        self.spin_font_size.setValue(self.manager.settings["font_size"])
        self.checkbox_anim.setChecked(self.manager.settings["animations"])
        self.checkbox_update.setChecked(self.manager.settings.get("enable_update", True))
        self.checkbox_headless.setChecked(self.manager.settings.get("headless", True))
        self.input_driver_path.setText(self.manager.settings.get("driver_path", ""))
        self.input_user_agent.setText(
            self.manager.settings.get("user_agent", scraper_images.USER_AGENT)
        )
        self.manager.save()
        self.apply_cb()

    def update_and_restart(self) -> None:
        """Run git pull after confirmation and restart the app if successful."""
        if not self.manager.settings.get("enable_update", True):
            QMessageBox.information(
                self,
                "Mise \u00e0 jour d\u00e9sactiv\u00e9e",
                "La mise \u00e0 jour par git pull est d\u00e9sactiv\u00e9e dans les param\u00e8tres.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Confirmer la mise \u00e0 jour",
            "Ex\u00e9cuter 'git pull' puis red\u00e9marrer l'application ?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            output = subprocess.check_output(
                ["git", "pull", "origin", "main"],
                stderr=subprocess.STDOUT,
                text=True,
            )
        except FileNotFoundError:
            QMessageBox.critical(
                self,
                "Erreur",
                "Git n'est pas install\u00e9 ou introuvable.",
            )
            return
        except subprocess.CalledProcessError as exc:
            msg = exc.output or str(exc)
            low = msg.lower()
            if "unable to access" in low or "could not resolve host" in low:
                msg = f"Erreur r\u00e9seau lors de la mise \u00e0 jour :\n{msg}"
            QMessageBox.critical(
                self,
                "Erreur lors de la mise \u00e0 jour",
                msg,
            )
            return

        QMessageBox.information(self, "Mise \u00e0 jour", output)
        QTimer.singleShot(1000, lambda: os.execv(sys.executable, [sys.executable] + sys.argv))


class MainWindow(QMainWindow):
    def __init__(self, settings: SettingsManager):
        super().__init__()
        self.settings = settings
        self.setWindowTitle("Interface Py")

        self.profile_manager = SiteProfileManager()

        # Sidebar buttons
        labels = [
            "Profils",
            "Scrap Liens Collection",
            "Scraper Images",
            "Scrap Description",
            "Scrap Prix",
            "Générateur de lien",
            "Moteur Variante",
            "Alpha",
            "Alpha 2",
            "Paramètres",
        ]

        icon_names = [
            "profile.svg",
            "links.svg",
            "images.svg",
            "description.svg",
            "variant.svg",
            "linkgen.svg",
            "variant.svg",
            "alpha.svg",
            "alpha.svg",
            "settings.svg",
        ]
        self.icon_paths = [ICONS_DIR / name for name in icon_names]

        self.sidebar = QWidget()
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(0, 0, 0, 0)

        self.side_buttons: list[QToolButton] = []
        for i, (text, icon) in enumerate(zip(labels, self.icon_paths)):
            section = CollapsibleSection(
                text,
                QIcon(str(icon)),
                lambda checked=False, i=i: self.show_page(i),
            )
            side_layout.addWidget(section)
            self.side_buttons.append(section.page_button)
        side_layout.addStretch()

        # Top bar
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        self.toggle_sidebar_btn = QToolButton()
        self.toggle_sidebar_btn.setArrowType(Qt.LeftArrow)
        self.toggle_sidebar_btn.clicked.connect(self.toggle_sidebar)
        self.toolbar.addWidget(self.toggle_sidebar_btn)

        self.label_title = QToolButton()
        self.label_title.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.label_title.setIcon(QIcon(str(self.icon_paths[0])))
        self.label_title.setIconSize(QSize(24, 24))
        self.label_title.setText(labels[0])
        self.label_title.setEnabled(False)
        self.toolbar.addWidget(self.label_title)

        self.stack = QStackedWidget()
        self.page_profiles = PageProfiles(self.profile_manager, self)
        self.page_scrap = PageScrapLienCollection(settings)
        self.page_images = PageScraperImages(settings)
        self.page_desc = PageScrapDescription(settings)
        self.page_price = PageScrapPrice(settings)
        self.page_linkgen = PageLinkGenerator(settings)
        self.page_variants = PageVariantScraper(settings)
        self.page_alpha = AlphaEngine()
        self.page_alpha2 = Alpha2Widget(settings)
        self.page_settings = PageSettings(settings, self.apply_settings)
        self.stack.addWidget(self.page_profiles)
        self.stack.addWidget(self.page_scrap)
        self.stack.addWidget(self.page_images)
        self.stack.addWidget(self.page_desc)
        self.stack.addWidget(self.page_price)
        self.stack.addWidget(self.page_linkgen)
        self.stack.addWidget(self.page_variants)
        self.stack.addWidget(self.page_alpha)
        self.stack.addWidget(self.page_alpha2)
        self.stack.addWidget(self.page_settings)

        self.page_images.input_source.editingFinished.connect(
            lambda: self.profile_manager.detect_and_apply(
                self.page_images.input_source.text(), self
            )
        )
        self.page_scrap.input_url.editingFinished.connect(
            lambda: self.profile_manager.detect_and_apply(
                self.page_scrap.input_url.text(), self
            )
        )
        self.page_price.input_url.editingFinished.connect(
            lambda: self.profile_manager.detect_and_apply(
                self.page_price.input_url.text(), self
            )
        )

        self.stack.currentChanged.connect(self.update_title)

        # Layout central avec scroll
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self.sidebar.setFixedWidth(180)
        self.scroll_area = QScrollArea()
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.stack)

        # Splitter to allow sidebar resizing
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.scroll_area)
        self.splitter.setStretchFactor(1, 1)
        layout.addWidget(self.splitter)
        self.setCentralWidget(container)

        self.sidebar_visible = True

        # Set initial page
        self.show_page(0)

        self.apply_settings()

    def show_page(self, index: int) -> None:
        """Display page at given index."""
        self.stack.setCurrentIndex(index)
        if 0 <= index < len(self.side_buttons):
            for i, btn in enumerate(self.side_buttons):
                btn.setChecked(i == index)
        self.update_title(index)

    def update_title(self, index: int) -> None:
        """Update title label when page changes."""
        if 0 <= index < len(self.side_buttons):
            self.label_title.setText(self.side_buttons[index].text())
            self.label_title.setIcon(QIcon(str(self.icon_paths[index])))

    def toggle_sidebar(self) -> None:
        """Show or hide the sidebar and update arrow direction."""
        self.sidebar_visible = not self.sidebar_visible
        self.sidebar.setVisible(self.sidebar_visible)
        arrow = Qt.LeftArrow if self.sidebar_visible else Qt.RightArrow
        self.toggle_sidebar_btn.setArrowType(arrow)

    def apply_settings(self) -> None:
        apply_settings(QApplication.instance(), self.settings.settings)


def main() -> None:
    app = QApplication(sys.argv)
    manager = SettingsManager()
    load_stylesheet()
    window = MainWindow(manager)
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
