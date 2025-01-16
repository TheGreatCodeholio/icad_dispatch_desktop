import json
import time
import datetime
import requests
import logging

# create logger
from colorama import Fore, Style

from lib.cache_check_handler import create_cached_item, get_all_cached_items, delete_cache, delete_single_cached_item
from lib.redis_handler import RedisCache

module_logger = logging.getLogger('icad_tone_detector.telegram')


def post_to_telegram(icad_config, detector_name, detector_data, mp3_url, mp3_local_path):
    try:
        service = "telegram"
        timestamp = datetime.datetime.fromtimestamp(time.time())
        cache_data = {"detector_name": detector_name, "detector_number": detector_data["station_number"],
                      "mp3_local_path": mp3_local_path, "mp3_url": mp3_url}
        if icad_config["redis_settings"]["enabled"] == 1:
            RedisCache(icad_config).add_call_to_redis(service, detector_name, cache_data)
        else:
            create_cached_item(service, cache_data)
        module_logger.debug(Fore.YELLOW + "Waiting for additional tones from same call." + Style.RESET_ALL)
        time.sleep(icad_config["telegram_settings"]["call_wait_time"])
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

                    telegram_channels = icad_config["telegram_settings"]["telegram_channel_ids"]
                    for channel in telegram_channels:
                        connect_and_post_text(icad_config, message, channel)
                        connect_and_post_audio(icad_config, mp3_local_path, channel)

                else:
                    if icad_config["redis_settings"]["enabled"] == 1:
                        RedisCache(icad_config).delete_all_calls(service)
                    else:
                        delete_cache(service)
                    message = f'{timestamp.strftime("%H")}:{timestamp.strftime("%M")} {timestamp.strftime("%b %d %Y")}\nStation: {detector_name} {str(detector_data["station_number"])}\n\n'

                    telegram_channels = icad_config["telegram_settings"]["telegram_channel_ids"]
                    for channel in telegram_channels:
                        connect_and_post_text(icad_config, message, channel)
                        connect_and_post_audio(icad_config, mp3_local_path, channel)

                return
        else:
            module_logger.debug(Fore.YELLOW + detector_name + " part of another call. Not Posting." + Style.RESET_ALL)
    except Exception as e:
        module_logger.critical(Fore.RED + "Telegram Upload Failure:\n" + repr(e) + Style.RESET_ALL)


def connect_and_post_text(icad_config, message, channel_id):
    payload = {
        'chat_id': channel_id,
        'text': message,
        'parse_mode': 'HTML'
    }

    resp = requests.post(
        f'https://api.telegram.org/bot{icad_config["telegram_settings"]["telegram_bot_token"]}/sendMessage',
        data=payload).json()
    if resp["ok"]:
        module_logger.debug(Fore.YELLOW + "Posted Text to Telegram Channel: " + str(channel_id) + Style.RESET_ALL)
    else:
        module_logger.critical(Fore.RED + "Telegram Text Post Failed: " + str(channel_id) + Style.RESET_ALL)


def connect_and_post_audio(icad_config, audio_path, channel_id):
    with open(audio_path, 'rb') as audio:
        payload = {
            'chat_id': channel_id,
            'title': f'Dispatch Audio',
            'parse_mode': 'HTML'
        }
        files = {
            'audio': audio.read(),
        }
        resp = requests.post(
            f'https://api.telegram.org/bot{icad_config["telegram_settings"]["telegram_bot_token"]}/sendAudio',
            data=payload,
            files=files).json()
        audio.close()
        if resp["ok"]:
            module_logger.debug(Fore.YELLOW + "Posted Audio to Telegram Channel: " + str(channel_id) + Style.RESET_ALL)
        else:
            module_logger.critical(Fore.RED + "Telegram Audio Post Failed: " + str(channel_id) + Style.RESET_ALL)
