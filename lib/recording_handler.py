import datetime
import logging
import math
import os
import struct
import time
import wave
import pyaudio
from colorama import Fore, Style

module_logger = logging.getLogger('icad_tone_detector.recording')


class Recorder:

    @staticmethod
    def rms(frame):
        count = len(frame) / 2
        format = "%dh" % (count)
        shorts = struct.unpack(format, frame)

        sum_squares = 0.0
        for sample in shorts:
            n = sample * (1.0 / 32768.0)
            sum_squares += n * n
        rms = math.pow(sum_squares / count, 0.5)

        return rms * 1000

    def __init__(self, icad_config, detection_name, audio_format, rate, chunk):
        self.icad_config = icad_config
        self.detection_name = detection_name
        self.audio_format = audio_format
        self.rate = rate
        self.chunk = chunk
        self.logger = logging.getLogger('icad_tone_detector.recording.Recorder')
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=self.audio_format,
                                  channels=1,
                                  rate=self.rate,
                                  input=True,
                                  output=True,
                                  input_device_index=self.icad_config["audio"]["input_device_index"],
                                  output_device_index=self.icad_config["audio"]["output_device_index"],
                                  frames_per_buffer=self.chunk)

    def record(self):
        rec = []
        rec_start = time.time()
        current = time.time()
        end = time.time() + self.icad_config["recording"]["silence_release"]
        rec_max = time.time() + self.icad_config["recording"]["max_length"]

        while current <= end and current <= rec_max:
            data = self.stream.read(self.chunk)
            if self.rms(data) >= 20:
                end = time.time() + self.icad_config["recording"]["silence_release"]

            current = time.time()
            rec.append(data)
        module_logger.debug(Fore.YELLOW + "Recording Finished" + Style.RESET_ALL)
        rec_length = time.time() - rec_start
        rec_status = self.write(rec_length, b''.join(rec))
        self.stream.close()
        return rec_status

    def write(self, rec_length, recording):
        if rec_length > self.icad_config["recording"]["min_length"]:
            module_logger.debug(Fore.YELLOW + "Saving Recording." + Style.RESET_ALL)
            x = datetime.datetime.now()
            current_date = x.strftime("%Y_%m_%d_%H_%M_%S")
            if not os.path.exists(self.icad_config["recording"]["path"]):
                os.mkdir(self.icad_config["recording"]["path"])

            file_path = self.icad_config["recording"]["path"]
            file_name = self.detection_name.replace(" ", "_").lower() + "_" + current_date + ".wav"

            wf = wave.open(file_path + "/" + file_name, 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(self.p.get_sample_size(self.audio_format))
            wf.setframerate(self.rate)
            wf.writeframes(recording)
            wf.close()
            module_logger.icad_info(Fore.GREEN + f'Recording written to file: {file_path + "/" + file_name}' + Style.RESET_ALL)
            return file_path + "/" + file_name
        else:
            module_logger.warning(Fore.CYAN + "Recording Too Short Discarding." + Style.RESET_ALL)
            return False
