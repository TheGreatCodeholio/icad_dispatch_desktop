import json
import logging
import subprocess
import time
from threading import Thread

import pika
from colorama import Fore, Style

from pika.exceptions import ChannelClosedByBroker

module_logger = logging.getLogger("icad_tone_detector.tr_play_worker")


def worker(config_data):
    module_logger.info(Fore.YELLOW + "Starting TR Recording Worker" + Style.RESET_ALL)
    credentials = pika.PlainCredentials(config_data["rabbitmq_settings"]["username"],
                                        config_data["rabbitmq_settings"]["password"])
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=config_data["rabbitmq_settings"]["hostname"],
                                  port=config_data["rabbitmq_settings"]["port"], credentials=credentials))
    channel = connection.channel()
    try:
        channel.queue_declare(queue=config_data["rabbitmq_settings"]["tone_detection_queue"], durable=True)
    except ChannelClosedByBroker as e:
        module_logger.warning("Channel Closed By Broker Restarting: " + str(e))
        time.sleep(60)
        worker(config_data)
    except ConnectionResetError as e:
        module_logger.warning(Fore.RED + "[x] " + Fore.YELLOW + " Connection Reset Restarting: " + str(
            e) + Style.RESET_ALL)
        time.sleep(60)
        worker(config_data)
    except ConnectionError as e:
        module_logger.warning(Fore.RED + "[x] " + Fore.YELLOW + " Connection Error Restarting: " + str(
            e) + Style.RESET_ALL)
        time.sleep(60)
        worker(config_data)

    module_logger.info(
        Fore.LIGHTMAGENTA_EX + "[*] " + Fore.YELLOW + "  Waiting for messages.")

    def callback(ch, method, properties, body):
        call_data = json.loads(body.decode())
        if "short_name" in call_data:
            module_logger.info(Fore.GREEN + "[+] " + Fore.YELLOW + " - Received Detection Job for " + call_data[
                "short_name"] + Style.RESET_ALL)
        else:
            module_logger.info(Fore.GREEN + "[+] " + Fore.YELLOW + " - Received Detection Job for " + str(call_data[
                                                                                                              "system"]) + Style.RESET_ALL)

        if "expires" in call_data:
            skip = 0
            if call_data["expires"] < time.time():
                skip = 1
        else:
            skip = 1

        if skip == 0:
            pulse_sink = config_data["audio"]["trunk_recorder"]["pulse_sink"]
            command = f'mplayer -ao pulse::{pulse_sink} {call_data["file_location"]}'
            result = subprocess.run(command.split(), capture_output=True, text=True)

        # if os.path.exists(config_data["general"]["audio_download_path"] + call_data["filename"].split("/")[-1]):
        #     os.remove(config_data["general"]["audio_download_path"] + call_data["filename"].split("/")[-1])

        module_logger.info(Fore.GREEN + "[+] " + Fore.YELLOW + " Detection Job Finished" + Style.RESET_ALL)
        ch.basic_ack(delivery_tag=method.delivery_tag)

        module_logger.info(Fore.LIGHTMAGENTA_EX + "[*] " + Fore.YELLOW + " Waiting for messages.")

    try:
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue=config_data["rabbitmq_settings"]["tone_detection_queue"], on_message_callback=callback)
        channel.start_consuming()
    except ChannelClosedByBroker as e:
        module_logger.warning(
            Fore.RED + "[x] " + Fore.YELLOW + " Channel Closed By Broker Restarting: " + str(e) + Style.RESET_ALL)
        time.sleep(60)
        worker(config_data)
    except ConnectionResetError as e:
        module_logger.warning(Fore.RED + "[x] " + Fore.YELLOW + " Connection Reset Restarting: " + str(
            e) + Style.RESET_ALL)
        time.sleep(60)
        worker(config_data)
    except ConnectionError as e:
        module_logger.warning(Fore.RED + "[x] " + Fore.YELLOW + " Connection Error Restarting: " + str(
            e) + Style.RESET_ALL)
        time.sleep(60)
        worker(config_data)


def init_tr_play_worker(icad_config):
    Thread(target=worker, args=(icad_config,)).start()
