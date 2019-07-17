import requests
import os.path
import json

def format_to_type(format):
    format_type = "other"
    if format == "MOVIE":
        format_type = "movie"
    if "TV" in format:
        format_type = "episode"
    return format_type

def seen(**kwargs):
    api = requests.post("https://graphql.anilist.co", headers={"Authorization": f"Bearer {data['token']}"}, json={"variables": {**kwargs}, "query": """
query ($userName: String, $userId: Int) {
  MediaListCollection(userName: $userName, userId: $userId, type: ANIME) {
   	lists {
      entries {
        mediaId
        status
        progress
        media {
          format
          episodes
          title {
            romaji
            english
            native
          }
        }
      }
    }
    user {
      id
      name
    }
  }
}
"""}).json()
    if "errors" in api:
        print("AniList error:", api["errors"][0]["message"])
        return False
    seen_list = {}
    for lst in api["data"]["MediaListCollection"]["lists"]:
        for entry in lst["entries"]:
            seen_list[entry["mediaId"]] = {"completed": entry["status"] == "COMPLETED", "episodes": entry["media"]["episodes"], "progress": entry["progress"], "type": format_to_type(entry["media"]["format"]), "titles": list(set(filter(None, entry["media"]["title"].values())))}
    return {"list": seen_list, "user": api["data"]["MediaListCollection"]["user"]}

def update(id, progress, completed):
    global data
    api = requests.post("https://graphql.anilist.co", headers={"Authorization": f"Bearer {data['token']}"}, json={"variables": {"mediaId": id, "progress": progress, "status": "COMPLETED" if completed else "CURRENT"}, "query": """
mutation ($mediaId: Int, $progress: Int, $status: MediaListStatus) {
  SaveMediaListEntry(mediaId: $mediaId, progress: $progress, status: $status) {
    mediaId
    status
    progress
    media {
      format
      episodes
      title {
        romaji
        english
        native
      }
	}
  }
}
"""}).json()
    if "errors" in api:
        print("AniList error:", api["errors"][0]["message"])
        return False
    info = {"completed": api["data"]["SaveMediaListEntry"]["status"] == "COMPLETED", "episodes": api["data"]["SaveMediaListEntry"]["media"]["episodes"], "progress": api["data"]["SaveMediaListEntry"]["progress"], "type": format_to_type(api["data"]["SaveMediaListEntry"]["media"]["format"]), "titles": list(set(filter(None, api["data"]["SaveMediaListEntry"]["media"]["title"].values())))}
    data["list"][api["data"]["SaveMediaListEntry"]["mediaId"]] = info
    return {"id": api["data"]["SaveMediaListEntry"]["mediaId"], **info}

def search(name):
    api = requests.post("https://graphql.anilist.co", headers={"Authorization": f"Bearer {data['token']}"}, json={"variables": {"search": name}, "query": """
query ($search: String) {
  anime: Page(perPage: 8) {
    results: media(search: $search, type: ANIME) {
      id
      format
      episodes
      title {
        english
        romaji
        native
      }
    }
  }
}
"""}).json()
    if "errors" in api:
        print("AniList error:", api["errors"][0]["message"])
        return False
    results = {}
    for entry in api["data"]["anime"]["results"]:
        results[entry["id"]] = {"episodes": entry["episodes"], "type": format_to_type(entry["format"]), "titles": list(set(filter(None, entry["title"].values())))}
    return results

def user(username):
    api = requests.post("https://graphql.anilist.co", headers={"Authorization": f"Bearer {data['token']}"}, json={"variables": {"userName": username}, "query": """
query ($userName: String!) {
  User(name: $userName) {
    id
    name
  }
}
"""}).json()
    if "errors" in api:
        print("AniList error:", api["errors"][0]["message"])
        return False
    return api["data"]["User"]

config_file = os.path.join(os.path.dirname(__file__), "anilist.json")

if os.path.isfile(config_file):
    with open(config_file, encoding="utf-8") as fh:
        data = json.load(fh)
    print("Updating AniList...")
    list_info = seen(userId=data["user"]["id"])
else:
    while True:
        username = input("Enter your AniList username: ")
        print("Please visit the following link in your browser https://anilist.co/api/v2/oauth/authorize?client_id=2296&response_type=token")
        token = input("and paste the code here: ")
        data = {"token": token}
        list_info = seen(userName=username)
        if list_info:
            break

data = {**data, **list_info}
with open(config_file, "w", encoding="utf-8") as fh:
    json.dump(data, fh, ensure_ascii=False)

cache = {}
