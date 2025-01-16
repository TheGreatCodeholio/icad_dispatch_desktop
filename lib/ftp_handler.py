import logging
import os
from datetime import datetime, timedelta
from ftplib import FTP, error_perm
from colorama import Fore, Style

# create logger
module_logger = logging.getLogger('icad_tone_detector.ftp')


def ftp_upload_to_path(icad_config_data, local_file):
    """
    Uploads a local file to the specified FTP server path.
    """
    try:
        module_logger.info(f"Uploading {local_file} to {icad_config_data['ftp_settings']['ftp_hostname']}")

        # Connect to FTP server
        ftp = FTP()
        ftp.connect(
            icad_config_data["ftp_settings"]["ftp_hostname"],
            icad_config_data["ftp_settings"]["ftp_port"]
        )

        # Login to FTP server
        ftp.login(
            user=icad_config_data["ftp_settings"]["ftp_username"],
            passwd=icad_config_data["ftp_settings"]["ftp_password"]
        )

        # Navigate to the remote directory
        remote_path = icad_config_data["ftp_settings"]["remote_path"]
        ftp.cwd(remote_path)

        # Upload the file
        with open(local_file, 'rb') as file:
            ftp.storbinary(f'STOR {os.path.basename(local_file)}', file)

        module_logger.info(f"Uploaded {local_file} to {remote_path}")
    except Exception as e:
        module_logger.error(Fore.RED + f"Failed to upload file: {e}" + Style.RESET_ALL)
    finally:
        ftp.quit()


def parse_ftp_date(date_str):
    """
    Parses FTP date strings returned by the server.
    Format: YYYYMMDDhhmmss (if supported by MDTM).
    """
    try:
        return datetime.strptime(date_str, "%Y%m%d%H%M%S")
    except ValueError as e:
        module_logger.error(Fore.RED + f"Failed to parse FTP date: {date_str}. Error: {e}" + Style.RESET_ALL)
        return None


def ftp_clean_remote_files(icad_config_data):
    """
    Cleans remote files older than a specified number of days.
    """
    try:
        ftp = FTP()
        ftp.connect(
            icad_config_data["ftp_settings"]["ftp_hostname"],
            icad_config_data["ftp_settings"]["ftp_port"]
        )

        # Login to FTP server
        ftp.login(
            user=icad_config_data["ftp_settings"]["ftp_username"],
            passwd=icad_config_data["ftp_settings"]["ftp_password"]
        )

        # Navigate to the remote directory
        remote_path = icad_config_data["ftp_settings"]["remote_path"]
        ftp.cwd(remote_path)

        # Define cleanup threshold
        cleanup_days = icad_config_data["cleanup_settings"]["remote_cleanup_days"]
        threshold_date = datetime.now() - timedelta(days=cleanup_days)

        # List files and delete old ones
        for filename in ftp.nlst():
            try:
                # Get file modification time (if supported by server)
                mdtm_response = ftp.sendcmd(f"MDTM {filename}")
                file_date = parse_ftp_date(mdtm_response.split()[1])

                if file_date and file_date < threshold_date:
                    ftp.delete(filename)
                    module_logger.info(Fore.YELLOW + f"Deleted remote file: {filename}" + Style.RESET_ALL)
                else:
                    module_logger.debug(Fore.CYAN + f"Skipped file: {filename} (not older than {cleanup_days} days)" + Style.RESET_ALL)

            except error_perm as e:
                module_logger.warning(Fore.RED + f"Permission error for file {filename}: {e}" + Style.RESET_ALL)
            except Exception as e:
                module_logger.error(Fore.RED + f"Error handling file {filename}: {e}" + Style.RESET_ALL)

        module_logger.info(Fore.GREEN + "Remote file cleanup completed" + Style.RESET_ALL)
    except Exception as e:
        module_logger.error(Fore.RED + f"Failed to clean remote files: {e}" + Style.RESET_ALL)
    finally:
        ftp.quit()
