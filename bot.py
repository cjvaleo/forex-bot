#!/usr/bin/env python3
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
WEBHOOK = os.environ["DISCORD_WEBHOOK"]
TZ = ZoneInfo("America/New_York")
STATE_FILE = Path(__file__).parent / "state.json"
ALERT_WINDOW = (20, 40)
HEADERS = {"User-Agent": "Mozilla/5.0 (ff-discord-bot)"}


def fetch_events():
    r = requests.get(FEED_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for e in root.findall("event"):
        if (e.findtext("country") or "").strip() != "USD":
            continue
        if (e.findtext("impact") or "").strip() != "High":
            continue
        title = (e.findtext("title") or "").strip()
        date = (e.findtext("date") or "").strip()
        time_str = (e.findtext("time") or "").strip()
        forecast = (e.findtext("forecast") or "").strip()
        previous = (e.findtext("previous") or "").strip()
        try:
            dt = datetime.strptime(f"{date} {time_str}", "%m-%d-%Y %I:%M%p").replace(tzinfo=TZ)
        except ValueError:
            dt = None
        out.append({"title": title, "date": date, "time": time_str,
                    "forecast": forecast, "previous": previous, "dt": dt})
    return out


def event_id(ev):
    return f"{ev['date']}|{ev['time']}|{ev['title']}"


def post(content):
    r = requests.post(WEBHOOK, json={"content": content}, timeout=30)
    r.raise_for_status()


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"week_start": "", "sent": []}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


def send_digest():
    events = fetch_events()
    events.sort(key=lambda e: (e["dt"] or datetime.max.replace(tzinfo=TZ), e["title"]))
    if not events:
        post("**USD Red Folder — Week Ahead**\n\nNo high-impact USD events this week.")
        save_state({"week_start": datetime.now(TZ).date().isoformat(), "sent": []})
        return
    lines = ["**USD Red Folder — Week Ahead**"]
    current_day = None
    for e in events:
        day = e["dt"].strftime("%A, %b %d") if e["dt"] else f"Tentative ({e['date']})"
        if day != current_day:
            lines.append("")
            lines.append(f"__**{day}**__")
            current_day = day
        time_str = e["dt"].strftime("%-I:%M %p ET") if e["dt"] else e["time"]
        forecast = f" — forecast {e['forecast']}" if e["forecast"] else ""
        previous = f" (prev {e['previous']})" if e["previous"] else ""
        lines.append(f"• {time_str} — {e['title']}{forecast}{previous}")
    post("\n".join(lines))
    save_state({"week_start": datetime.now(TZ).date().isoformat(), "sent": []})


def send_alerts():
    events = fetch_events()
    now = datetime.now(TZ)
    state = load_state()
    sent = set(state.get("sent", []))
    changed = False
    for e in events:
        if not e["dt"]:
            continue
        eid = event_id(e)
        if eid in sent:
            continue
        mins = int((e["dt"] - now).total_seconds() / 60)
        if not (ALERT_WINDOW[0] <= mins <= ALERT_WINDOW[1]):
            continue
        time_str = e["dt"].strftime("%-I:%M %p ET")
        forecast = f"\nForecast: {e['forecast']}" if e["forecast"] else ""
        previous = f"\nPrevious: {e['previous']}" if e["previous"] else ""
        post(f"**USD Red Folder Coming Up**\n**{e['title']}** at {time_str} (in {mins} min){forecast}{previous}")
        sent.add(eid)
        changed = True
    if changed:
        state["sent"] = sorted(sent)
        save_state(state)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "alerts"
    {"digest": send_digest, "alerts": send_alerts}[cmd]()
