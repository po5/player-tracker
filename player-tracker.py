import sys
import types
import string
import psutil
import os.path
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


players = ("5kplayer", "ace_player", "allplayer", "baka mplayer", "bestplayer", "bomi", "bsplayer", "divx player", "divx plus player", "gom", "kantaris", "kantarismain", "kmplayer", "kodi", "xbmc", "la", "mplayerc", "mplayerc64", "mpc-qt", "miro", "mpc-be", "mpc-be64", "mpc-hc", "mpc-hc64", "iris", "shoukaku", "mpcstar", "mediaplayerdotnet", "mpv", "mv2player", "mv2playerplus", "potplayer", "potplayer64", "potplayermini", "potplayermini64", "sumire", "zuikaku", "smplayer", "smplayer2", "splash", "splashlite", "splayer", "umplayer", "vlc", "webtorrent", "winamp", "wmplayer", "zplayer")
extensions = (".3gp", ".avi", ".divx", ".mkv", ".mov", ".mp4", ".mpg", ".ogm", ".rm", ".rmvb", ".webm", ".wmv")
titles = []
services_list = [key for key, obj in services.__dict__.items() if type(obj) is types.ModuleType]
if not services_list:
    print("Looks like you haven't enabled any services!")
    print("Uncomment lines in", os.path.join("services", "__init__.py"), "by removing '#' and try again.")
    sys.exit()
services_info = {}
for service in services_list:
    module = getattr(services, service)
    services_info[service] = dir(module)
    if "data" in services_info[service] and "list" in module.data:
        for item in module.data["list"].values():
            for title in item["titles"]:
                titles.append(str(title))
                titles.append("".join([c for c in str(title) if c.isalpha() or c.isdigit() or c==" "]).rstrip())

plays = {}
cycles = {}


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
            files.append({"player": name, "pid": proc.pid, "file": path})
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
                    if (result["seasons"].get(season, {}).get("episodes", None) or 99) >= episode:
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
                matches.append({"id": id, "title": best_title["title"], "result": result, "season": season, "episode": max_episode, "completed": season == max(result["seasons"]) and max_episode == result["seasons"].get(season, {}).get("episodes", None), "type": result["type"], "score": score})
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
                if update(module, match, format) is False:
                    print("Update failed")
            if "announce" in features:
                module.announce(match)


def update(module, match, format):
    module.update(match["id"], match["season"], match["episode"], match["completed"], format, match["type"])


while True:
    old_plays = plays
    old_cycles = dict(cycles)
    plays = {}
    for play in playing():
        if play["pid"] not in plays:
            plays[play["pid"]] = []
        if play["file"] not in cycles:
            cycles[play["file"]] = 0
            print("Queuing", os.path.basename(play["file"]), "for list update")
        cycles[play["file"]] += 1
        plays[play["pid"]].append(play)
    for pid, old in old_plays.items():
        if plays.get(pid, None) == old:
            continue
        for play in old:
            if play["file"] in cycles and cycles[play["file"]] >= 3:
                info = identify(play, titles)
                search_and_match(**info)
    for file, count in old_cycles.items():
        if count == cycles[file]:
            del cycles[file]

    print("Waiting 30s...")
    sleep(30)
