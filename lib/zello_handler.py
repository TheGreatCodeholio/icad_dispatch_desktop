import base64
import json
import os.path
import time
import logging
import asyncio

import aiohttp
import socket
import subprocess
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256

# create logger
from colorama import Fore, Style

from lib.cache_check_handler import create_cached_item, get_all_cached_items, delete_cache, delete_single_cached_item

module_logger = logging.getLogger('icad_tone_detector.zello')


def zello_create_token(icad_config):
    module_logger.debug(Fore.YELLOW + "Creating Zello Token" + Style.RESET_ALL)
    if os.path.exists(icad_config["zello_settings"]["private_key"]):
        f = open(icad_config["zello_settings"]["private_key"], 'r')
    else:
        module_logger.critical(Fore.RED + "Zello Private Key Not Found Exiting" + Style.RESET_ALL)
        return
    key = RSA.import_key(f.read())
    # Create a Zello-specific JWT.  Can't use PyJWT because Zello doesn't support url safe base64 encoding in the JWT.
    header = {"typ": "JWT", "alg": "RS256"}
    payload = {"iss": icad_config["zello_settings"]["issuer"], "exp": round(time.time() + 60)}
    signer = pkcs1_15.new(key)
    json_header = json.dumps(header, separators=(",", ":"), cls=None).encode("utf-8")
    json_payload = json.dumps(payload, separators=(",", ":"), cls=None).encode("utf-8")
    h = SHA256.new(base64.standard_b64encode(json_header) + b"." + base64.standard_b64encode(json_payload))
    signature = signer.sign(h)
    token = (base64.standard_b64encode(json_header) + b"." + base64.standard_b64encode(
        json_payload) + b"." + base64.standard_b64encode(signature))
    return token


def zello_convert(local_mp3_path):
    module_logger.debug(Fore.YELLOW + "Converting Audio to Opus" + Style.RESET_ALL)
    command = "ffmpeg -i " + local_mp3_path + " -c:a libopus -b:a 64k " + local_mp3_path.replace(".mp3", ".opus")
    subprocess.run(command.split(), capture_output=True)
    return local_mp3_path.replace(".mp3", ".opus")


class ZelloSend:
    def __init__(self, icad_config, audio_file):
        self.logger = logging.getLogger('icad_tone_detector.zello.ZelloSend')
        self.icad_config = icad_config
        self.audio = audio_file
        self.endpoint = "wss://zello.io/ws"
        self.ws_timeout = 2
        self.zello_ws = None
        self.zello_stream_id = None

    def zello_init_upload(self):
        self.logger.info(Fore.YELLOW + "Starting Zello Stream" + Style.RESET_ALL)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        loop.run_until_complete(ZelloSend(self.icad_config, self.audio).zello_stream_audio_to_channel())

        self.logger.debug(Fore.YELLOW + "Closing Zello Stream Loop" + Style.RESET_ALL)
        loop.close()

    async def zello_stream_audio_to_channel(self):
        # Pass out the opened WebSocket and StreamID to handle synchronous keyboard interrupt
        try:
            opus_stream = OpusFileStream(self.audio)
            conn = aiohttp.TCPConnector(family=socket.AF_INET, ssl=False)
            async with aiohttp.ClientSession(connector=conn) as session:
                async with session.ws_connect(self.endpoint) as ws:
                    self.zello_ws = ws
                    await asyncio.wait_for(ZelloSend(self.icad_config, self.audio).authenticate(ws), self.ws_timeout)
                    stream_id = await asyncio.wait_for(
                        ZelloSend(self.icad_config, self.audio).zello_stream_start(ws, opus_stream), self.ws_timeout)
                    self.zello_stream_id = stream_id
                    print(f"Started streaming {self.audio}")
                    await ZelloSend(self.icad_config, self.audio).zello_stream_send_audio(session, ws, stream_id,
                                                                                          opus_stream)
                    await asyncio.wait_for(ZelloSend(self.icad_config, self.audio).zello_stream_stop(ws, stream_id),
                                           self.ws_timeout)
        except (NameError, aiohttp.client_exceptions.ClientError, IOError) as error:
            print(error)
        except asyncio.TimeoutError:
            print("Communication timeout")

    async def authenticate(self, ws):
        # https://github.com/zelloptt/zello-channel-api/blob/master/AUTH.md
        await ws.send_str(json.dumps({
            "command": "logon",
            "seq": 1,
            "auth_token": self.icad_config["zello_settings"]["token"].decode("utf-8"),
            "username": self.icad_config["zello_settings"]["username"],
            "password": self.icad_config["zello_settings"]["password"],
            "channel": self.icad_config["zello_settings"]["channel"]
        }))

        is_authorized = False
        is_channel_available = False
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if "refresh_token" in data:
                    is_authorized = True
                elif "command" in data and "status" in data and data["command"] == "on_channel_status":
                    is_channel_available = data["status"] == "online"
                if is_authorized and is_channel_available:
                    break

        if not is_authorized or not is_channel_available:
            raise NameError('Authentication failed')

    async def zello_stream_start(self, ws, opus_stream):
        sample_rate = opus_stream.sample_rate
        frames_per_packet = opus_stream.frames_per_packet
        packet_duration = opus_stream.packet_duration

        # Sample_rate is in little endian.
        # https://github.com/zelloptt/zello-channel-api/blob/409378acd06257bcd07e3f89e4fbc885a0cc6663/sdks/js/src/classes/utils.js#L63
        codec_header = base64.b64encode(
            sample_rate.to_bytes(2, "little") + frames_per_packet.to_bytes(1, "big") + packet_duration.to_bytes(1,
                                                                                                                "big")).decode()

        await ws.send_str(json.dumps({
            "command": "start_stream",
            "seq": 2,
            "type": "audio",
            "codec": "opus",
            "codec_header": codec_header,
            "packet_duration": packet_duration
        }))

        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if "success" in data and "stream_id" in data and data["success"]:
                    return data["stream_id"]
                elif "error" in data:
                    print("Got an error:", data["error"])
                    break
                else:
                    # Ignore the messages we are not interested in
                    continue

        raise NameError('Failed to create Zello audio stream')

    async def zello_stream_stop(self, ws, stream_id):
        await ws.send_str(json.dumps({
            "command": "stop_stream",
            "stream_id": stream_id
        }))

    async def send_audio_packet(self, ws, packet):
        # Once the data has been sent - listen on websocket, connection may be closed otherwise.
        await ws.send_bytes(packet)
        await ws.receive()

    def generate_zello_stream_packet(self, stream_id, packet_id, data):
        # https://github.com/zelloptt/zello-channel-api/blob/master/API.md#stream-data
        return (1).to_bytes(1, "big") + stream_id.to_bytes(4, "big") + \
            packet_id.to_bytes(4, "big") + data

    async def zello_stream_send_audio(self, session, ws, stream_id, opus_stream):
        packet_duration_sec = opus_stream.packet_duration / 1000
        start_ts_sec = time.time_ns() / 1000000000
        time_streaming_sec = 0
        packet_id = 0
        while True:
            data = opus_stream.get_next_opus_packet()

            if not data:
                self.logger.debug(Fore.YELLOW + "Completed Zello Stream" + Style.RESET_ALL)
                break

            if session.closed:
                raise NameError("Session is closed!")

            packet_id += 1
            packet = ZelloSend(self.icad_config, self.audio).generate_zello_stream_packet(stream_id, packet_id, data)
            try:
                # Once wait_for() is timed out - it takes additional operational time.
                # Recalculate delay and sleep at the end of the loop to compensate this delay.
                await asyncio.wait_for(
                    ZelloSend(self.icad_config, self.audio).send_audio_packet(ws, packet), packet_duration_sec * 0.8
                )
            except asyncio.TimeoutError:
                pass

            time_streaming_sec += packet_duration_sec
            time_elapsed_sec = (time.time_ns() / 1000000000) - start_ts_sec
            sleep_delay_sec = time_streaming_sec - time_elapsed_sec

            if sleep_delay_sec > 0.001:
                time.sleep(sleep_delay_sec)


class OpusFileStream:
    # https://tools.ietf.org/html/rfc7845
    # https://tools.ietf.org/html/rfc3533
    def __init__(self, filename):
        self.opusfile = open(filename, "rb")
        if not self.opusfile:
            raise NameError(f'Failed opening {filename}')
        self.segment_sizes = bytes()
        self.segment_idx = 0
        self.segments_count = 0
        self.sequence_number = -1
        self.opus_headers_count = 0
        self.packet_duration = 0
        self.frames_per_packet = 0
        self.saved_packets = list()
        self.__fill_opus_config()

    def __get_next_ogg_packet_start(self):
        # Each Ogg page starts with magic bytes "OggS"
        # Stream may be corrupted, so find a first valid magic
        magic = bytes("OggS", "ascii")
        verified_bytes = 0
        while True:
            byte = self.opusfile.read(1)
            if not byte:
                return False

            if byte[0] == magic[verified_bytes]:
                verified_bytes += 1
                if verified_bytes == 4:
                    return True
            else:
                verified_bytes = 0

    def __parse_ogg_packet_header(self):
        # The Ogg page has the following format:
        #  0               1               2               3                Byte
        #  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1| Bit
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # | capture_pattern: Magic number for page start "OggS"           | 0-3
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # | version       | header_type   | granule_position              | 4-7
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # |                                                               | 8-11
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # |                               | bitstream_serial_number       | 12-15
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # |                               | page_sequence_number          | 16-19
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # |                               | CRC_checksum                  | 20-23
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # |                               | page_segments | segment_table | 24-27
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # | ...                                                           | 28-
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        version = self.opusfile.read(1)
        header_type = self.opusfile.read(1)
        granule = self.opusfile.read(8)
        serial_num = self.opusfile.read(4)
        self.sequence_number = int.from_bytes(self.opusfile.read(4), "little")
        checksum = int.from_bytes(self.opusfile.read(4), "little")
        self.segments_count = int.from_bytes(self.opusfile.read(1), "little")
        self.segment_idx = 0
        if self.segments_count > 0:
            self.segment_sizes = self.opusfile.read(self.segments_count)

    def __get_ogg_segment_data(self):
        data = bytes()
        continue_needed = False

        # Read data from the next segment according to the sizes table page_segments.
        # The length of 255 indicates the data requires continuing from the next
        # segment. The data from the last segment may still require continuing.
        # Return the bool continue_needed to accumulate such lacing data.
        while self.segment_idx < self.segments_count:
            segment_size = self.segment_sizes[self.segment_idx]
            segment = self.opusfile.read(segment_size)
            data += segment
            continue_needed = (segment_size == 255)
            self.segment_idx += 1
            if not continue_needed:
                break

        return data, continue_needed

    def __parse_opushead_header(self, data):
        # OpusHead header format:
        #  0               1               2               3                Byte
        #  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1| Bit
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # |      'O'      |      'p'      |      'u'      |      's'      | 0-3
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # |      'H'      |      'e'      |      'a'      |      'd'      | 4-7
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # |  Version = 1  | Channel Count |           Pre-skip            | 8-11
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # |                     Input Sample Rate (Hz)                    | 12-15
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # |   Output Gain (Q7.8 in dB)    | Mapping Family|               | 16-
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+               :
        # :               Optional Channel Mapping Table...               :
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        if data.find(bytes("OpusHead", "ascii")) != 0:
            return False
        version = data[8]
        channels = data[9]
        preskip = int.from_bytes(data[10:12], "little")
        self.sample_rate = int.from_bytes(data[12:15], "little")
        return True

    def __parse_opustags_header(self, data):
        #  0               1               2               3                Byte
        #  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1| Bit
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # |      'O'      |      'p'      |      'u'      |      's'      | 0-3
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # |      'T'      |      'a'      |      'g'      |      's'      | 4-7
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # |                     Vendor String Length                      | 8-11
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # :                        Vendor String...                       : 12-
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # |                   User Comment List Length                    |
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # |                 User Comment #0 String Length                 |
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # :                   User Comment #0 String...                   :
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        # |                 User Comment #1 String Length                 |
        # +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        return data.find(bytes("OpusTags", "ascii")) == 0

    def __parse_opus_toc(self, data):
        # https://tools.ietf.org/html/rfc6716#section-3.1
        # Each Opus packet starts with the Table Of Content Byte:
        # |0 1 2 3 4 5 6 7| Bit
        # +-+-+-+-+-+-+-+-+
        # | config  |s| c |
        # +-+-+-+-+-+-+-+-+
        toc_c = data[0] & 0x03
        if toc_c == 0:
            frames_per_packet = 1
        elif toc_c == 1 or toc_c == 2:
            frames_per_packet = 2
        else:
            # API requires predefined number of frames per packet
            print("An arbitrary number of frames in the packet - possible audio arifacts")
            frames_per_packet = 1

        configs_ms = {}
        configs_ms[2.5] = [16, 20, 24, 28]
        configs_ms[5] = [17, 21, 25, 29]
        configs_ms[10] = [0, 4, 8, 12, 14, 18, 22, 26, 30]
        configs_ms[20] = [1, 5, 9, 13, 15, 19, 23, 27, 31]
        configs_ms[40] = [2, 6, 10]
        configs_ms[60] = [3, 7, 11]

        durations = [2.5, 5, 10, 20, 40, 60]
        conf = data[0] >> 3 & 0x1f

        for duration in durations:
            if conf in configs_ms[duration]:
                return frames_per_packet, duration

        return frames_per_packet, 20

    def all_headers_parsed(self):
        # There are three mandatory headers. Don't send data until the headers are parsed.
        return self.opus_headers_count >= 3

    def get_next_opus_packet(self):
        continue_needed = False
        data = bytes()

        # The Table Of Contents byte has been read from the first audio data segment
        # stored in the saved_packets[] list.
        if self.all_headers_parsed() and len(self.saved_packets) > 0:
            data = self.saved_packets[0]
            self.saved_packets.remove(self.saved_packets[0])
            return data

        while True:
            if self.segment_idx >= self.segments_count:
                last_seq_num = self.sequence_number

                # Move to next Ogg packet
                if self.__get_next_ogg_packet_start():
                    self.__parse_ogg_packet_header()
                else:
                    return None

                # Drop current data if continuation sequence is broken
                if continue_needed and (last_seq_num + 1) != self.sequence_number:
                    self.segments_count = -1
                    print("Skipping frame: continuation sequence is broken")
                    continue

            # Get another chunk of data from the parsed Ogg page
            segment_data, continue_needed = self.__get_ogg_segment_data()
            data += segment_data
            # The last data chunk may require continuing in the next Ogg page
            if continue_needed:
                continue

            # Do not send Opus headers
            if not self.all_headers_parsed():
                self.__parse_opus_headers(data)
                data = bytes()
                continue

            # Verify the Opus TOC is the same as we initially declared
            frames, duration = self.__parse_opus_toc(data)
            if self.frames_per_packet != frames or self.packet_duration != duration:
                data = bytes()
                print("Skipping frame - TOC differs")
                continue

            return data

        return None

    def __parse_opus_headers(self, data):
        # First header is OpusHead, second one - OpusTags.
        # Third one is a Table Of Contents byte from the first Opus packet.
        if self.opus_headers_count < 1:
            if self.__parse_opushead_header(data):
                self.opus_headers_count += 1
        elif self.opus_headers_count < 2:
            if self.__parse_opustags_header(data):
                self.opus_headers_count += 1
        elif self.opus_headers_count < 3:
            frames_per_packet, packet_duration = self.__parse_opus_toc(data)
            self.frames_per_packet = frames_per_packet
            self.packet_duration = packet_duration
            self.opus_headers_count += 1
            self.saved_packets.append(data)

    def __fill_opus_config(self):
        while not self.all_headers_parsed():
            packet = self.get_next_opus_packet()
            if not packet:
                raise NameError('Invalid Opus file')


def zello_init(icad_config, detector_name, mp3_local_path):
    try:
        icad_config["zello_settings"]["token"] = zello_create_token(icad_config)
        opus_file = zello_convert(mp3_local_path)
        module_logger.debug(Fore.YELLOW + "Queueing For Zello Stream" + Style.RESET_ALL)
        service = "zello"

        cache_data = {"detector_name": detector_name, "mp3_local_path": mp3_local_path, "opus_file_path": opus_file}

        create_cached_item(service, cache_data)
        module_logger.debug(Fore.YELLOW + "Waiting for additional tones from same call." + Style.RESET_ALL)
        time.sleep(icad_config["zello_settings"]["call_wait_time"])
        calls_result = get_all_cached_items(service)
        if calls_result:
            working_call = calls_result[detector_name]
            if working_call:
                if len(calls_result) >= 2:
                    delete_cache(service)
                    ZelloSend(icad_config, opus_file).zello_init_upload()
                else:
                    delete_cache(service)
                    ZelloSend(icad_config, opus_file).zello_init_upload()
                return
        else:
            module_logger.debug(Fore.YELLOW + detector_name + " part of another call. Not Posting." + Style.RESET_ALL)

        if os.path.exists(opus_file):
            os.remove(opus_file)
    except Exception as e:
        module_logger.critical(Fore.RED + "Zello Upload Failure:\n" + repr(e) + Style.RESET_ALL)
