import types
import string
import psutil
import requests
from similarity.normalized_levenshtein import NormalizedLevenshtein
from unidecode import unidecode
from operator import itemgetter
from guessit import guessit
from time import sleep

import services


def normalize(s):
    for p in string.punctuation:
        s = s.replace(p, '')

    return unidecode(s).lower().strip()


players = ("sumire", "zuikaku", "vlc", "mpv", "potplayer", "potplayer64", "potplayermini", "potplayermini64")
extensions = (".ogm", ".avi", ".mp4", ".mkv", ".webm")
titles = []
services_list = [key for key, obj in services.__dict__.items() if type(obj) is types.ModuleType]
services_info = {}
for service in services_list:
    module = getattr(services, service)
    services_info[service] = dir(module)
    if "data" in services_info[service] and "list" in module.data:
        for item in module.data["list"].values():
            for title in item["titles"]:
                titles.append(str(title))


def playing():
    files = []
    for proc in psutil.process_iter():
        name = proc.name().lower()
        if name.endswith(".exe"):
            name = name[:-4]
        if name not in players:
            continue
        for file in proc.open_files():
            path = file.path
            if not path.endswith(extensions):
                continue
            files.append({"player": name, "file": path})
    return files


def identify(play, expected=[]):
    guess = guessit(play["file"], options={"expected_title": expected})
    identifier = f"{guess.get('title', '')} ({guess.get('year', '')})"

    return {"guess": guess, "identifier": identifier}


def search_and_match(guess, identifier):
    title = guess.get("title", "")
    format = guess.get("type", "other")
    episodes = guess.get("episode", 1)
    season = guess.get("season", 1)
    if isinstance(title, list):
        title = max(title, key=len)
    normalized = normalize(title)
    if not isinstance(episodes, list):
        episodes = [episodes]
    if not title:
        return
    for service, features in services_info.items():
        module = getattr(services, service)
        cached = False
        if "cache" in features and identifier in module.cache:
            search = module.cache[identifier]
            cached = True
        if "search" in features:
            if not cached:
                print(f"Searching on {service}...")
                search = module.search(title)
                module.cache[identifier] = search
            matches = []
            for id, result in search.items():
                score = 0
                valid_episodes = []
                for episode in episodes:
                    if result["seasons"].get(season, {}).get("episodes", None) or 99 >= episode:
                        valid_episodes.append(episode)
                        score = 2
                if valid_episodes:
                    max_episode = max(valid_episodes)
                else:
                    max_episode = 1
                if result["type"] == format:
                    score += .3
                if "data" in features and "list" in module.data:
                    if id in module.data["list"]:
                        score += .1
                similar_titles = []
                for similar_title in result["titles"]:
                    distance = NormalizedLevenshtein().distance(normalized, normalize(similar_title))
                    if distance > 8:
                        continue
                    similar_titles.append({"title": similar_title, "distance": distance})
                if not similar_titles:
                    continue
                best_title = min(similar_titles, key=itemgetter("distance"))
                score += 1 - best_title["distance"]
                matches.append({"id": id, "title": best_title["title"], "result": result, "season": season, "episode": max_episode, "completed": season == max(result["seasons"]) and max_episode == result["seasons"].get(season, {}).get("episodes", None), "score": score})
            if not matches:
                if not cached:
                    print(f"No matches found {title}")
                continue
            match = max(matches, key=itemgetter("score"))
            if "data" in features and "list" in module.data and match["id"] in module.data["list"]:
                if module.data["list"][match["id"]]["completed"] or module.data["list"][match["id"]]["seasons"].get(season, {}).get("progress", 0) >= match["episode"]:
                    if not cached:
                        print(f"Already in list {match['title']} {'- Season ' + str(season) + ' Episode ' + str(match['episode']) if format != 'movie' else ''}")
                    continue
            print(f"Our best match is {match['title']} {'- Season ' + str(season) + ' Episode ' + str(match['episode']) if format != 'movie' else ''}")
            if "update" in features:
                update(module, match, format)
            if "announce" in features:
                module.announce(match)


def update(module, match, format):
    module.update(match["id"], match["season"], match["episode"], match["completed"], format)


while True:
    for play in playing():
        info = identify(play, titles)
        search_and_match(**info)
    print("Waiting 30s...")
    sleep(30)
