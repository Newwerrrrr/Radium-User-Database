import os
import json
import time
import logging
from datetime import datetime
from typing import List, Dict

import requests

# =========================
# CONFIG
# =========================

BASE_URL = "https://accounts.radie.app/account/bulk"
BATCH_SIZE = 100
SLEEP_BETWEEN_REQUESTS = 0.5  # 500ms
CONSECUTIVE_MISSING_LIMIT = 5000

LOG_DIR = "logs"

# =========================
# SETUP
# =========================

os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename="scanner.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

# =========================
# HELPERS
# =========================

def sanitize_folder_name(name: str) -> str:
    """Make usernames safe for folder names."""
    bad_chars = r'\/:*?"<>|'
    for c in bad_chars:
        name = name.replace(c, "_")
    return name.strip() or "unknown"


def fetch_batch(start_id: int, end_id: int) -> List[Dict]:
    """Fetch a batch of accounts from API."""
    ids = "&id=".join(str(i) for i in range(start_id, end_id + 1))
    url = f"{BASE_URL}?id={ids}"

    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()

        if isinstance(data, list):
            return data
        return []

    except Exception as e:
        logging.error(f"Request failed for {start_id}-{end_id}: {e}")
        return []


def save_user(account: Dict):
    """Save user data into logs/<username>/"""
    username = sanitize_folder_name(account.get("username", "unknown"))
    user_id = str(account.get("accountId", "unknown"))

    user_dir = os.path.join(LOG_DIR, username)
    os.makedirs(user_dir, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")

    # Save latest.json
    latest_path = os.path.join(user_dir, "latest.json")
    with open(latest_path, "w") as f:
        json.dump(account, f, indent=2)

    # Save timestamped snapshot
    snapshot_path = os.path.join(user_dir, f"{timestamp}.json")
    with open(snapshot_path, "w") as f:
        json.dump(account, f, indent=2)

    logging.info(f"Saved user {user_id} ({username})")


# =========================
# MAIN SCANNER
# =========================

def run_scan():
    current_id = 1
    consecutive_missing = 0

    logging.info("Scanner started")

    while True:
        batch_start = current_id
        batch_end = current_id + BATCH_SIZE - 1

        data = fetch_batch(batch_start, batch_end)

        returned_ids = set()

        # Process returned accounts
        for account in data:
            account_id = account.get("accountId")
            if account_id is not None:
                returned_ids.add(account_id)
                save_user(account)

        # Count missing IDs in this batch
        for i in range(batch_start, batch_end + 1):
            if i not in returned_ids:
                consecutive_missing += 1
            else:
                consecutive_missing = 0

        logging.info(
            f"Batch {batch_start}-{batch_end} "
            f"missing_streak={consecutive_missing}"
        )

        current_id += BATCH_SIZE

        # Stop condition
        if consecutive_missing >= CONSECUTIVE_MISSING_LIMIT:
            logging.info("Reached missing limit. Restarting scan.")
            break

        time.sleep(SLEEP_BETWEEN_REQUESTS)

    # Restart delay
    time.sleep(300)  # 5 minutes
    run_scan()


if __name__ == "__main__":
    run_scan()
