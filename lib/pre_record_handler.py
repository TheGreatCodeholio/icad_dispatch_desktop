import logging
from colorama import Fore, Style
from lib.email_handler import send_email
from lib.mqtt_handler import publish_to_mqtt

module_logger = logging.getLogger('icad_tone_detector.pre_record')


def process_pre_record_actions(icad_config, detector_data, detector_name):
    # Send Pre Record Emails
    if icad_config["email"]["pre_record_enabled"] == 1 and len(detector_data["pre_record_emails"]) >= 1:
        module_logger.debug(Fore.YELLOW + "Starting Pre Record Email Sending" + Style.RESET_ALL)
        if icad_config["email"]["send_as_single_email"] == 1:
            send_email(icad_config, detector_data, detector_name, False, detector_data["pre_record_emails"], False)
        else:
            for em in detector_data["pre_record_emails"]:
                em = [em]
                send_email(icad_config, detector_data, detector_name, False, em, False)
    else:
        module_logger.debug(Fore.YELLOW + "Pre Record Email Sending Disabled" + Style.RESET_ALL)

    if icad_config["mqtt"]["enabled"] == 1:
        module_logger.debug(Fore.YELLOW + "Starting Pre Record MQTT." + Style.RESET_ALL)
        publish_to_mqtt(icad_config, detector_data, detector_name)
    else:
        module_logger.debug(Fore.YELLOW + "Pre Record MQTT Disabled" + Style.RESET_ALL)
