#!/usr/bin/env python3
"""Extract the HTML description of a product page using Selenium."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from driver_utils import setup_driver

DEFAULT_SELECTOR = ".rte"




def extract_html_description(url: str, css_selector: str = DEFAULT_SELECTOR) -> str:
    """Return the inner HTML of the first element matching *css_selector* on *url*."""
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")

    driver = setup_driver()
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
        )
        element = driver.find_element(By.CSS_SELECTOR, css_selector)
        html = element.get_attribute("innerHTML")
        logging.info("\u2714\ufe0f HTML extrait avec succès")
        return html.strip()
    finally:
        driver.quit()


def save_html_to_file(html: str, filename: Path = Path("description.html")) -> None:
    """Save *html* into *filename* encoded as UTF-8."""
    filename.parent.mkdir(parents=True, exist_ok=True)
    filename.write_text(html, encoding="utf-8")
    logging.info("\U0001F4BE Description enregistrée dans %s", filename.resolve())


def scrape_description(url: str, selector: str, output: Path) -> None:
    """High level helper combining extraction and saving."""
    html = extract_html_description(url, selector)
    save_html_to_file(html, output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extraire la description HTML d'un produit et la sauvegarder dans un fichier.",
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
        help="Sélecteur CSS de la description (defaut: %(default)s)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="description.html",
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
        scrape_description(args.url, args.selector, Path(args.output))
    except Exception as exc:
        logging.error("%s", exc)


if __name__ == "__main__":
    main()
