import json
import time
import datetime
import requests
import logging
from colorama import Fore, Style

from lib.cache_check_handler import create_cached_item, get_all_cached_items, delete_cache, delete_single_cached_item
from lib.mysql_handler import Database
from lib.redis_handler import RedisCache

module_logger = logging.getLogger('icad_tone_detector.facebook')


def send_post(icad_config, detector_name, detector_data, mp3_url, mp3_local_path):
    try:
        if detector_data["post_to_facebook"] == 0:
            module_logger.info(Fore.BLUE + detector_name + " has Facebook Posts Disabled." + Style.RESET_ALL)
            return
        service = "facebook"
        timestamp = datetime.datetime.fromtimestamp(time.time())
        cache_data = {"detector_name": detector_name, "detector_number": detector_data["station_number"],
                      "mp3_local_path": mp3_local_path, "mp3_url": mp3_url}
        if icad_config["redis_settings"]["enabled"] == 1:
            RedisCache(icad_config).add_call_to_redis(service, detector_name, cache_data)
        else:
            create_cached_item(service, cache_data)
        module_logger.debug(Fore.YELLOW + "Waiting for additional tones from same call." + Style.RESET_ALL)
        time.sleep(icad_config["facebook_settings"]["call_wait_time"])
        if icad_config["redis_settings"]["enabled"] == 1:
            calls_result = RedisCache(icad_config).get_all_call(service)
        else:
            calls_result = get_all_cached_items(service)
        if calls_result:
            if icad_config["redis_settings"]["enabled"] == 1:
                working_call = calls_result[detector_name.encode("utf-8")]
            else:
                working_call = calls_result[detector_name]
            if working_call:
                if len(calls_result) >= 2:
                    message = f'{timestamp.strftime("%H")}:{timestamp.strftime("%M")} {timestamp.strftime("%b %d %Y")}\nStations:\n'

                    if icad_config["redis_settings"]["enabled"] == 1:
                        for call in calls_result:
                            data = json.loads(str(calls_result[call].decode('utf-8')))
                            message += str(data["detector_name"] + " " + str(data["detector_number"]) + "\n")
                        RedisCache(icad_config).delete_all_calls(service)
                    else:
                        for call in calls_result:
                            message += str(calls_result[call]["detector_name"] + "\n")
                        delete_cache(service)
                    message += "\n\n"
                    message += "Dispatch Audio: " + str(mp3_url)
                    facebook_page = icad_config["facebook_settings"]["facebook_page_id"]
                    connect_and_post_page(icad_config, message, facebook_page, mp3_url)

                else:
                    if icad_config["redis_settings"]["enabled"] == 1:
                        RedisCache(icad_config).delete_all_calls(service)
                    else:
                        delete_cache(service)

                    message = f'{timestamp.strftime("%H")}:{timestamp.strftime("%M")} {timestamp.strftime("%b %d %Y")}\nStation: {detector_name} {str(detector_data["station_number"])}\n\n'

                    message += "Dispatch Audio: " + str(mp3_url) + "\n"
                    facebook_page = icad_config["facebook_settings"]["facebook_page_id"]
                    connect_and_post_page(icad_config, message, facebook_page, mp3_url)

        else:
            module_logger.debug(Fore.YELLOW + detector_name + " part of another call. Not Posting." + Style.RESET_ALL)

    except Exception as e:
        module_logger.critical(Fore.RED + "Facebook Post Failure:\n" + repr(e) + Style.RESET_ALL)


def connect_and_post_page(icad_config, message, page_id, mp3_url):
    if icad_config["facebook_settings"]["facebook_app_token_page"]:
        post_url = f"https://graph.facebook.com/v14.0/{page_id}/feed"
        payload = {
            'message': message,
            'access_token': icad_config["facebook_settings"]["facebook_app_token_page"]
        }
        r = requests.post(post_url, data=payload)
        if r.status_code == 200:
            response = json.loads(r.text)
            post_id = response["id"]
            module_logger.debug("Page Post Successful: " + str(post_id))
            if icad_config["mysql_settings"]["enabled"] == 1:
                # Add post ID to Database so we can manipulate from iCAD Web
                Database(icad_config).update_facebook_post(post_id, message, mp3_url)
        else:
            module_logger.critical("Page Post Failed: " + str(page_id) + " " + str(r.status_code) + " " + r.text)

    else:
        module_logger.critical("No Page ID given or app token is empty!")


def connect_and_post_page_comment_stream(icad_config, message, post_id):
    if icad_config["facebook_settings"]["facebook_app_token_page"]:
        post_url = f"https://graph.facebook.com/v15.0/{post_id}/comments"
        payload = {
            'message': message,
            'access_token': icad_config["facebook_settings"]["facebook_app_token_page"]
        }
        r = requests.post(post_url, data=payload)
        if r.status_code == 200:
            module_logger.debug("Stream Comment Post Successful: " + str(post_id))
        else:
            module_logger.critical(
                "Stream Comment Failed: " + str(post_id) + " " + str(r.status_code) + " " + r.text)

    else:
        module_logger.critical("No Group ID given or app token is empty!")
