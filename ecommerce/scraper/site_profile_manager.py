import json
import logging
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse


class SiteProfileManager:
    """Handle saving/loading of site profiles."""

    def __init__(self, directory: str = "profiles") -> None:
        self.dir = Path(directory)
        self.dir.mkdir(exist_ok=True)

    def load_profile(self, path: str | Path) -> Dict[str, Any]:
        """Return profile data from *path*."""
        p = Path(path)
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            logging.warning("Failed to load profile %s: %s", path, exc)
            return {}

    def save_profile(self, path: str | Path, data: Dict[str, Any]) -> None:
        """Save *data* into *path* as JSON."""
        p = Path(path)
        try:
            p.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:
            logging.warning("Failed to save profile %s: %s", path, exc)

    def apply_profile_to_ui(self, profile: Dict[str, Any], main_window) -> None:
        """Apply CSS selectors from *profile* to the main window UI."""
        selectors = profile.get("selectors", {})
        if hasattr(main_window.page_images, "input_options"):
            main_window.page_images.input_options.setText(
                selectors.get("images", "")
            )
        if hasattr(main_window.page_images, "input_alt_json"):
            main_window.page_images.input_alt_json.setText(
                profile.get("sentences_file", "")
            )
        if hasattr(main_window.page_images, "input_urls_file"):
            main_window.page_images.input_urls_file.setText(
                profile.get("urls_file", "")
            )
        if hasattr(main_window.page_desc, "input_selector"):
            main_window.page_desc.input_selector.setText(
                selectors.get("description", "")
            )
        if hasattr(main_window.page_desc, "input_urls_file"):
            main_window.page_desc.input_urls_file.setText(
                profile.get("desc_urls_file", "")
            )
        if hasattr(main_window.page_scrap, "input_selector"):
            main_window.page_scrap.input_selector.setText(
                selectors.get("collection", "")
            )
        if hasattr(main_window, "page_price") and hasattr(
            main_window.page_price, "input_selector"
        ):
            main_window.page_price.input_selector.setText(
                selectors.get("price", "")
            )

    def detect_and_apply(self, url: str, main_window) -> None:
        """Detect site type from *url* and apply matching default profile."""
        if not url:
            return
        host = urlparse(url).netloc.lower()
        profile_name = None
        if "shopify" in host:
            profile_name = "shopify_default.json"
        elif any(key in host for key in ["woocommerce", "wordpress", "wp"]):
            profile_name = "woocommerce_default.json"

        if not profile_name:
            return

        path = self.dir / profile_name
        if not path.exists():
            return
        data = self.load_profile(path)
        self.apply_profile_to_ui(data, main_window)

