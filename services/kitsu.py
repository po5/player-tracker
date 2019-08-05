import requests
import os.path
import json


def format_to_type(format):
    format_type = "other"
    if format == "movie":
        format_type = "movie"
    if "TV" in format:
        format_type = "episode"
    return format_type


def seen():
    url = f"https://kitsu.io/api/edge/library-entries?filter[kind]=anime&filter[user_id]={data['user']['id']}&include=anime&page[limit]=500"
    seen_list = {}
    while True:
        api = requests.get(url, headers={"Authorization": f"Bearer {data['user']['access_token']}"}).json()
        if "errors" in api:
            print("Kitsu error:", api["errors"][0]["detail"])
            return False
        included = {}
        for entry in api["included"]:
            if entry["type"] == "anime":
                included[entry["id"]] = entry
        for entry in api["data"]:
            id = None
            if "anime" in entry["relationships"] and "data" in entry["relationships"]["anime"]:
                id = entry["relationships"]["anime"]["data"]["id"]
            if id:
                seen_list[id] = {"completed": entry["attributes"]["status"] == "completed", "seasons": {1: {"episodes": included[id]["attributes"]["episodeCount"], "progress": entry["attributes"]["progress"]}}, "type": format_to_type(included[id]["attributes"]["showType"]), "titles": list(set(filter(None, [*included[id]["attributes"]["titles"].values(), *list(included[id]["attributes"]["abbreviatedTitles"] if included[id]["attributes"]["abbreviatedTitles"] is not None else []), included[id]["attributes"]["canonicalTitle"]])))}
        if "next" not in api["links"]:
            return seen_list
        url = api["links"]["next"]


def update(id, season, progress, completed, format, media_type):
    global data
    status = {"status": "current", "progress": progress}
    if id not in data["list"]:
        entry = requests.get(f"https://kitsu.io/api/edge/anime/{id}", headers={"Authorization": f"Bearer {data['user']['access_token']}"}).json()["data"]["attributes"]
        if progress >= entry["episodeCount"]:
            status = {"status": "completed"}
        data["list"][id] = {"completed": status["status"] == "completed", "seasons": {1: {"episodes": entry["episodeCount"], "progress": progress}}, "type": format_to_type(entry["showType"]), "titles": list(set(filter(None, [*entry["titles"].values(), *list(entry["abbreviatedTitles"] if entry["abbreviatedTitles"] is not None else []), entry["canonicalTitle"]])))}
        requests.post("https://kitsu.io/api/edge/library-entries", json={"data": {"type": "libraryEntries", "attributes": status, "relationships": {"user": {"data": {"id": data["user"]["id"], "type": "users"}}, "anime": {"data": {"id": id, "type": "anime"}}}}}, headers={"Authorization": f"Bearer {data['user']['access_token']}", "Content-Type": "application/vnd.api+json"})
    else:
        entry = requests.get(f"https://kitsu.io/api/edge/library-entries?filter[animeId]={id}&filter[userId]={data['user']['id']}&include=anime", headers={"Authorization": f"Bearer {data['user']['access_token']}"}).json()
        if progress >= data["list"][id]["seasons"][season]["episodes"]:
            status = {"status": "completed"}
            data["list"][id]["completed"] = True
        data["list"][id]["seasons"][season]["progress"] = progress
        requests.patch(f"https://kitsu.io/api/edge/library-entries/{entry['data'][0]['id']}", json={"data": {"id": int(entry["data"][0]["id"]), "type": "libraryEntries", "attributes": status}}, headers={"Authorization": f"Bearer {data['user']['access_token']}", "Content-Type": "application/vnd.api+json"})
    return {"id": id, **data["list"][id]}


def search(name):
    api = requests.get("https://kitsu.io/api/edge/anime", params={"filter[text]": name}).json()
    results = {}
    for entry in api["data"]:
        id = entry["id"]
        entry = entry["attributes"]
        results[id] = {"seasons": {1: {"episodes": entry["episodeCount"]}}, "type": format_to_type(entry["showType"]), "titles": list(set(filter(None, [*entry["titles"].values(), *list(entry["abbreviatedTitles"] if entry["abbreviatedTitles"] is not None else []), entry["canonicalTitle"]])))}
    return results


def login(username, password):
    api = requests.post("https://kitsu.io/api/oauth/token", data={"grant_type": "password", "client_id": "dd031b32d2f56c990b1425efe6c42ad847e7fe3ab46bf1299f05ecd856bdb7dd", "client_secret": "54d7307928f63414defd96399fc31ba847961ceaecef3a5fd93144e960c0e151", "username": username, "password": password}).json()
    if "error" in api:
        print("Kitsu error:", api["error_description"])
        return False
    user = requests.get("https://kitsu.io/api/edge/users?filter[self]=true", headers={"Authorization": f"Bearer {api['access_token']}"}).json()
    if not user["data"]:
        print("Kitsu error")
        return False
    return {"user": {"name": username, "id": user["data"][0]["id"], **api}}


def refresh():
    api = requests.post("https://kitsu.io/api/oauth/token", data={"grant_type": "refresh_token", "client_id": "dd031b32d2f56c990b1425efe6c42ad847e7fe3ab46bf1299f05ecd856bdb7dd", "client_secret": "54d7307928f63414defd96399fc31ba847961ceaecef3a5fd93144e960c0e151", "refresh_token": data["user"]["refresh_token"]}).json()
    if "error" in api:
        print("Kitsu error:", api["error_description"])
        return False
    return api


config_file = os.path.join(os.path.dirname(__file__), "kitsu.json")

if os.path.isfile(config_file):
    with open(config_file, encoding="utf-8") as fh:
        data = json.load(fh)
    data["user"] = {**data["user"], **refresh()}
    with open(config_file, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
else:
    while True:
        username = input("Enter your Kitsu username: ")
        password = input("Enter your Kitsu password: ")
        data = login(username, password)
        if data:
            break

print("Updating Kitsu...")

data = {**data, "list": seen()}
with open(config_file, "w", encoding="utf-8") as fh:
    json.dump(data, fh, ensure_ascii=False)

cache = {}
