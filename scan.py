import os
import json
import time
import logging
import sys
from datetime import datetime, timezone
import requests

BASE_URL = "https://accounts.radie.app/account/bulk"
BATCH_SIZE = 100
SLEEP_BETWEEN_REQUESTS = 0.5
CONSECUTIVE_MISSING_LIMIT = 5000
RESTART_DELAY = 300

LOG_DIR = "logs"

os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    handlers=[
        logging.FileHandler("scanner.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

def sanitize(name: str) -> str:
    bad = r'\/:*?"<>|'
    for c in bad:
        name = name.replace(c, "_")
    return name.strip() or "unknown"

def fetch_batch(start_id: int, end_id: int):
    ids = "&id=".join(str(i) for i in range(start_id, end_id + 1))
    url = f"{BASE_URL}?id={ids}"

    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        logging.info(f"Request error {start_id}-{end_id}: {e}")
        return []

def save_account(account: dict):
    username = sanitize(account.get("username", "unknown"))
    folder = os.path.join(LOG_DIR, username)
    os.makedirs(folder, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")

    with open(os.path.join(folder, "latest.json"), "w") as f:
        json.dump(account, f, indent=2)

    with open(os.path.join(folder, f"{ts}.json"), "w") as f:
        json.dump(account, f, indent=2)

def eta(start_time, processed, total_estimate):
    if processed == 0:
        return "calculating"

    elapsed = time.time() - start_time
    rate = elapsed / processed
    remaining = max(total_estimate - processed, 0)
    return time.strftime("%H:%M:%S", time.gmtime(rate * remaining))

def run_scan():
    current_id = 1
    missing_streak = 0
    processed_batches = 0
    estimated_total = 100000

    start_time = time.time()

    logging.info("Scanner started")

    while True:
        start = current_id
        end = current_id + BATCH_SIZE - 1

        processed_batches += 1

        logging.info(f"Scanning {start}-{end}")

        data = fetch_batch(start, end)

        returned_ids = set()

        for account in data:
            aid = account.get("accountId")
            if aid is not None:
                returned_ids.add(aid)
                save_account(account)

        for i in range(start, end + 1):
            if i in returned_ids:
                missing_streak = 0
            else:
                missing_streak += 1

        logging.info(
            f"Batch {processed_batches} | "
            f"Missing streak {missing_streak} | "
            f"ETA {eta(start_time, processed_batches, estimated_total)}"
        )

        current_id += BATCH_SIZE

        if missing_streak >= CONSECUTIVE_MISSING_LIMIT:
            logging.info("Missing limit reached, restarting in 5 minutes")
            break

        time.sleep(SLEEP_BETWEEN_REQUESTS)

while True:
    run_scan()
    time.sleep(RESTART_DELAY)
