import os
import time
import logging

# create logger
from colorama import Fore, Style

from lib.ftp_handler import ftp_clean_remote_files
from lib.sftp_handler import sftp_clean_remote_files

module_logger = logging.getLogger('icad_tone_detector.local_cleanup')


def cleanup_local_audio(icad_config):
    current_time = time.time()
    count = 0
    for f in os.listdir(icad_config["recording"]["path"]):
        path = os.path.join(icad_config["recording"]["path"], f)
        creation_time = os.path.getctime(path)
        if (current_time - creation_time) // (24 * 3600) >= icad_config["cleanup_settings"]["local_cleanup_days"]:
            count += 1
            os.unlink(path)
    module_logger.debug(Fore.YELLOW + "Cleaned " + str(count) + " Files" + Style.RESET_ALL)

def cleanup_remote_files(icad_config):
    if icad_config["sftp_settings"]["enabled"] == 1:
        try:
            sftp_clean_remote_files(icad_config)
        except Exception as e:
            module_logger.critical(Fore.RED + "SFTP Remote File Cleanup Failure:\n" + repr(e) + Style.RESET_ALL)

    if icad_config["ftp_settings"]["enabled"] == 1:
        try:
            ftp_clean_remote_files(icad_config)
        except Exception as e:
            module_logger.critical(Fore.RED + "FTP Remote File Cleanup Failure:\n" + repr(e) + Style.RESET_ALL)
