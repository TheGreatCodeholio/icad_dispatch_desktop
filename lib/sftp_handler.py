import logging

from colorama import Fore, Style
from paramiko import SSHClient, AutoAddPolicy, RSAKey

# create logger
module_logger = logging.getLogger('icad_tone_detector.sftp')


def sftp_upload_to_path(icad_config_data, local_file):
    module_logger.icad_info("Uploading " + local_file + " to " + icad_config_data["sftp_settings"]["sftp_hostname"])
    ssh = SSHClient()
    ssh.load_system_host_keys()
    if icad_config_data["sftp_settings"]["private_key"] != "":
        private_key = RSAKey.from_private_key_file(icad_config_data["sftp_settings"]["private_key"])
        ssh.connect(icad_config_data["sftp_settings"]["sftp_hostname"],
                    port=icad_config_data["sftp_settings"]["sftp_port"],
                    username=icad_config_data["sftp_settings"]["sftp_username"], look_for_keys=False, allow_agent=False,
                    pkey=private_key)
    else:
        ssh.connect(icad_config_data["sftp_settings"]["sftp_hostname"],
                    port=icad_config_data["sftp_settings"]["sftp_port"],
                    username=icad_config_data["sftp_settings"]["sftp_username"],
                    password=icad_config_data["sftp_settings"]["sftp_password"], look_for_keys=False, allow_agent=False)

    sftp = ssh.open_sftp()
    sftp.put(local_file, icad_config_data["sftp_settings"]["remote_path"] + local_file.split("/")[-1])
    ssh.close()


def sftp_clean_remote_files(icad_config_data):
    ssh = SSHClient()
    ssh.load_system_host_keys()
    if icad_config_data["sftp_settings"]["private_key"] != "":
        private_key = RSAKey.from_private_key_file(icad_config_data["sftp_settings"]["private_key"])
        ssh.connect(icad_config_data["sftp_settings"]["sftp_hostname"],
                    port=icad_config_data["sftp_settings"]["sftp_port"],
                    username=icad_config_data["sftp_settings"]["sftp_username"], look_for_keys=False, allow_agent=False,
                    pkey=private_key)
    else:
        ssh.connect(icad_config_data["sftp_settings"]["sftp_hostname"],
                    port=icad_config_data["sftp_settings"]["sftp_port"],
                    username=icad_config_data["sftp_settings"]["sftp_username"],
                    password=icad_config_data["sftp_settings"]["sftp_password"], look_for_keys=False, allow_agent=False)

    command = "find " + icad_config_data["sftp_settings"]["remote_path"] + "* -mtime +" + str(
        icad_config_data["cleanup_settings"]["remote_cleanup_days"]) + " -exec rm {} \;"
    stdin, stdout, stderr = ssh.exec_command(command)
    for line in stdout:
        module_logger.debug(Fore.YELLOW + str(line) + Style.RESET_ALL)
    module_logger.debug(Fore.YELLOW + "Cleaned Remote Files" + Style.RESET_ALL)
    ssh.close()
