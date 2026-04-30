#!/usr/bin/env python3
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

WEBHOOK = os.environ["BIBLE_WEBHOOK"]
URL = "https://beta.ourmanna.com/api/v1/get/?format=json&order=daily"
HEADERS = {"User-Agent": "Mozilla/5.0 (verse-bot)"}


def main():
    if os.environ.get("FORCE_SEND") != "true":
        hour = datetime.now(ZoneInfo("America/New_York")).hour
        if hour != 8:
            print(f"Not 8am ET (hour={hour}), skipping")
            return

    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    details = r.json().get("verse", {}).get("details", {})
    text = (details.get("text") or "").strip()
    ref = (details.get("reference") or "").strip()
    version = (details.get("version") or "KJV").strip()
    if not text or not ref:
        raise RuntimeError(f"Bad response: {r.text[:500]}")

    msg = f"**Verse of the Day** — {ref} ({version})\n\n> {text}"
    rr = requests.post(WEBHOOK, json={"content": msg}, timeout=30)
    rr.raise_for_status()


if __name__ == "__main__":
    main()
