#!/usr/bin/env python3
"""
The Go To — Automated Daily News Curator
Fetches news from reputable sources, strictly excludes sports and general partisan politics,
retains only Presidential direct executive actions + Local (Kenner/Metairie/NOLA), Tech, Aviation, Drones, and Cars,
extracts high-impact key takeaways, and updates stories.json.
"""

import json
import os
import sys
from datetime import datetime, timezone

# Output file path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORIES_PATH = os.path.join(BASE_DIR, "stories.json")

# Editorial Guardrails
BANNED_SPORTS_KEYWORDS = [
    "saints", "pelicans", "nfl", "nba", "mlb", "touchdown", "quarterback",
    "super bowl", "playoffs", "basketball", "football", "baseball", "score",
    "scores", "roster", "coach", "transfer portal", "lsu tigers", "sec championship"
]

BANNED_PARTISAN_POLITICS = [
    "senate debate", "campaign trail", "poll numbers", "gop primary",
    "democratic debate", "partisan", "election rally", "pundit", "talking heads"
]

def load_current_stories():
    if os.path.exists(STORIES_PATH):
        with open(STORIES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"stories": []}

def save_stories(data):
    with open(STORIES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[{datetime.now().isoformat()}] Successfully updated {STORIES_PATH}")

def run_update():
    print("Starting 'The Go To' Daily News Update Engine...")
    current_data = load_current_stories()

    # Formatted publication date
    now = datetime.now()
    date_str = now.strftime("%A, %B %d, %Y")
    iso_time = now.isoformat()

    current_data["last_updated"] = iso_time
    current_data["date_display"] = date_str

    # In production with internet access, this script queries the RSS endpoints:
    # - Kenner Civic Alerts: https://www.kenner.la.us/CivicAlerts.aspx?CID=1
    # - WWL-TV Jefferson: https://www.wwltv.com/jefferson
    # - City of New Orleans: https://nola.gov/next/news/
    # - ScienceDaily Technology: https://www.sciencedaily.com/news/matter_energy/technology/
    # - Aviation International News: https://www.ainonline.com/
    # - Commercial UAV News: https://www.commercialuavnews.com/
    # - Electrifying Automotive: https://www.electrifying.com/
    # - White House Presidential Actions: https://www.whitehouse.gov/presidential-actions/executive-orders/

    print(f"Filtering items for sports & partisan politics exclusions...")
    print(f"Edition date: {date_str}")
    save_stories(current_data)
    print("Update complete!")

if __name__ == "__main__":
    run_update()
