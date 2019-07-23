import requests
import os.path
import json
import time


def format_to_type(format):
    format_type = "other"
    if format == "movie":
        format_type = "movie"
    if format == "show" or format == "series":
        format_type = "episode"
    return format_type


def seen():
    seen_list = {}
    for watch_list in ["watchlist", "watched"]:
        for watch_type in ["movie", "show"]:
            api = requests.get(f"https://api.trakt.tv/sync/{watch_list}/{watch_type}s", headers={"trakt-api-version": "2", "trakt-api-key": data["user"]["client_id"], "Authorization": f"Bearer {data['user']['access_token']}"}).json()
            for entry in api:
                seasons = {}
                if watch_type == "show" and "seasons" in entry:
                    for season in entry["seasons"]:
                        last_episode_season = 0
                        for episode in season["episodes"]:
                            if ("plays" in episode and episode["plays"] > 0) or ("completed" in episode and episode["completed"]):
                                last_episode_season = episode["number"]
                        seasons[season["number"]] = {"episodes": 99, "progress": last_episode_season}
                if not seasons:
                    seasons = {1: {"episodes": 99 if watch_type != "movie" else 1, "progress": 0 if watch_list == "watchlist" else 1}}
                seen_list[entry[watch_type]["ids"]["trakt"]] = {
                    "completed": (seasons[max(seasons)]["progress"] == seasons[max(seasons)]["episodes"]) if watch_type != "movie" else (False if watch_list == "watchlist" else True),
                    "seasons": seasons,
                    "type": format_to_type(watch_type),
                    "titles": [entry[watch_type]["title"]]
                }
    return seen_list


def update(id, season, progress, completed, format):
    global data
    post = {"movies" if format == "movie" else "shows": {"ids": {"trakt": id}}, "progress": 100}
    if progress == 0:
        post = {"movies" if format == "movie" else "shows": [{"ids": {"trakt": id}}]}
        api = requests.post("https://api.trakt.tv/sync/watchlist", headers={"trakt-api-version": "2", "trakt-api-key": data["user"]["client_id"], "Authorization": f"Bearer {data['user']['access_token']}"}, json=post).json()
        return {"id": id}
    if format == "episode":
        post["episode"] = {"season": season, "number": progress}
    api = requests.post("https://api.trakt.tv/scrobble/stop", headers={"trakt-api-version": "2", "trakt-api-key": data["user"]["client_id"], "Authorization": f"Bearer {data['user']['access_token']}"}, json=post)
    if api.status_code == 404:
        return False
    api = api.json()
    if id not in data["list"]:
        data["list"][id] = {"completed": False, "seasons": {season: {"episodes": 99, "progress": progress}}, "type": format, "titles": []}
    elif season in data["list"][id]["seasons"]:
        data["list"][id]["seasons"][season]["progress"] = progress
    else:
        data["list"][id]["seasons"][season] = {"episodes": 99, "progress": progress}
    return {"id": id, **data["list"][id]}


def search(name):
    api = requests.get("https://api.trakt.tv/search/movie,show", params={"query": name, "fields": "title,translations,aliases"}, headers={"trakt-api-version": "2", "trakt-api-key": data["user"]["client_id"], "Authorization": f"Bearer {data['user']['access_token']}"}).json()
    results = {}
    for entry in api:
        seasons = {1: {"episodes": 1}}
        if entry["type"] == "show":
            sapi = requests.get(f"https://api.trakt.tv/shows/{entry[entry['type']]['ids']['trakt']}/seasons?extended=full", params={"query": name, "fields": "title,translations,aliases"}, headers={"trakt-api-version": "2", "trakt-api-key": data["user"]["client_id"], "Authorization": f"Bearer {data['user']['access_token']}"}).json()
            for season in sapi:
                seasons[season["number"]] = {"episodes": season["episode_count"]}
        results[entry[entry["type"]]["ids"]["trakt"]] = {"seasons": seasons, "type": format_to_type(entry["type"]), "titles": [entry[entry["type"]]["title"]]}
    return results


def token(client_id, client_secret):
    start = time.time()
    time_passed = 0
    api = requests.post("https://api.trakt.tv/oauth/device/code", json={"client_id": client_id}).json()
    print("Please visit the following link in your browser", api["verification_url"])
    print("and enter this code:", api["user_code"])
    while True:
        time_passed = time.time() - start
        if time_passed > api["expires_in"]:
            return False
        time.sleep(api["interval"])
        r = requests.post("https://api.trakt.tv/oauth/device/token", json={"code": api["device_code"], "client_id": client_id, "client_secret": client_secret})
        if r.status_code == 200:
            api = r.json()
            return {"access_token": api["access_token"], "refresh_token": api["refresh_token"]}


def user():
    return requests.get("https://api.trakt.tv/users/me", headers={"trakt-api-version": "2", "trakt-api-key": data["user"]["client_id"], "Authorization": f"Bearer {data['user']['access_token']}"}).json()["username"]


def refresh():
    tokens = requests.post("https://api.trakt.tv/oauth/token", data={"refresh_token": data["user"]["refresh_token"], "client_id": data["user"]["client_id"], "client_secret": data["user"]["client_secret"], "redirect_uri": "urn:ietf:wg:oauth:2.0:oob", "grant_type": "refresh_token"}).json()
    return (tokens["access_token"], tokens["refresh_token"])


config_file = os.path.join(os.path.dirname(__file__), "trakt.json")

if os.path.isfile(config_file):
    with open(config_file, encoding="utf-8") as fh:
        data = json.load(fh)
    print("Updating Trakt.tv...")
    data["user"]["access_token"], data["user"]["refresh_token"] = refresh()
    with open(config_file, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
else:
    while True:
        print("Please visit the following link in your browser https://trakt.tv/oauth/applications/new")
        print("- Give your app a name")
        print("- Set the redirect URI to 'urn:ietf:wg:oauth:2.0:oob'")
        print("- Enable the '/scrobble' permission")
        print("- Press 'Save App'")
        client_id = input("Enter your Trakt.tv client id: ")
        client_secret = input("Enter your Trakt.tv client secret: ")
        tokens = token(client_id, client_secret)
        if tokens:
            break
        print("Trakt.tv session expired")
    data = {"user": {"client_id": client_id, "client_secret": client_secret, **tokens}}
    data["user"]["name"] = user()

data["list"] = seen()

with open(config_file, "w", encoding="utf-8") as fh:
    json.dump(data, fh, ensure_ascii=False)

cache = {}
