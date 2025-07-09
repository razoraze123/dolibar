#!/usr/bin/env python3
"""Extract and save the price of a product using Selenium."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from driver_utils import setup_driver

DEFAULT_SELECTOR = ".price"


def extract_price(url: str, css_selector: str = DEFAULT_SELECTOR) -> str:
    """Return the text content of the element matching *css_selector* on *url*."""
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")

    driver = setup_driver()
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
        )
        element = driver.find_element(By.CSS_SELECTOR, css_selector)
        price = element.get_attribute("innerText")
        logging.info("\u2714\ufe0f Prix extrait avec succès")
        return price.strip()
    finally:
        driver.quit()


def save_price_to_file(price: str, filename: Path = Path("price.txt")) -> None:
    """Save *price* into *filename* encoded as UTF-8."""
    filename.parent.mkdir(parents=True, exist_ok=True)
    filename.write_text(price, encoding="utf-8")
    logging.info("\U0001F4BE Prix enregistré dans %s", filename.resolve())


def scrape_price(url: str, selector: str, output: Path) -> None:
    """High level helper combining extraction and saving."""
    price = extract_price(url, selector)
    save_price_to_file(price, output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extraire le prix d'un produit et le sauvegarder dans un fichier.",
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="URL du produit (si absent, demande à l'exécution)",
    )
    parser.add_argument(
        "-s",
        "--selector",
        default=DEFAULT_SELECTOR,
        help="Sélecteur CSS du prix (defaut: %(default)s)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="price.txt",
        help="Fichier de sortie (defaut: %(default)s)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Niveau de logging (defaut: %(default)s)",
    )
    args = parser.parse_args()

    if not args.url:
        args.url = input("\U0001F517 Entrez l'URL du produit : ").strip()

    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s: %(message)s")

    try:
        scrape_price(args.url, args.selector, Path(args.output))
    except Exception as exc:  # noqa: BLE001
        logging.error("%s", exc)


if __name__ == "__main__":
    main()
