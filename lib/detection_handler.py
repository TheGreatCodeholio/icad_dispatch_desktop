import datetime
import logging
import operator
import threading
import time
from functools import reduce

import pyaudio
from numpy import short, hamming, frombuffer, array
from numpy.fft import rfft
from colorama import Style, Fore
from lib.recording_handler import Recorder
from lib.system_tray_handler import show_notification
from lib.pre_record_handler import process_pre_record_actions
from lib.post_record_handler import process_post_record_actions
from lib.tone_finder_actions_handler import process_tone_finder_actions

module_logger = logging.getLogger('icad_tone_detector.detection')

match_list = {"last": {"a": 0, "b": 0}}
long_match_list = {"last": {"tone": 0}}

def start_audio_stream(icad_config, format, rate, chunk):
    try:
        p = pyaudio.PyAudio()
        stream = p.open(format=format, channels=1, rate=rate, input=True, output=False, frames_per_buffer=chunk,
                        input_device_index=icad_config["audio"]["input_device_index"],
                        output_device_index=icad_config["audio"]["output_device_index"])
        return stream
    except:
        return False


def record(stream, rate, chunk, seconds):
    alldata = []
    for i in range(0, int(rate / chunk * seconds)):
        data = stream.read(chunk)
        alldata.append(data)

    data = b''.join(alldata)
    data = frombuffer(data, dtype=short)
    return data


def parse_detectors_config(detectors_config):
    module_logger.debug(Fore.YELLOW + "Loading Detectors" + Style.RESET_ALL)
    active_tones = {}
    for detector in detectors_config:
        if int(detectors_config[detector]["a_tone"]) != 0 and int(detectors_config[detector]["b_tone"]) != 0:
            if detectors_config[detector]["a_tone_length"] > 4:
                detectors_config[detector]["a_tone_length"] = 4
            elif detectors_config[detector]["a_tone_length"] < 0.2:
                detectors_config[detector]["a_tone_length"] = 0.02
            if detectors_config[detector]["b_tone_length"] > 4:
                detectors_config[detector]["b_tone_length"] = 4
            elif detectors_config[detector]["b_tone_length"] < 0.2:
                detectors_config[detector]["b_tone_length"] = 0.02
            active_tones[detector] = [detectors_config[detector]["a_tone"]] * int(
                round(detectors_config[detector]["a_tone_length"] / 0.2)) + [detectors_config[detector]["b_tone"]] * int(
                round(detectors_config[detector]["b_tone_length"] / 0.2))
        elif int(detectors_config[detector]["a_tone"]) == 0 and int(detectors_config[detector]["b_tone"]) != 0:
            if detectors_config[detector]["b_tone_length"] > 8:
                detectors_config[detector]["b_tone_length"] = 8
            elif detectors_config[detector]["b_tone_length"] < 0.2:
                detectors_config[detector]["b_tone_length"] = 0.02
            active_tones[detector] = [detectors_config[detector]["b_tone"]] * int(round(detectors_config[detector]["b_tone_length"] / 0.2))
        else:
            continue

    return detectors_config, active_tones


def detect_loop(icad_config, detectors_config, stream, audio_format, rate, chunk):
    buffer = [0] * 40
    detectors_config, active_tones = parse_detectors_config(detectors_config)
    inactive_tones = []

    def remove_inactive(detector_name):
        module_logger.debug(Fore.YELLOW + "Removing Tone From Inactive: " + detector_name + Style.RESET_ALL)
        if detector_name in inactive_tones:
            inactive_tones.remove(detector_name)

    loop_count = 0
    while 1:
        loop_count += 1
        audio_data = record(stream, rate, chunk, 0.2)
        max_audio_level = max(abs(audio_data))
        if max_audio_level > icad_config["detection"]["silence_threshold"]:
            window = hamming(len(audio_data))
            audio_data = audio_data * window
            FFT = abs(rfft(audio_data))
            FFT[:46] = 0
            FFT[559:] = 0
            freq = rate / 2.0 * FFT.argmax() / len(FFT)
            if freq == 0:
                freqsorted = FFT.argsort()
                freq = rate / 2 * freqsorted[1] / len(FFT)
            buffer.append(freq)
            buffer.pop(0)
            if icad_config["detection"]["mode"] == 0:
                threading.Thread(target=tone_finder, args=(icad_config, buffer, audio_format, rate, chunk)).start()
            else:
                detection, detector_name = tone_detector(detectors_config, active_tones, inactive_tones, buffer)
                if detection:
                    module_logger.debug(Fore.YELLOW + "Starting Alert Checks" + Style.RESET_ALL)
                    if detector_name not in inactive_tones:
                        inactive_tones.append(detector_name)
                        threading.Timer(detectors_config[detector_name]["ignore_time"], remove_inactive,
                                        args=(detector_name,)).start()
                        for exclude_time in icad_config["alerting"]["exclude_times"]:
                            now = datetime.datetime.now()
                            if int(now.strftime('%w')) in icad_config["alerting"]["exclude_times"][exclude_time][
                                "exclude_days"]:
                                if icad_config["alerting"]["exclude_times"][exclude_time][
                                    "exclude_time_start"] != "00:00" and \
                                        icad_config["alerting"]["exclude_times"][exclude_time][
                                            "exclude_time_end"] != "00:00":
                                    now = datetime.datetime.now()
                                    start_time = now.replace(hour=int(
                                        icad_config["alerting"]["exclude_times"][exclude_time][
                                            "exclude_time_start"].split(':')[0]), minute=int(
                                        icad_config["alerting"]["exclude_times"][exclude_time][
                                            "exclude_time_start"].split(':')[1]), second=0, microsecond=0)
                                    end_time = now.replace(hour=int(
                                        icad_config["alerting"]["exclude_times"][exclude_time][
                                            "exclude_time_end"].split(':')[0]), minute=int(
                                        icad_config["alerting"]["exclude_times"][exclude_time][
                                            "exclude_time_end"].split(':')[1]), second=0, microsecond=0)
                                    if start_time < end_time and (
                                            start_time < now < end_time or start_time > end_time and (
                                            now > start_time or now < end_time)):
                                        module_logger.debug(Fore.YELLOW + "Time is excluded, exiting Alert" + Style.RESET_ALL)
                                        continue
                                else:
                                    continue

                        module_logger.icad_info(Fore.BLUE + "Alerting!!!" + Style.RESET_ALL)
                        threading.Thread(target=process_pre_record_actions, args=(icad_config, detectors_config[detector_name], detector_name)).start()
                        if icad_config["recording"]["enabled"] == 1:
                            module_logger.debug(Fore.YELLOW + "Recording Enabled" + Style.RESET_ALL)
                            time.sleep(icad_config["recording"]["start_delay"])
                            recording_status = Recorder(icad_config, detector_name, audio_format, rate, chunk).record()
                            if not recording_status:
                                module_logger.debug(Fore.YELLOW + "No Recording Exiting Alert" + Style.RESET_ALL)
                                continue
                            else:
                                module_logger.debug(Fore.YELLOW + "Starting Post Record Actions" + Style.RESET_ALL)
                                threading.Thread(target=process_post_record_actions, args=(icad_config, detectors_config[detector_name], detector_name, recording_status)).start()
                        else:
                            threading.Thread(target=process_post_record_actions, args=(icad_config, detectors_config[detector_name], detector_name, False)).start()

                    else:
                        module_logger.debug(Fore.YELLOW + "Detector is inactive because it has been triggered already. Exiting Alert." + Style.RESET_ALL)
                else:
                    if icad_config["detection"]["mode"] == 2:
                        threading.Thread(target=tone_finder,
                                         args=(icad_config, buffer, audio_format, rate, chunk)).start()

        else:
            buffer.append(-99999)
            buffer.pop(0)


def tone_detector(detectors_config, active_tones, inactive_tones, buffer):
    for detector in active_tones:
        if detector not in inactive_tones:
            temp_buffer = buffer[40 - len(active_tones[detector]):40]
            temp_data_1 = abs(1 - array(temp_buffer) / active_tones[detector])
            temp_data_2 = temp_data_1 < detectors_config[detector]["tone_tolerance"]
            temp_data_3 = temp_data_1 > 100000
            temp_data_1 = operator.or_(temp_data_2, temp_data_3)
            if reduce(operator.and_, temp_data_1):
                module_logger.icad_info(Fore.GREEN + 'Tone Set Found Alerting: ' + detector + Style.RESET_ALL)
                return True, detector
        else:
            continue
    return False, False


def tone_finder(icad_config, buffer, audio_format, rate, chunk):
    global match_list
    global long_match_list
    freq_a = 0
    freq_b = 0

    if buffer[len(buffer) - 1] != 0 or buffer[len(buffer) - 1] != -99999:
        match_a = True
        long_match = True
        end_buffer = buffer[-19:]
        end_list_a = end_buffer[:5]
        if icad_config["detection"]["rounded_detection"] == 1:

            for freq in end_list_a:
                if int(round(freq, -1)) in range(int(round(end_list_a[0], -1)), int(round(end_list_a[0], -1)) + icad_config["detection"]["rounded_detection_range"]) or int(round(freq, -1)) in range(int(round(end_list_a[0], -1)), int(round(end_list_a[0], -1)) - icad_config["detection"]["rounded_detection_range"]):
                    nothing = ""
                    # for some reason this if statement works the best backwards.
                else:
                    match_a = False

            if int(round(end_buffer[:6][-1], -1)) in range(int(round(end_list_a[0], -1)), int(round(end_list_a[0], -1)) + icad_config["detection"]["rounded_detection_range"]) or int(round(end_buffer[:6][-1], -1)) in range(int(round(end_list_a[0], -1)), int(round(end_list_a[0], -1)) - icad_config["detection"]["rounded_detection_range"]):
                match_a = False

            if int(round(end_buffer[:7][-1], -1)) in range(int(round(end_list_a[0], -1)), int(round(end_list_a[0], -1)) + icad_config["detection"]["rounded_detection_range"]) or int(round(end_buffer[:7][-1], -1)) in range(int(round(end_list_a[0], -1)), int(round(end_list_a[0], -1)) - icad_config["detection"]["rounded_detection_range"]):
                match_a = False

            if match_a:
                freq_a = end_list_a[0]
        else:
            for freq in end_list_a:
                if round(freq, 1) != round(end_list_a[0], 1):
                    match_a = False

            if round(end_buffer[:6][-1], 1) == round(end_list_a[0], 1) or round(end_buffer[:7][-1], 1) == round(end_list_a[0], 1):
                match_a = False

            if match_a:
                freq_a = end_list_a[0]

        end_list_b = end_buffer[-14:]
        b_match = True
        if icad_config["detection"]["rounded_detection"] == 1:
            for x in end_list_b:
                if int(round(x, -1)) in range(int(round(end_list_b[0], -1)), int(round(end_list_b[0], -1)) + icad_config["detection"]["rounded_detection_range"]) or int(round(x, -1)) in range(int(round(end_list_b[0], -1)), int(round(end_list_b[0], -1)) - icad_config["detection"]["rounded_detection_range"]):
                    nothing = ""
                    # for some reason this if statement works the best backwards.
                else:
                    b_match = False
            if b_match:
                freq_b = end_list_b[0]
        else:
            for x in end_list_b:
                if round(x, 1) != round(end_list_b[0], 1):
                    b_match = False
            if b_match:
                freq_b = end_list_b[0]

        if freq_a != 0 and freq_b != 0:
            if freq_a != -99999:
                if freq_b != -9999:
                    if icad_config["detection"]["rounded_detection"] == 1:
                        if int(round(freq_a, -1)) not in range(int(round(freq_b, -1)), int(round(freq_b, -1)) - icad_config["detection"]["rounded_detection_range"]):
                            if int(round(freq_a, -1)) not in range(int(round(freq_b, -1)), int(round(freq_b, -1)) + icad_config["detection"]["rounded_detection_range"]):
                                if round(freq_a, 1) != round(freq_b, 1):
                                    module_logger.icad_info(
                                        Fore.GREEN + "Finder Detection - A Tone: " + str(round(freq_a, 1)) + " B Tone: " + str(
                                            round(freq_b, 1)) + Style.RESET_ALL)
                                    match_list["last"] = {"a": round(freq_a, 1), "b": round(freq_b, 1)}
                                    if icad_config["general"]["headless"] == 0:
                                        show_notification("Alert Detected", "Detection - A Tone: " + str(
                                            round(freq_a, 1)) + " B Tone: " + str(round(freq_b, 1)))

                                    detected_frequencies = str(round(freq_a, 1)) + "_" + str(round(freq_b, 1))
                                    if icad_config["recording"]["enabled"] == 1:
                                        module_logger.debug(Fore.YELLOW + "Recording Detection" + Style.RESET_ALL)
                                        recording_status = Recorder(icad_config, detected_frequencies, audio_format, rate, chunk).record()
                                        if not recording_status:
                                            module_logger.debug(
                                                Fore.YELLOW + "No Recording Exiting Finder Alert" + Style.RESET_ALL)
                                        else:
                                            threading.Thread(target=process_tone_finder_actions, args=(icad_config, detected_frequencies, recording_status)).start()

                    else:
                        if round(freq_a, 1) != round(freq_b, 1):
                            module_logger.icad_info(
                                Fore.GREEN + "Finder Detection - A Tone: " + str(round(freq_a, 1)) + " B Tone: " + str(
                                    round(freq_b, 1)) + Style.RESET_ALL)
                            match_list["last"] = {"a": round(freq_a, 1), "b": round(freq_b, 1)}
                            if icad_config["general"]["headless"] == 0:
                                show_notification("Alert Detected",
                                                  "Detection - A Tone: " + str(round(freq_a, 1)) + " B Tone: " + str(
                                                      round(freq_b, 1)))
                            detected_frequencies = str(round(freq_a, 1)) + "_" + str(round(freq_b, 1))
                            if icad_config["recording"]["enabled"] == 1:
                                module_logger.debug(Fore.YELLOW + "Recording Finder Detection" + Style.RESET_ALL)
                                recording_status = Recorder(icad_config, detected_frequencies, audio_format, rate,
                                                            chunk).record()
                                if not recording_status:
                                    module_logger.debug(Fore.YELLOW + "No Recording Exiting Finder Alert" + Style.RESET_ALL)
                                else:
                                    threading.Thread(target=process_tone_finder_actions, args=(icad_config, detected_frequencies, recording_status)).start()

        elif freq_a == 0 and icad_config["detection"]["find_long_tones"] == 1:
            long_tone_buffer = end_buffer[:8]
            for x in long_tone_buffer:
                if x == -99999:
                    long_match = False
                if x == 0:
                    long_match = False

                if int(round(x, -1)) in range(int(round(long_tone_buffer[0], -1)),
                                              int(round(long_tone_buffer[0], -1)) + icad_config["detection"][
                                                  "long_tone_range"]) or int(
                    round(x, -1)) in range(int(round(long_tone_buffer[0], -1)),
                                           int(round(long_tone_buffer[0], -1)) - icad_config["detection"][
                                               "long_tone_range"]):
                    # for some reason this if statement works the best backwards.
                    nothing = ""
                else:
                    long_match = False

            if int(round(long_tone_buffer[0], -1)) in range(int(round(match_list["last"]["a"], -1)),
                                                            int(round(match_list["last"]["a"], -1)) + 20) or int(
                    round(long_tone_buffer[0], -1)) in range(int(round(match_list["last"]["a"], -1)),
                                                             int(round(match_list["last"]["a"], -1)) - 20):
                long_match = False

            if int(round(long_tone_buffer[0], -1)) in range(int(round(match_list["last"]["b"], -1)),
                                                            int(round(match_list["last"]["b"], -1)) + 20) or int(
                    round(long_tone_buffer[0], -1)) in range(int(round(match_list["last"]["b"], -1)),
                                                             int(round(match_list["last"]["b"], -1)) - 20):
                long_match = False

            if round(long_tone_buffer[0], 1) == long_match_list["last"]["tone"]:
                long_match = False

            if long_match:
                # print("Long is True" + str(long_tone_buffer))
                long_freq = long_tone_buffer[0]

                if long_freq != 0:
                    if long_freq != -99999:
                        print(
                            Fore.GREEN + "Finder Detection - Long Tone: " + str(
                                round(long_freq, 1)) + Style.RESET_ALL)

                        long_match_list["last"]["tone"] = round(long_freq, 1)
                        long_freq = str(round(long_freq, 1))
                        detected_frequencies = long_freq
                        if icad_config["recording"]["enabled"] == 1:
                            module_logger.debug(Fore.YELLOW + "Recording Finder Detection" + Style.RESET_ALL)
                            recording_status = Recorder(icad_config, detected_frequencies, audio_format, rate,
                                                        chunk).record()
                            if not recording_status:
                                module_logger.debug(Fore.YELLOW + "No Recording Exiting Finder Alert" + Style.RESET_ALL)

                            else:
                                threading.Thread(target=process_tone_finder_actions,
                                             args=(icad_config, detected_frequencies, recording_status)).start()

