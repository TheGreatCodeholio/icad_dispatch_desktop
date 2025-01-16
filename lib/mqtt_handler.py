import time
import logging
import paho.mqtt.publish as publish

# create logger
from colorama import Fore, Style

module_logger = logging.getLogger('icad_tone_detection.mqtt')


def publish_to_mqtt(icad_config, detector_data, detector_name):
    # Make sure data is not empty
    if detector_data["mqtt_start_message"] and detector_data["mqtt_topic"]:
        # publish start message
        publish.single(topic=detector_data["mqtt_topic"], payload=detector_data["mqtt_start_message"],
                       hostname=icad_config["mqtt"]["mqtt_hostname"],
                       port=icad_config["mqtt"]["mqtt_port"], auth={'username': icad_config["mqtt"]["mqtt_username"],
                                                                    'password': icad_config["mqtt"]["mqtt_password"]})

        module_logger.debug(Fore.YELLOW + "Start message published MQTT: " + detector_data["mqtt_start_message"] + Style.RESET_ALL)
        # check for stop message
        if detector_data["mqtt_stop_message"] and detector_data["mqtt_message_interval"] and detector_data[
            "mqtt_message_interval"] > 0:
            # sleep for mqtt interval
            time.sleep(detector_data["mqtt_message_interval"])
            # publish stop message
            publish.single(topic=detector_data["mqtt_topic"], payload=detector_data["mqtt_stop_message"],
                           hostname=icad_config["mqtt"]["mqtt_hostname"],
                           port=icad_config["mqtt"]["mqtt_port"],
                           auth={'username': icad_config["mqtt"]["mqtt_username"],
                                 'password': icad_config["mqtt"]["mqtt_password"]})
            module_logger.debug(Fore.YELLOW + "Stop message published MQTT: " + detector_data["mqtt_stop_message"] + Style.RESET_ALL)

        else:
            module_logger.warning(Fore.CYAN + "Stop message not configured skipping." + Style.RESET_ALL)

    else:
        module_logger.warning(Fore.CYAN + "Must have start message and topic for MQTT configured" + Style.RESET_ALL)
