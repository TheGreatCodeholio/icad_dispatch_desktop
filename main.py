# -*- coding:utf-8 -*-
import subprocess
from logging import handlers
import logging
import os
import time
from colorama import Fore, Back, Style, init
import pyaudio
from threading import Thread
from lib.main_config_handler import read_main_config, create_main_config, read_tones_config, create_tones_config
import lib.flask_request_handler as web_app
import lib.detection_handler as detection
import lib.logger_handler as log_handler

__name__ = "iCAD Tone Detection"
__version__ = "0.40"

from lib.trunk_recorder_handler import init_tr_play_worker

create_main_config()
create_tones_config()
init()

icad_config = read_main_config()
icad_detectors = read_tones_config()

input_devices = []
output_devices = []
input_device_indices = {}
output_device_indices = {}
input_device_index = icad_config["audio"]["input_device_index"]
output_device_index = icad_config["audio"]["output_device_index"]
chunk = 2048
format = pyaudio.paInt16
rate = 22050

log_file = 'log/icad.log'

if not os.path.exists("log/"):
    os.mkdir("log/")

should_roll_over = os.path.isfile(log_file)
handler = logging.handlers.RotatingFileHandler(log_file, mode='w+', backupCount=10)
if should_roll_over:  # log already exists, roll over!
    handler.doRollover()

log_handler.add_logging_level('ICAD_INFO', 21)

logger = logging.getLogger('icad_tone_detector')

# create file handler which logs even debug messages
fh = logging.FileHandler(log_file)

if icad_config["general"]["log_debug"] == 1:
    logger.setLevel(logging.DEBUG)
    fh.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.ICAD_INFO)
    fh.setLevel(logging.ICAD_INFO)

# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
# add the handlers to the logger
logger.addHandler(fh)

if icad_config["general"]["headless"] == 0:
    import lib.system_tray_handler as tray_handler
    logger.icad_info(
        Fore.CYAN + " Starting iCAD Dispatch v" + str(__version__) + " in GUI mode." + Style.RESET_ALL)
else:
    logger.icad_info(Fore.CYAN + " Starting iCAD Dispatch v" + str(__version__) + " in headless mode." + Style.RESET_ALL)


def init_audio_interfaces():
    global input_devices
    global output_devices
    global input_device_indices
    global output_device_indices
    global input_device_index
    global output_device_index
    p = pyaudio.PyAudio()
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')

    for i in range(0, numdevices):
        if (p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
            input_devices.append(p.get_device_info_by_host_api_device_index(0, i).get('name'))
            input_device_indices[p.get_device_info_by_host_api_device_index(0, i).get('name')] = i
            inv_input_device_indices = dict((v, k) for k, v in input_device_indices.items())

        if p.get_device_info_by_host_api_device_index(0, i).get('maxOutputChannels') > 0:
            output_devices.append(p.get_device_info_by_host_api_device_index(0, i).get('name'))
            output_device_indices[p.get_device_info_by_host_api_device_index(0, i).get('name')] = i
            inv_output_device_indices = dict((v, k) for k, v in output_device_indices.items())

    if icad_config["audio"]["input_device_index"] in inv_input_device_indices:
        input_device_index = icad_config["audio"]["input_device_index"]
        logger.icad_info(p.get_device_info_by_host_api_device_index(0, input_device_index).get(
            'name') + ' selected as audio input device')
        audio_input_setup = True
    elif icad_config["audio"]["input_device_index"] == 99:
        input = p.get_default_input_device_info()
        icad_config["audio"]["input_device_index"] = input["index"]
        audio_input_setup = True
    else:
        logger.critical("Unable to select input device. " + str(input_device_index))
        audio_input_setup = False

    if icad_config["audio"]["output_device_index"] in inv_output_device_indices:
        output_device_index = icad_config["audio"]["output_device_index"]
        logger.icad_info(p.get_device_info_by_host_api_device_index(0, output_device_index).get(
            'name') + ' selected as audio input device')
        audio_output_setup = True
    elif icad_config["audio"]["output_device_index"] == 99:
        output = p.get_default_output_device_info()
        icad_config["audio"]["output_device_index"] = output["index"]
        audio_output_setup = True
    else:
        logger.critical("Unable to select output device. " + str(output_device_index))
        audio_output_setup = False

    return audio_input_setup, audio_output_setup




try:
    subprocess.check_call(['ffmpeg', '-version'])
    ffmpeg = 1
    logger.info(Fore.GREEN + "ffmpeg install found." + Style.RESET_ALL)
except:
    ffmpeg = 0
    logger.info(Fore.RED + "ffmpeg not found, exiting." + Style.RESET_ALL)
    os._exit(0)

input_status, output_status = init_audio_interfaces()

if not input_status or not output_status:
    # print("Audio initialization error.")
    input_message = "Audio Device Init Error: \n\n"
    input_message += "Input Devices: \n"
    for dev in input_device_indices:
        input_message += "Index: " + str(input_device_indices[dev]) + " Name: " + str(dev) + "\n"
    input_message += "\n\nOutput Devices: \n"
    for dev in output_device_indices:
        input_message += "Index: " + str(output_device_indices[dev]) + " Name: " + str(dev) + "\n"
    input_message += "\n\nAdd correct device index to config for input and output and restart application."
    if icad_config["general"]["headless"] == 0:
        tray_handler.popup_static("iCAD Tone Detection", input_message, "Exit")
        logger.critical(Fore.RED + input_message + Style.RESET_ALL)
    else:
        logger.critical(Fore.RED + input_message + Style.RESET_ALL)
    os._exit(0)

if icad_config["detection"]["mode"] == 0:
    # TwoTone Finder
    logger.icad_info(Fore.BLUE + "Starting in Tone Finder Mode" + Style.RESET_ALL)
elif icad_config["detection"]["mode"] == 1:
    logger.icad_info(Fore.BLUE + "Starting in Tone Detection Mode" + Style.RESET_ALL)
elif icad_config["detection"]["mode"] == 2:
    logger.icad_info(Fore.BLUE + "Starting in Tone Detection  + FinderMode" + Style.RESET_ALL)

try:
    stream = detection.start_audio_stream(icad_config, format, rate, chunk)
except Exception as e:
    logger.critical(Fore.RED + "Getting Stream Failed Check Audio configuration." + Style.RESET_ALL)
    time.sleep(10)
    os._exit(0)

if not stream:
    logger.critical(Fore.RED + "Getting Stream Failed Check Audio configuration." + Style.RESET_ALL)
    if icad_config["general"]["headless"] == 0:
        tray_handler.popup_static("iCAD Tone Detection", " Error: Getting Stream Failed Check Audio configuration.",
                                  "Exit")
    os._exit(0)

Thread(target=detection.detect_loop, args=(icad_config, icad_detectors, stream, format, rate, chunk)).start()
web_app.init_flask(icad_config)
if icad_config["audio"]["trunk_recorder"]["enabled"] == 1:
    init_tr_play_worker(icad_config)
if icad_config["general"]["headless"] == 0:
    tray_handler.start_tray_icon()
