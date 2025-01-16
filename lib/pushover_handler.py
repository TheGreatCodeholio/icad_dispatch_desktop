import time
from datetime import datetime

import requests
import logging

# create logger
from colorama import Fore, Style

module_logger = logging.getLogger('icad_tone_detector.pushover')


def send_push(icad_config, detector_name, detector_data, mp3_url):
    try:
        timestamp = datetime.fromtimestamp(time.time())
        hr_timestamp = f'{timestamp.strftime("%H")}:{timestamp.strftime("%M")} {timestamp.strftime("%b %d %Y")}'
        if not mp3_url:
            mp3_url = ""
        else:
            mp3_url = mp3_url

        if detector_data["pushover_subject"] != "":
            title = detector_data["pushover_subject"]
        else:
            title = icad_config["pushover_settings"]["subject"]

        if detector_data["pushover_sound"] != "":
            sound = detector_data["pushover_sound"]
        else:
            sound = icad_config["pushover_settings"]["sound"]

        if detector_data["pushover_body"] != "":
            body = detector_data["pushover_body"]
        else:
            body = icad_config["pushover_settings"]["message_html_string"]

        body = body.replace("%detector_name%", detector_name).replace("%timestamp%", hr_timestamp).replace("%mp3_url%", mp3_url)

        if icad_config["pushover_settings"]["all_detector_group"] == 1:
            module_logger.debug(Fore.YELLOW + "Sending Pushover All Detectors Group" + Style.RESET_ALL)
            if icad_config["pushover_settings"]["all_detector_app_token"] and icad_config["pushover_settings"]["all_detector_group_token"]:

                r = requests.post("https://api.pushover.net/1/messages.json", data={
                    "token": icad_config["pushover_settings"]["all_detector_app_token"],
                    "user": icad_config["pushover_settings"]["all_detector_group_token"],
                    "html": 1,
                    "message": body,
                    "title": title,
                    "sound": sound
                })
                if r.status_code == 200:
                    module_logger.debug(Fore.GREEN + "Pushover Successful: Group All" + Style.RESET_ALL)
                else:
                    module_logger.critical(Fore.RED + "Pushover Unsuccessful: Group All " + str(r.text) + Style.RESET_ALL)

            else:
                module_logger.critical(Fore.RED + "Missing Pushover APP or Group Token for All group" + Style.RESET_ALL)
        else:
            module_logger.debug(Fore.YELLOW + "Pushover all detector group disabled." + Style.RESET_ALL)

        if "pushover_app_token" in detector_data and "pushover_group_token" in detector_data:
            if detector_data["pushover_app_token"] and detector_data["pushover_group_token"]:
                module_logger.debug(Fore.YELLOW + "Sending Pushover Detector Group" + Style.RESET_ALL)
                r = requests.post("https://api.pushover.net/1/messages.json", data={
                    "token": detector_data["pushover_app_token"],
                    "user": detector_data["pushover_group_token"],
                    "html": 1,
                    "message": body,
                    "title": title,
                    "sound": sound
                })
                if r.status_code == 200:
                    module_logger.debug(Fore.GREEN + "Pushover Successful: Group " + detector_name + Style.RESET_ALL)
                else:
                    module_logger.critical(
                        Fore.RED + "Pushover Unsuccessful: Group " + detector_name + " " + str(r.text) + Style.RESET_ALL)
            else:
                module_logger.critical(Fore.RED + "Missing Pushover APP or Group Token" + Style.RESET_ALL)
        else:
            module_logger.critical(Fore.RED + "Missing Pushover APP or Group Token" + Style.RESET_ALL)

    except Exception as e:
        module_logger.critical(Fore.RED + "Pushover Send Failure:\n" + repr(e) + Style.RESET_ALL)
