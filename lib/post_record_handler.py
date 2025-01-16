import logging
import os.path
import time
from threading import Thread

from lib.email_handler import send_email
from lib.facebook_handler import send_post
from lib.ftp_handler import ftp_upload_to_path
from lib.mp3_handler import add_id_tags, soften_clipping, noise_filter, remove_silence, high_pass_filter, \
    low_pass_filter, convert_wav_mp3, gain_filter, append_audio_file, append_text2speech_audio, remove_tones
from lib.sftp_handler import sftp_upload_to_path, clean_remote_files
from lib.pushover_handler import send_push
from lib.mysql_handler import Database
from lib.zello_handler import zello_init
from lib.telegram_handler import post_to_telegram
from lib.cleanup_handler import cleanup_local_audio
from colorama import Fore, Style

module_logger = logging.getLogger('icad_tone_detector.post_record')

threads = []


def process_post_record_actions(icad_config, detector_data, detector_name, wav_file_path):
    # Send Post Record Emails
    module_logger.icad_info(Fore.GREEN + "Processing Post Recording Email Sending" + Style.RESET_ALL)
    if icad_config["email"]["post_record_enabled"] == 1 and len(detector_data["post_record_emails"]) >= 1:
        try:
            module_logger.debug(Fore.YELLOW + "Starting Post Record Email Sending" + Style.RESET_ALL)
            if icad_config["email"]["send_as_single_email"] == 1:
                if wav_file_path:
                    send_email(icad_config, detector_data, detector_name, wav_file_path,
                               detector_data["post_record_emails"], True)
                else:
                    send_email(icad_config, detector_data, detector_name,
                               False,
                               detector_data["post_record_emails"], True)
            else:
                if wav_file_path:
                    for em in detector_data["post_record_emails"]:
                        em = [em]
                        send_email(icad_config, detector_data, detector_name,
                                   wav_file_path, em, True)
                else:
                    for em in detector_data["post_record_emails"]:
                        em = [em]
                        send_email(icad_config, detector_data, detector_name,
                                   False, em, True)
        except Exception as e:
            module_logger.critical(Fore.RED + "Email Sending Failure:\n" + repr(e) + Style.RESET_ALL)

    else:
        module_logger.debug(Fore.YELLOW + "Post Record Email Sending Disabled" + Style.RESET_ALL)

    if wav_file_path is not False:
        module_logger.icad_info(Fore.GREEN + "Processing Post Recording Audio" + Style.RESET_ALL)

    if icad_config["mp3_settings"]["fix_clipping"]["enabled"] == 1 and wav_file_path is not False:
        try:
            module_logger.debug(Fore.YELLOW + "Starting Audio Clipping Softening" + Style.RESET_ALL)
            soften_clipping(wav_file_path)
        except Exception as e:
            module_logger.critical(Fore.RED + "Audio Clipping Softening Failure:\n" + repr(e) + Style.RESET_ALL)
    else:
        module_logger.debug(Fore.YELLOW + "Audio Clipping Softening Disabled" + Style.RESET_ALL)

    if icad_config["mp3_settings"]["noise_filter"]["enabled"] == 1 and wav_file_path is not False:
        try:
            module_logger.debug(Fore.YELLOW + "Starting Audio Noise Reduction" + Style.RESET_ALL)
            noise_filter(icad_config, wav_file_path)
        except Exception as e:
            module_logger.critical(Fore.RED + "Noise Filter Failure:\n" + repr(e) + Style.RESET_ALL)
    else:
        module_logger.debug(Fore.YELLOW + "Audio Noise Reduction Disabled" + Style.RESET_ALL)
    if icad_config["mp3_settings"]["remove_silence"]["enabled"] == 1 and wav_file_path is not False:
        try:
            module_logger.debug(Fore.YELLOW + "Starting Audio Remove Silence" + Style.RESET_ALL)
            remove_silence(icad_config, wav_file_path)
        except Exception as e:
            module_logger.critical(Fore.RED + "Remove Silence Failure:\n" + repr(e) + Style.RESET_ALL)
    else:
        module_logger.debug(Fore.YELLOW + "Audio Remove Silence Disabled" + Style.RESET_ALL)

    if icad_config["mp3_settings"]["high_pass_filter"]["enabled"] == 1 and wav_file_path is not False:
        module_logger.debug(Fore.YELLOW + "Starting High Pass Filter" + Style.RESET_ALL)
        try:
            high_pass_filter(icad_config, wav_file_path)
        except Exception as e:
            module_logger.critical(Fore.RED + "High Pass Filter Failure:\n" + repr(e) + Style.RESET_ALL)
    else:
        module_logger.debug(Fore.YELLOW + "Audio High Pass Filter Disabled" + Style.RESET_ALL)

    if icad_config["mp3_settings"]["low_pass_filter"]["enabled"] == 1 and wav_file_path is not False:
        module_logger.debug(Fore.YELLOW + "Starting Low Pass Filter" + Style.RESET_ALL)
        try:
            low_pass_filter(icad_config, wav_file_path)
        except Exception as e:
            module_logger.critical(Fore.RED + "Low Pass Filter Failure:\n" + repr(e) + Style.RESET_ALL)
    else:
        module_logger.debug(Fore.YELLOW + "Audio Low Pass Filter Disabled" + Style.RESET_ALL)

    if icad_config["mp3_settings"]["gain_filter"]["enabled"] == 1 and wav_file_path is not False:
        try:
            module_logger.debug(Fore.YELLOW + "Starting Gain Filter" + Style.RESET_ALL)
            gain_filter(icad_config, wav_file_path)
        except Exception as e:
            module_logger.critical(Fore.RED + "Gain Filter Failure:\n" + repr(e) + Style.RESET_ALL)
    else:
        module_logger.debug(Fore.YELLOW + "Audio Gain Filter Disabled" + Style.RESET_ALL)

    if icad_config["mp3_settings"]["remove_tones"]["enabled"] == 1:
        module_logger.debug(Fore.YELLOW + "Starting Remove Tones File" + Style.RESET_ALL)
        try:
            remove_tones(icad_config, wav_file_path)
        except Exception as e:
            module_logger.critical(Fore.RED + "Remove Tones Failure:\n" + repr(e) + Style.RESET_ALL)
    else:
        module_logger.debug(Fore.YELLOW + "Audio remove Tones Disabled" + Style.RESET_ALL)

    if wav_file_path is not False:
        try:
            convert_wav_mp3(icad_config, wav_file_path)
        except Exception as e:
            module_logger.critical(Fore.RED + "Convert WAV to MP3 Failure:\n" + repr(e) + Style.RESET_ALL)

    if icad_config["mp3_settings"]["append_text_to_speech"]["enabled"] == 1 and wav_file_path is not False:
        module_logger.debug(Fore.YELLOW + "Starting Append Text to Speech" + Style.RESET_ALL)
        try:
            append_text2speech_audio(icad_config, detector_name, wav_file_path.replace(".mp3", ".wav"))
        except Exception as e:
            module_logger.critical(Fore.RED + "Append Text to Speech Failure:\n" + repr(e) + Style.RESET_ALL)
    else:
        module_logger.debug(Fore.YELLOW + "Audio Append Text to Speech Disabled" + Style.RESET_ALL)

    if icad_config["mp3_settings"]["append_audio_file"]["enabled"] == 1 and wav_file_path is not False:
        module_logger.debug(Fore.YELLOW + "Starting Append Audio File" + Style.RESET_ALL)
        try:
            append_audio_file(detector_name, detector_data, wav_file_path.replace(".mp3", ".wav"))
        except Exception as e:
            module_logger.critical(Fore.RED + "Append Audio File Failure:\n" + repr(e) + Style.RESET_ALL)
    else:
        module_logger.debug(Fore.YELLOW + "Audio Append Audio File Disabled" + Style.RESET_ALL)

    if wav_file_path is not False:
        try:
            add_id_tags(icad_config, detector_name, wav_file_path.replace(".wav", ".mp3"))
        except Exception as e:
            module_logger.critical(Fore.RED + "Add ID Tags to MP3 Failure:\n" + repr(e) + Style.RESET_ALL)

    module_logger.icad_info(Fore.GREEN + "Processing Audio File Upload" + Style.RESET_ALL)

    if icad_config["sftp_settings"]["enabled"] == 1 and wav_file_path is not False:
        module_logger.debug(Fore.YELLOW + "Starting Audio File Upload via SFTP" + Style.RESET_ALL)
        try:
            sftp_upload_to_path(icad_config, wav_file_path.replace(".wav", ".mp3"))
        except Exception as e:
            module_logger.critical(Fore.RED + "SFTP Upload Failure:\n" + repr(e) + Style.RESET_ALL)
    else:
        module_logger.debug(Fore.YELLOW + "Audio File Upload via SFTP disabled" + Style.RESET_ALL)

    if icad_config["ftp_settings"]["enabled"] == 1 and wav_file_path is not False:
        module_logger.debug(Fore.YELLOW + "Starting Audio File Upload via FTP" + Style.RESET_ALL)
        try:
            ftp_upload_to_path(icad_config, wav_file_path.replace(".wav", ".mp3"))
        except Exception as e:
            module_logger.critical(Fore.RED + "FTP Upload Failure:\n" + repr(e) + Style.RESET_ALL)
    else:
        module_logger.debug(Fore.YELLOW + "Audio File Upload via FTP disabled" + Style.RESET_ALL)

    if icad_config["mysql_settings"]["enabled"] == 1 and wav_file_path is not False:
        module_logger.debug(Fore.YELLOW + "Starting Database Add Detection." + Style.RESET_ALL)
        try:
            result = Database(icad_config).check_for_table("incidents")
            if result:

                    Database(icad_config).add_new_call(time.time(), detector_name, detector_data, icad_config["general"]["url_audio_path"] + wav_file_path.split("/")[-1].replace(".wav", ".mp3"))
                    module_logger.debug(Fore.YELLOW + "Finished Adding Detection to Database" + Style.RESET_ALL)

            else:
                module_logger.critical(Fore.RED + "MySQL Database Incidents Table doesn't exist." + Style.RESET_ALL)
        except Exception as e:
            module_logger.critical(repr(e))
    else:
        module_logger.debug(Fore.YELLOW + "Database Add Detection Disabled." + Style.RESET_ALL)

    if icad_config["facebook_settings"]["enabled"] == 1:
        module_logger.debug(Fore.YELLOW + "Starting Facebook Notifications" + Style.RESET_ALL)
        if wav_file_path is not False:
            fb = Thread(target=send_post, args=(icad_config, detector_name, detector_data,
                                            icad_config["general"]["url_audio_path"] + wav_file_path.split("/")[
                                                -1].replace(".wav", ".mp3"), wav_file_path.split("/")[
                                                -1].replace(".wav", ".mp3")))
            fb.start()
            threads.append(fb)
        else:
            module_logger.critical(Fore.RED + "No Audio File For Facebook." + Style.RESET_ALL)

    else:
        module_logger.debug(Fore.YELLOW + "Facebook Notifications Disabled" + Style.RESET_ALL)

    if icad_config["pushover_settings"]["enabled"] == 1:
        module_logger.debug(Fore.YELLOW + "Starting Pushover Notifications" + Style.RESET_ALL)
        if wav_file_path is not False:
            po = Thread(target=send_push, args=(icad_config, detector_name, detector_data,
                                            icad_config["general"]["url_audio_path"] + wav_file_path.split("/")[
                                                -1].replace(".wav", ".mp3")))
        else:
            po = Thread(target=send_push, args=(icad_config, detector_name, detector_data, wav_file_path))

        po.start()
        threads.append(po)
    else:
        module_logger.debug(Fore.YELLOW + "Pushover Notifications Disabled" + Style.RESET_ALL)

    if icad_config["zello_settings"]["enabled"] == 1:
        module_logger.debug(Fore.YELLOW + "Starting Zello Stream" + Style.RESET_ALL)
        zl = Thread(target=zello_init, args=(icad_config, detector_name, wav_file_path.replace(".wav", ".mp3")))
        zl.start()
        threads.append(zl)
    else:
        module_logger.debug(Fore.YELLOW + "Zello Stream Disabled" + Style.RESET_ALL)

    if icad_config["telegram_settings"]["enabled"] == 1:
        module_logger.debug(Fore.YELLOW + "Starting Telegram Channel Post" + Style.RESET_ALL)
        # Post to Telegram Channels
        tg = Thread(target=post_to_telegram, args=(icad_config, detector_name, detector_data, icad_config["general"]["url_audio_path"] + wav_file_path.split("/")[-1].replace(".wav", ".mp3"), wav_file_path.replace(".wav", ".mp3")))
        tg.start()
        threads.append(tg)
    else:
        module_logger.debug(Fore.YELLOW + "Telegram Channel Post Disabled" + Style.RESET_ALL)

    if icad_config["cleanup_settings"]["local_enabled"] == 1:
        module_logger.debug(Fore.YELLOW + "Starting Local File Cleanup" + Style.RESET_ALL)
        try:
            cleanup_local_audio(icad_config)
        except Exception as e:
            module_logger.critical(Fore.RED + "Local File Cleanup Failure:\n" + repr(e) + Style.RESET_ALL)

    else:
        module_logger.debug(Fore.YELLOW + "Local File Cleanup Disabled" + Style.RESET_ALL)

    if icad_config["cleanup_settings"]["remote_enabled"] == 1:
        module_logger.debug(Fore.YELLOW + "Starting Remote File Cleanup" + Style.RESET_ALL)
        try:
            clean_remote_files(icad_config)
        except Exception as e:
            module_logger.critical(Fore.RED + "Remote File Cleanup Failure:\n" + repr(e) + Style.RESET_ALL)
    else:
        module_logger.debug(Fore.YELLOW + "Remote File Cleanup Disabled" + Style.RESET_ALL)

    if os.path.exists(wav_file_path):
        os.remove(wav_file_path)

    for th in threads:
        th.join()

    module_logger.icad_info(Fore.BLUE + "Detection Alerts Complete." + Style.RESET_ALL)

