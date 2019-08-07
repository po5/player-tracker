import requests
import os.path
import json
from time import sleep
from selectolax.parser import HTMLParser


def format_to_type(format):
    format_type = "other"
    if format == "Movie":
        format_type = "movie"
    if "TV" in format:
        format_type = "episode"
    return format_type


def seen(username):
    offset = 0
    seen_list = {}
    while True:
        sleep(5)
        api = session.get(f"https://myanimelist.net/animelist/{username}/load.json?offset={offset}&status=7")
        if "Too Many Requests" == api.text:
            print("Rate limited on MyAnimeList, waiting 10s...")
            sleep(10)
            continue
        api = api.json()
        if "errors" in api:
            print("MyAnimeList error:", api["errors"][0]["message"])
            return False
        for entry in api:
            seen_list[entry["anime_id"]] = {"completed": entry["status"] == 2, "seasons": {1: {"episodes": entry["anime_num_episodes"], "progress": entry["num_watched_episodes"]}}, "type": format_to_type(entry["anime_media_type_string"]), "titles": [entry["anime_title"]]}
        if len(api) != 300:
            return seen_list
        offset += 300


def update(id, season, progress, completed, format, media_type):
    global data
    edit = session.get(f"https://myanimelist.net/ownlist/anime/{id}/edit?hideLayout")
    if "Too Many Requests" == edit.text:
        print("Rate limited on MyAnimeList, waiting 20s...")
        sleep(20)
        return update(id, season, progress, completed, format, media_type)
    document = HTMLParser(edit.text)
    episodes = document.css("#anime_num_episodes")
    if not episodes:
        print("Rate limited on MyAnimeList, waiting 20s...")
        sleep(20)
        return update(id, season, progress, completed, format, media_type)
    episodes = int(episodes[0].attributes["value"])
    score = document.css("#add_anime_score option[selected]")
    if len(score) > 0:
        score = int(score[0].attributes["value"] or 0)
    else:
        score = 0
    title = document.css("strong a")[0].text()
    url = "https://myanimelist.net/ownlist/anime/add.json"
    if id in data["list"]:
        url = "https://myanimelist.net/ownlist/anime/edit.json"
    post = json.dumps({"anime_id": id, "status": 2 if progress >= episodes else 1, "score": score, "num_watched_episodes": progress, "csrf_token": data["user"]["csrf"]})
    api = session.post(url, data=post)
    try:
        api = api.json()
    except JSONDecodeError:
        print("Rate limited on MyAnimeList, waiting 20s...")
        sleep(20)
        return update(id, season, progress, completed, format, media_type)
    if api is None:
        if id in data["list"]:
            data["list"][id]["seasons"][season]["progress"] = progress
            data["list"][id]["completed"] = data["list"][id]["seasons"][season]["episodes"] == progress
        else:
            data["list"][id] = {"completed": progress >= episodes, "seasons": {1: {"episodes": episodes, "progress": progress}}, "type": "episode", "titles": [title]}
        return {"id": id, **data["list"][id]}
    if "errors" in api:
        print("MyAnimeList error:", api["errors"][0]["message"])
        return False


def search(name):
    api = requests.get("https://myanimelist.net/search/prefix.json", params={"type": "anime", "keyword": name}).json()
    if "errors" in api:
        print("MyAnimeList error:", api["errors"][0]["message"])
        return False
    results = {}
    for entry in api["categories"][0]["items"]:
        results[entry["id"]] = {"seasons": {1: {"episodes": None}}, "type": format_to_type(entry["payload"]["media_type"]), "titles": [entry["name"]]}
    return results


def login(username, password):
    login_page = session.get("https://myanimelist.net/login.php")
    document = HTMLParser(login_page.text)
    csrf_token = document.css("meta[name='csrf_token']")
    if not csrf_token:
        print("Rate limited on MyAnimeList, waiting 20s...")
        sleep(20)
        return login(username, password)
    csrf_token = csrf_token[0].attributes["content"]
    sleep(10)
    login_attempt = session.post("https://myanimelist.net/login.php", data={"user_name": username, "password": password, "csrf_token": csrf_token, "cookie": "1", "sublogin": "Login", "submit": "1"})
    if "Too Many Requests" == login_attempt.text:
        print("Rate limited on MyAnimeList, waiting 20s...")
        sleep(20)
        return login(username, password)
    document = HTMLParser(login_attempt.text)
    error = document.css(".badresult")
    if error:
        print("MyAnimeList error:", error.innerText)
        return False
    id = int(document.css(".header-profile-button")[0].attributes["style"].replace("background-image:url(https://cdn.myanimelist.net/images/userimages/", "").split(".")[0])
    return {"user": {"id": id, "name": username, "cookies": [{"name": c.name, "value": c.value, "domain": c.domain, "path": c.path} for c in session.cookies], "csrf": csrf_token}}


session = requests.session()

config_file = os.path.join(os.path.dirname(__file__), "myanimelist.json")

if os.path.isfile(config_file):
    with open(config_file, encoding="utf-8") as fh:
        data = json.load(fh)
    for cookie in data["user"]["cookies"]:
        session.cookies.set(**cookie)
else:
    while True:
        username = input("Enter your MyAnimeList username: ")
        password = input("Enter your MyAnimeList password: ")
        data = login(username, password)
        if data:
            break

print("Updating MyAnimeList...")

data = {**data, "list": seen(data["user"]["name"])}
with open(config_file, "w", encoding="utf-8") as fh:
    json.dump(data, fh, ensure_ascii=False)

cache = {}
