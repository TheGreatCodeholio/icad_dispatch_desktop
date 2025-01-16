import json
import os
import shutil


def create_cached_item(service, detection_data):
    if not os.path.exists("var/"):
        os.mkdir("var/")
    if not os.path.exists("var/cache"):
        os.mkdir("var/cache")

    if not os.path.exists("var/cache/" + service + ".json"):
        cache = open("var/cache/" + service + ".json", "w+")
        cache_data = {detection_data["detector_name"]: detection_data}
        json.dump(cache_data, cache, indent=4)
        cache.close()
    else:
        cache = open("var/cache/" + service + ".json", "r")
        size = os.path.getsize("var/cache/" + service + ".json")
        if size == 0:
            print("Data is none.")
            cache_data = {}
        else:
            cache_data = json.load(cache)
        cache.close()
        cache = open("var/cache/" + service + ".json", "w+")
        cache_data[detection_data["detector_name"]] = detection_data
        json.dump(cache_data, cache, indent=4)
        cache.close()


def get_all_cached_items(service):
    if not os.path.exists("var/cache/" + service + ".json"):
        return False
    try:
        cache = open("var/cache/" + service + ".json", "r")
        size = os.path.getsize("var/cache/" + service + ".json")
        if size == 0:
            return False
        else:
            cache_data = json.load(cache)
            return cache_data
    except Exception as e:
        print(e)
        return False


def get_single_cached_item(service, detector_name):
    if not os.path.exists("var/cache/" + service + ".json"):
        return False
    try:
        cache = open("var/cache/" + service + ".json", "r")
        size = os.path.getsize("var/cache/" + service + ".json")
        if size == 0:
            return False
        else:
            cache_data = json.load(cache)
            return cache_data[detector_name]
    except Exception as e:
        print(e)
        return False


def delete_single_cached_item(service, detector_name):
    if not os.path.exists("var/cache/" + service + ".json"):
        return
    cache = open("var/cache/" + service + ".json", "r")
    size = os.path.getsize("var/cache/" + service + ".json")
    if size == 0:
        print("Data is none.")
        cache_data = {}
    else:
        cache_data = json.load(cache)
    cache.close()
    cache = open("var/cache/" + service + ".json", "w+")
    del cache_data[detector_name]
    json.dump(cache_data, cache, indent=4)
    cache.close()


def delete_cache(service):
    if not os.path.exists("var/cache/" + service + ".json"):
        return
    else:
        shutil.copy("var/cache/" + service + ".json", "var/cache/" + service + "_last.json")
        os.remove("var/cache/" + service + ".json")
