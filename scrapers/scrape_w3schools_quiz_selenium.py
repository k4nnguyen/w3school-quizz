#!/usr/bin/env python3
"""Headless Selenium scraper for W3Schools interactive quiz pages.

This script drives a browser to click through the quiz and collect questions/options.
"""
import argparse
import json
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException


def scrape_with_selenium(start_url, headless=True, limit=0):
    opts = Options()
    if headless:
        # headless=new for newer Chrome; fallback to --headless
        try:
            opts.add_argument("--headless=new")
        except Exception:
            opts.add_argument("--headless")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    driver.get(start_url)
    results = []
    count = 0
    while True:
        time.sleep(0.2)
        try:
            qel = driver.find_element(By.ID, "qtext")
        except NoSuchElementException:
            break
        qtext = qel.text.strip()
        opts_labels = driver.find_elements(By.CSS_SELECTOR, "label.radiocontainer")
        options = [l.text.strip() for l in opts_labels]
        results.append({"question": qtext, "options": options})

        if opts_labels:
            try:
                # click the first option
                inp = opts_labels[0].find_element(By.TAG_NAME, "input")
                driver.execute_script("arguments[0].click();", inp)
            except Exception:
                pass

        # click Next
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, "button.answerbutton")
            driver.execute_script("arguments[0].click();", next_btn)
        except NoSuchElementException:
            break

        count += 1
        if limit and count >= limit:
            break

    driver.quit()
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-url", required=True)
    parser.add_argument("--output", default="quizzes_selenium.json")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--headless", action="store_true", default=True)
    args = parser.parse_args()

    data = scrape_with_selenium(args.start_url, headless=args.headless, limit=args.limit)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(data)} questions to {args.output}")


if __name__ == "__main__":
    main()
