"""Extract product variants from a web page."""
from __future__ import annotations

import random
import time

import argparse
import logging
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from driver_utils import setup_driver

DEFAULT_SELECTOR = ".variant-picker__option-values span.sr-only"


def extract_variants(url: str, selector: str = DEFAULT_SELECTOR) -> tuple[str, list[str]]:
    """Return product title and list of variants found on *url*."""
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")

    driver = setup_driver()
    try:
        logging.info("\U0001F310 Chargement de la page %s", url)
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        title = driver.find_element(By.CSS_SELECTOR, "h1").text.strip()
        elems = driver.find_elements(By.CSS_SELECTOR, selector)
        variants = [e.text.strip() for e in elems if e.text.strip()]
        logging.info("\u2714\ufe0f %d variante(s) d\u00e9tect\u00e9e(s)", len(variants))
        return title, variants
    finally:
        driver.quit()


def extract_variants_with_images(url: str) -> tuple[str, dict[str, str]]:
    """Return product title and a mapping of variant name to image URL."""
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")

    driver = setup_driver()
    try:
        logging.info("\U0001F310 Chargement de la page %s", url)
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h1"))
        )
        title = driver.find_element(By.CSS_SELECTOR, "h1").text.strip()

        container = driver.find_element(By.CSS_SELECTOR, ".variant-picker__option-values")
        inputs = container.find_elements(By.CSS_SELECTOR, "input[type='radio'].sr-only")

        results: dict[str, str] = {}
        for inp in inputs:
            name = inp.get_attribute("value")
            if not name or name in results:
                continue

            img_elem = driver.find_element(By.CSS_SELECTOR, ".product-gallery__media.is-selected img")
            old_src = img_elem.get_attribute("src")

            if inp.get_attribute("checked") is None:
                driver.execute_script("arguments[0].click();", inp)
                time.sleep(random.uniform(0.1, 0.2))
                WebDriverWait(driver, 5).until(
                    lambda d: d.find_element(By.CSS_SELECTOR, ".product-gallery__media.is-selected img").get_attribute("src") != old_src
                )
                img_elem = driver.find_element(By.CSS_SELECTOR, ".product-gallery__media.is-selected img")

            src = img_elem.get_attribute("src")
            if src.startswith("//"):
                src = "https:" + src
            results[name] = src
            logging.info("%s -> %s", name, src)

        return title, results
    finally:
        driver.quit()


def save_to_file(title: str, variants: list[str], path: Path) -> None:
    """Write *title* and *variants* into *path* as a single line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"{title}\t{', '.join(variants)}\n")
    logging.info("\U0001F4BE Variantes enregistr\u00e9es dans %s", path)


def save_images_to_file(title: str, variants: dict[str, str], path: Path) -> None:
    """Write *title* and variant/image pairs into *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"{title}\n")
        for name, img in variants.items():
            fh.write(f"{name} : {img}\n")
    logging.info("\U0001F4BE Variantes enregistr\u00e9es dans %s", path)


def scrape_variants(url: str, selector: str, output: Path) -> None:
    """High level helper combining extraction and saving."""
    title, variants = extract_variants(url, selector)
    save_to_file(title, variants, output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extrait le titre du produit et la liste des variantes." 
    )
    parser.add_argument(
        "url", nargs="?", help="URL du produit (si absent, demande \u00e0 l'ex\u00e9cution)"
    )
    parser.add_argument(
        "-s", "--selector", default=DEFAULT_SELECTOR, help="S\u00e9lecteur CSS des variantes"
    )
    parser.add_argument(
        "-o", "--output", default="variants.txt", help="Fichier de sortie"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Niveau de logging",
    )
    args = parser.parse_args()

    if not args.url:
        args.url = input("URL du produit : ").strip()

    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s: %(message)s")

    try:
        scrape_variants(args.url, args.selector, Path(args.output))
    except Exception as exc:
        logging.error("%s", exc)


if __name__ == "__main__":
    main()
