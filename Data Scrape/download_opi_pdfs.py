import os
import base64
import asyncio
from pathlib import Path
from urllib.parse import urljoin, urldefrag
from concurrent.futures import ThreadPoolExecutor

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait


MAIN_URL = "https://www.issbtests.com/issb-opi-test.html"
OUTPUT_DIR = Path("SRT") / "OPI tests and situations"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DONE_FILE = OUTPUT_DIR / "done_urls.txt"

MAX_WORKERS = 4


# -------------------------
# Progress handling
# -------------------------

def load_done_urls():
    if not DONE_FILE.exists():
        return set()

    with open(DONE_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def mark_done(url: str):
    with open(DONE_FILE, "a", encoding="utf-8") as f:
        f.write(url + "\n")


# -------------------------
# Utilities
# -------------------------

def sanitize_filename(name: str) -> str:
    invalid = '<>:"/\\|?*'
    for ch in invalid:
        name = name.replace(ch, "_")
    return name.strip()


def setup_driver():
    options = webdriver.ChromeOptions()

    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )


# -------------------------
# Link extraction
# -------------------------

def get_all_links(driver, done_urls: set):
    driver.get(MAIN_URL)

    WebDriverWait(driver, 10).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )

    anchors = driver.find_elements(By.TAG_NAME, "a")

    links = []
    seen = set()

    for a in anchors:
        href = a.get_attribute("href")
        text = a.text.strip()

        if not href:
            continue

        if "opi" not in href.lower() and "situational" not in href.lower():
            continue

        full_url = urldefrag(urljoin(MAIN_URL, href))[0]

        if full_url in done_urls:
            continue

        if full_url in seen:
            continue

        seen.add(full_url)

        links.append({
            "title": text or full_url.split("/")[-1],
            "url": full_url
        })

    return links


# -------------------------
# PDF generator
# -------------------------

def save_page_as_pdf(driver, url, filename):
    driver.get(url)

    WebDriverWait(driver, 10).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )

    pdf = driver.execute_cdp_cmd(
        "Page.printToPDF",
        {
            "printBackground": True,
            "paperWidth": 8.27,
            "paperHeight": 11.69,
            "preferCSSPageSize": True,
            "scale": 1.0
        }
    )

    pdf_data = base64.b64decode(pdf["data"])

    filepath = OUTPUT_DIR / filename
    with open(filepath, "wb") as f:
        f.write(pdf_data)

    return str(filepath)


# -------------------------
# Worker
# -------------------------

def worker(task_queue, done_lock):
    driver = setup_driver()

    try:
        while True:
            task = task_queue.get_nowait()
            if task is None:
                break

            url, filename = task

            try:
                path = save_page_as_pdf(driver, url, filename)
                print(f"[OK] {path}")

                # mark progress safely
                with done_lock:
                    mark_done(url)

            except Exception as e:
                print(f"[FAIL] {url} -> {e}")

            task_queue.task_done()

    except Exception:
        pass
    finally:
        driver.quit()


# -------------------------
# Main async controller
# -------------------------

async def run_scraper():
    import queue
    import threading

    done_urls = load_done_urls()
    done_lock = threading.Lock()

    # Step 1: extract links
    driver = setup_driver()
    try:
        links = get_all_links(driver, done_urls)
    finally:
        driver.quit()

    print(f"Found {len(links)} new links")

    # Step 2: build queue
    task_queue = queue.Queue()

    for i, item in enumerate(links, 1):
        title = sanitize_filename(item["title"])
        filename = f"{i:03d}_{title}.pdf"
        task_queue.put((item["url"], filename))

    # stop signals
    for _ in range(MAX_WORKERS):
        task_queue.put(None)

    # Step 3: run workers
    loop = asyncio.get_event_loop()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            loop.run_in_executor(executor, worker, task_queue, done_lock)
            for _ in range(MAX_WORKERS)
        ]

        await asyncio.gather(*futures)

    print("Scraping completed.")


# -------------------------
# Entry
# -------------------------

if __name__ == "__main__":
    asyncio.run(run_scraper())