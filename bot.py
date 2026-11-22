import json
import os
import re
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DISCORD = "https://discord.com/api/v10"
TITLE = "YouTube channel stats"


def request(url, headers, method="GET", payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = Request(url, data=data, method=method, headers={
        "Content-Type": "application/json", "User-Agent": "YouTubeStatsBot/1.0", **headers
    })
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def dashboard(ids, api_key):
    query = urlencode({"part": "snippet,statistics", "id": ",".join(ids), "maxResults": 50})
    result = request("https://www.googleapis.com/youtube/v3/channels?" + query,
                     {"X-Goog-Api-Key": api_key})
    channels = {item["id"]: item for item in result.get("items", [])}
    fields = []
    for channel_id in ids:
        item = channels.get(channel_id)
        if item is None:
            fields.append({"name": channel_id, "value": "Channel unavailable"})
            continue
        stats = item["statistics"]
        subs = "Hidden" if stats.get("hiddenSubscriberCount") else count(stats, "subscriberCount")
        fields.append({"name": item["snippet"]["title"][:200],
                       "value": f"Subscribers: **{subs}** · Total views: **{count(stats, 'viewCount')}**"})
    return {"embeds": [{"title": TITLE, "fields": fields,
                        "description": f"Updated <t:{int(time.time())}:R>"}],
            "allowed_mentions": {"parse": []}}


def count(stats, key):
    return f"{int(stats[key]):,}" if key in stats else "Unavailable"


def run():
    config = json.loads((ROOT / "channels.json").read_text())
    target = config["discord_channel_id"]
    ids = config["youtube_channel_ids"]
    if not re.fullmatch(r"[0-9]{17,20}", target):
        raise SystemExit("Set discord_channel_id in channels.json.")
    if not isinstance(ids, list) or not 1 <= len(ids) <= 25 or not all(
        isinstance(i, str) and re.fullmatch(r"UC[\w-]{22}", i, re.ASCII) for i in ids
    ) or len(ids) != len(set(ids)):
        raise SystemExit("Enter 1–25 unique YouTube channel IDs in channels.json.")
    auth = {"Authorization": "Bot " + os.environ["DISCORD_BOT_TOKEN"]}
    key = os.environ["YOUTUBE_API_KEY"]
    url = f"{DISCORD}/channels/{target}/messages"
    payload = dashboard(ids, key)
    me = request(DISCORD + "/users/@me", auth)["id"]
    recent = request(url + "?limit=100", auth)
    message_id = next((m["id"] for m in recent if m["author"]["id"] == me
                       and any(e.get("title") == TITLE for e in m.get("embeds", []))), None)
    if message_id:
        try:
            request(f"{url}/{message_id}", auth, "PATCH", payload)
        except HTTPError as error:
            if error.code != 404:
                raise
            message_id = None
    if message_id is None:
        message_id = request(url, auth, "POST", payload)["id"]
    print("Discord stats refreshed.")


if __name__ == "__main__":
    run()
