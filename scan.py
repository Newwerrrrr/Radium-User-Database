import os
import json
import time
import logging
from datetime import datetime
from typing import List, Dict
import requests

BASE_URL = "https://accounts.radie.app/account/bulk"
BATCH_SIZE = 100
SLEEP_BETWEEN_REQUESTS = 0.5
CONSECUTIVE_MISSING_LIMIT = 5000
LOG_DIR = "logs"

os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename="scanner.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

def sanitize(name: str) -> str:
    bad = r'\/:*?"<>|'
    for c in bad:
        name = name.replace(c, "_")
    return name.strip() or "unknown"

def fetch(start: int, end: int):
    ids = "&id=".join(str(i) for i in range(start, end + 1))
    url = f"{BASE_URL}?id={ids}"
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except:
        return []

def save(account: Dict):
    username = sanitize(account.get("username", "unknown"))
    folder = os.path.join(LOG_DIR, username)
    os.makedirs(folder, exist_ok=True)

    ts = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")

    with open(os.path.join(folder, "latest.json"), "w") as f:
        json.dump(account, f, indent=2)

    with open(os.path.join(folder, f"{ts}.json"), "w") as f:
        json.dump(account, f, indent=2)

def run():
    current = 1
    missing = 0

    while True:
        start = current
        end = current + BATCH_SIZE - 1

        data = fetch(start, end)

        returned = set()

        for acc in data:
            aid = acc.get("accountId")
            if aid is not None:
                returned.add(aid)
                save(acc)

        for i in range(start, end + 1):
            if i in returned:
                missing = 0
            else:
                missing += 1

        logging.info(f"{start}-{end} missing={missing}")

        current += BATCH_SIZE

        if missing >= CONSECUTIVE_MISSING_LIMIT:
            break

        time.sleep(SLEEP_BETWEEN_REQUESTS)

while True:
    run()
    time.sleep(300)
