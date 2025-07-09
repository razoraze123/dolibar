import json
from pathlib import Path
from PySide6.QtGui import QColor, QFont

DEFAULT_SETTINGS = {
    "button_bg_color": "#007BFF",
    "button_text_color": "white",
    "theme": "light",  # 'light' or 'dark'
    "button_radius": 8,
    "lineedit_radius": 6,
    "console_radius": 6,
    "font_family": "Consolas",
    "font_size": 13,
    "animations": True,
    "enable_update": True,
    "driver_path": "",
    "headless": True,
    "user_agent": "ScrapImageBot/1.0",

    # Last used values for scrapers
    "scrap_lien_url": "",
    "scrap_lien_output": "products.txt",
    "scrap_lien_selector": "",
    "scrap_lien_format": "txt",

    "images_url": "",
    "images_file": "",
    "images_dest": "images",
    "images_selector": "",
    "images_alt_json": "product_sentences.json",
    "images_max_threads": 4,

    "desc_url": "",
    "desc_selector": "",
    "desc_output": "description.html",

    "price_url": "",
    "price_selector": "",
    "price_output": "price.txt",

    "variant_url": "",
    "variant_selector": "",
    "variant_output": "variants.txt",

    "linkgen_base_url": "https://www.planetebob.fr",
    "linkgen_date": "2025/07",
    "linkgen_folder": "",
}


class SettingsManager:
    def __init__(self, path: str = "settings.json") -> None:
        self.path = Path(path)
        self.settings = DEFAULT_SETTINGS.copy()
        self.load_settings()

    def load(self) -> None:
        """Deprecated compatibility alias for load_settings."""
        self.load_settings()

    def load_settings(self) -> None:
        if self.path.is_file():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.settings.update(data)
            except Exception:
                pass

    def save(self) -> None:
        """Write current settings to disk."""
        try:
            self.path.write_text(json.dumps(self.settings, indent=2), encoding="utf-8")
        except Exception:
            pass

    def save_setting(self, key: str, value) -> None:
        """Update a single setting and persist it."""
        self.settings[key] = value
        self.save()

    def reset(self) -> None:
        self.reset_settings()

    def reset_settings(self) -> None:
        self.settings = DEFAULT_SETTINGS.copy()
        self.save()


def darker(color: str, factor: int = 120) -> str:
    qcolor = QColor(color)
    return qcolor.darker(factor).name()


def apply_settings(app, settings: dict) -> None:
    """Apply visual settings to the QApplication."""
    font = QFont(settings["font_family"], settings["font_size"])
    app.setFont(font)

    bg = settings["button_bg_color"]
    hover = darker(bg, 110 if settings.get("animations", True) else 100)
    pressed = darker(bg, 130)

    if settings["theme"] == "dark":
        base_bg = "#2b2b2b"
        base_fg = "#f0f0f0"
        console_bg = "#333333"
        console_fg = "#f0f0f0"
    else:
        base_bg = "#ffffff"
        base_fg = "#000000"
        console_bg = "#fdfdfd"
        console_fg = "#222222"

    style = f"""
    QWidget {{
        background-color: {base_bg};
        color: {base_fg};
        font-family: {settings['font_family']};
        font-size: {settings['font_size']}px;
    }}
    QPushButton {{
        background-color: {bg};
        color: {settings['button_text_color']};
        border-radius: {settings['button_radius']}px;
        padding: 8px 16px;
        font-weight: bold;
        border: none;
    }}
    QPushButton:hover {{
        background-color: {hover};
    }}
    QPushButton:pressed {{
        background-color: {pressed};
    }}
    QPushButton:disabled {{
        background-color: #cccccc;
        color: #666666;
    }}
    QLineEdit {{
        border: 1px solid #cccccc;
        border-radius: {settings['lineedit_radius']}px;
        padding: 6px;
    }}
    QPlainTextEdit {{
        background-color: {console_bg};
        color: {console_fg};
        border: 1px solid #cccccc;
        border-radius: {settings['console_radius']}px;
        padding: 6px;
    }}
    QProgressBar {{
        color: #000000;
        border: 2px solid #555;
        border-radius: 5px;
        text-align: center;
        font-weight: bold;
        height: 20px;
        background-color: #f0f0f0;
    }}
    QProgressBar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00c6ff, stop:1 #0072ff);
        border-radius: 5px;
        margin: 1px;
    }}
    """
    app.setStyleSheet(style)
