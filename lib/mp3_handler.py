import datetime
import logging
import subprocess

from colorama import Fore, Style
from pydub import AudioSegment
import pyttsx3
import os
import shutil

from pydub.silence import split_on_silence

module_logger = logging.getLogger('icad_tone_detector.mp3')


def soften_clipping(wav_file_path):
    module_logger.debug(Fore.YELLOW + "Fixing Clipping in Audio" + Style.RESET_ALL)
    command = "ffmpeg -y -i " + wav_file_path + " -af asoftclip=type=hard " + wav_file_path.replace(".wav",
                                                                                                    "_clipping.wav")
    result = subprocess.run(command.split(), capture_output=True, text=True)
    module_logger.debug(Fore.YELLOW + "Clipping Filter: " + str(result.stdout) + Style.RESET_ALL)
    shutil.move(wav_file_path.replace(".wav", "_clipping.wav"), wav_file_path)


def noise_filter(icad_config_data, wav_file_path):
    module_logger.debug(Fore.YELLOW + "Applying Noise Filter to Audio" + Style.RESET_ALL)

    if icad_config_data["mp3_settings"]["noise_filter"]["model"] == 0:

        rnnn = "bin/bd.rnnn"
    elif icad_config_data["mp3_settings"]["noise_filter"]["model"] == 1:
        rnnn = "bin/lq.rnnn"
    else:
        rnnn = "bin/cb.rnnn"

    command = "ffmpeg -y -i " + wav_file_path + " -af arnndn=m=" + rnnn + " " + wav_file_path.replace(".wav",
                                                                                                      "_noise.wav")
    result = subprocess.run(command.split(), capture_output=True, text=True)
    module_logger.debug(Fore.YELLOW + "Noise Filter: " + str(result.stdout) + Style.RESET_ALL)
    shutil.move(wav_file_path.replace(".wav", "_noise.wav"), wav_file_path)


def remove_silence(icad_config_data, wav_file_path):
    module_logger.info(Fore.YELLOW + "Removing Silence From Audio" + Style.RESET_ALL)
    command = "ffmpeg -y -i " + wav_file_path + " -af silenceremove=stop_periods=-1:stop_threshold=" + str(
        icad_config_data["mp3_settings"]["remove_silence"]["silence_threshold"]) + "dB:stop_duration=" + str(
        icad_config_data["mp3_settings"]["remove_silence"]["min_silence_length"]) + " " + wav_file_path.replace(".wav",
                                                                                                                "_silence.wav")
    result = subprocess.run(command.split(), capture_output=True, text=True)
    module_logger.debug(Fore.YELLOW + "Silence Filter: " + str(result.stdout) + Style.RESET_ALL)
    shutil.move(wav_file_path.replace(".wav", "_silence.wav"), wav_file_path)


def high_pass_filter(icad_config_data, wav_file_path):
    module_logger.debug(Fore.YELLOW + "Applying High Pass Filter" + Style.RESET_ALL)
    command = "ffmpeg -y -i " + wav_file_path + " -af highpass=f=" + str(
        icad_config_data["mp3_settings"]["high_pass_filter"]["cutoff_freq"]) + " " + wav_file_path.replace(".wav",
                                                                                                           "_high.wav")
    result = subprocess.run(command.split(), capture_output=True, text=True)
    module_logger.debug(Fore.YELLOW + "High Pass Filter: " + str(result.stdout) + Style.RESET_ALL)
    shutil.move(wav_file_path.replace(".wav", "_high.wav"), wav_file_path)


def low_pass_filter(icad_config_data, wav_file_path):
    module_logger.debug(Fore.YELLOW + "Applying Low Pass Filter" + Style.RESET_ALL)
    command = "ffmpeg -y -i " + wav_file_path + " -af lowpass=f=" + str(
        icad_config_data["mp3_settings"]["low_pass_filter"]["cutoff_freq"]) + " " + wav_file_path.replace(".wav",
                                                                                                          "_low.wav")
    result = subprocess.run(command.split(), capture_output=True, text=True)
    module_logger.debug(Fore.YELLOW + "Low Pass Filter: " + str(result.stdout) + Style.RESET_ALL)
    shutil.move(wav_file_path.replace(".wav", "_low.wav"), wav_file_path)


def gain_filter(icad_config_data, wav_file_path):
    module_logger.debug(Fore.YELLOW + "Applying Gain Filter" + Style.RESET_ALL)
    command = "ffmpeg -i " + wav_file_path + " -filter:a volume=" + str(
        icad_config_data["mp3_settings"]["gain_filter"]["gain_db"]) + "dB " + wav_file_path.replace(".wav",
                                                                                                    "_gain.wav")
    result = subprocess.run(command.split(), capture_output=True, text=True)
    module_logger.debug(Fore.YELLOW + "Gain Filter: " + str(result.stdout) + Style.RESET_ALL)
    shutil.move(wav_file_path.replace(".wav", "_gain.wav"), wav_file_path)


def remove_tones(icad_config_data, wav_file_path):
    audio_segment = AudioSegment.from_wav(wav_file_path)
    chunks = split_on_silence(
        # Use the loaded audio.
        audio_segment,
        # Specify that a silent chunk must be at least 2 seconds or 2000 ms long.
        min_silence_len=icad_config_data["mp3_settings"]["remove_tones"]["min_silence_length"],
        # Consider a chunk silent if it's quieter than -16 dBFS.
        # (You may want to adjust this parameter.)
        silence_thresh=icad_config_data["mp3_settings"]["remove_tones"]["silence_threshold"],
        keep_silence=1000
    )
    # now recombine the chunks so that the parts are at least 90 sec lon
    export_list = []
    new_audio = 0
    for i, chunk in enumerate(chunks):
        if chunk.duration_seconds >= 6:
            export_list.append(chunk)
    for ch in export_list:
        new_audio += ch
    if new_audio != 0:
        new_audio.export(wav_file_path, format="wav")


def convert_wav_mp3(icad_config_data, wav_file_path):
    if icad_config_data["mp3_settings"]["convert_to_stereo"]["enabled"] == 1:
        module_logger.debug(Fore.YELLOW + "Converting WAV to Stereo MP3 at " + str(
            icad_config_data["mp3_settings"]["bitrate"]) + "k" + Style.RESET_ALL)
        command = "ffmpeg -y -i " + wav_file_path + " -vn -ar 22050 -ac 2 -b:a " + str(
            icad_config_data["mp3_settings"]["bitrate"]) + "k " + wav_file_path.replace(".wav", ".mp3")
        result = subprocess.run(command.split(), capture_output=True, text=True)
        module_logger.debug(Fore.YELLOW + "Convert MP3 Stereo: " + str(result.stdout) + Style.RESET_ALL)
    else:
        module_logger.debug(Fore.YELLOW + "Converting WAV to Mono MP3 at " + str(
            icad_config_data["mp3_settings"]["bitrate"]) + "k" + Style.RESET_ALL)
        command = "ffmpeg -y -i " + wav_file_path + " -vn -ar 22050 -ac 1 -b:a " + str(
            icad_config_data["mp3_settings"]["bitrate"]) + "k " + wav_file_path.replace(".wav", ".mp3")
        result = subprocess.run(command.split(), capture_output=True, text=True)
        module_logger.debug(Fore.YELLOW + "Convert MP3 Mono: " + str(result.stdout) + Style.RESET_ALL)


def append_text2speech_audio(icad_config_data, detector_name, mp3_file):
    module_logger.debug(Fore.YELLOW + "Appending Text to Speech" + Style.RESET_ALL)
    x = datetime.datetime.now()
    current_date = x.strftime("%Y_%m_%d_%H_%M")
    detector_name = detector_name.replace(" ", "_")
    engine = pyttsx3.init()
    engine.setProperty('rate', icad_config_data["mp3_settings"]["append_text_to_speech"]["speech_rate"])
    engine.save_to_file(detector_name, icad_config_data["recording"]["path"] + detector_name + ".mp3")
    engine.runAndWait()
    audio1 = AudioSegment.from_mp3(mp3_file)
    audio2 = AudioSegment.from_mp3(icad_config_data["recording"]["path"] + detector_name + ".mp3")
    new_audio = audio2 + audio1
    new_audio.export(mp3_file, format="mp3",
                     tags={'artist': detector_name, 'album': 'iCAD Dispatch', 'comments': current_date})
    if os.path.exists(icad_config_data["recording"]["path"] + detector_name + ".mp3"):
        os.remove(icad_config_data["recording"]["path"] + detector_name + ".mp3")


def append_audio_file(detector_name, detector_data, mp3_file_path):
    module_logger.debug(Fore.YELLOW + "Appending Audio File" + Style.RESET_ALL)
    x = datetime.datetime.now()
    current_date = x.strftime("%Y_%m_%d_%H_%M")
    audio1 = AudioSegment.from_mp3(mp3_file_path)
    audio2 = AudioSegment.from_mp3(detector_data["mp3_append_file"])
    new_audio = audio2 + audio1
    new_audio.export(mp3_file_path, format="mp3",
                     tags={'artist': detector_name, 'album': 'iCAD Dispatch', 'comments': current_date})


def add_id_tags(icad_config_data, detector_name, mp3_file_path):
    if icad_config_data["mp3_settings"]["append_audio_file"]["enabled"] == 0 and \
            icad_config_data["mp3_settings"]["append_text_to_speech"]["enabled"] == 0:
        x = datetime.datetime.now()
        current_date = x.strftime("%Y_%m_%d_%H_%M")
        audio = AudioSegment.from_mp3(mp3_file_path)
        audio.export(mp3_file_path, format="mp3",
                     tags={'title': 'iCAD Dispatch: ' + str(current_date), 'artist': detector_name,
                           'album': 'iCAD Dispatch', 'comments': current_date})
