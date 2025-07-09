import logging
import json
from pathlib import Path

from site_profile_manager import SiteProfileManager


def test_load_profile_logs_warning(tmp_path, caplog):
    bad = tmp_path / "bad.json"
    bad.write_text("{ bad json }", encoding="utf-8")

    spm = SiteProfileManager(tmp_path)
    with caplog.at_level(logging.WARNING):
        data = spm.load_profile(bad)

    assert data == {}
    assert any("Failed to load profile" in record.message for record in caplog.records)


def test_detect_and_apply(tmp_path):
    woo = {"selectors": {"images": "wooimg", "description": "woodesc", "collection": "woocol"}}
    shop = {"selectors": {"images": "shopimg", "description": "shopdesc", "collection": "shopcol"}}
    (tmp_path / "woocommerce_default.json").write_text(json.dumps(woo), encoding="utf-8")
    (tmp_path / "shopify_default.json").write_text(json.dumps(shop), encoding="utf-8")

    spm = SiteProfileManager(tmp_path)

    class Field:
        def __init__(self):
            self.text = ""

        def setText(self, val):
            self.text = val

    class Dummy:
        pass

    class DummyWin:
        def __init__(self):
            self.page_images = Dummy()
            self.page_images.input_options = Field()
            self.page_desc = Dummy()
            self.page_desc.input_selector = Field()
            self.page_scrap = Dummy()
            self.page_scrap.input_selector = Field()

    mw = DummyWin()
    spm.detect_and_apply("https://example.myshopify.com", mw)
    assert mw.page_images.input_options.text == "shopimg"
    mw2 = DummyWin()
    spm.detect_and_apply("https://example.com", mw2)
    assert mw2.page_images.input_options.text == ""
