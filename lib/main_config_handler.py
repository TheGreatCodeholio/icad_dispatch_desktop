import json
import os

default_config = {
    "general": {
        "log_debug": 0,
        "headless": 0,
        "base_url": "https://example.com",
        "url_audio_path": "https://example.com/audio/"
    },
    "web_gui": {"ip": "0.0.0.0",
                "port": 9911
                },
    "audio": {
        "trunk_recorder": {
            "enabled": 0,
            "pulse_sink": "dispatch"
        },
        "input_device_index": 99,
        "output_device_index": 99
    },
    "detection": {
        "mode": 0,
        "silence_threshold": 54,
        "rounded_detection": 0,
        "rounded_detection_range": 20,
        "find_long_tones": 0,
        "long_tone_range": 20

    },
    "recording": {
        "enabled": 1,
        "path": "audio/",
        "max_length": 120.0,
        "min_length": 15.0,
        "start_delay": 2.5,
        "silence_release": 5.0
    },
    "alerting": {
        "exclude_times": {}
    },
    "email": {
        "pre_record_enabled": 0,
        "post_record_enabled": 0,
        "send_as_single_email": 0,
        "smtp_hostname": "mail.example.com",
        "smtp_port": 465,
        "smtp_username": "dispatch@example.com",
        "smtp_password": "CE3QsT2biDfruQM",
        "email_address_from": "dispatch@example.com",
        "email_text_from": "iCAD Example County",
        "pre_record_subject": "Dispatch Alert - %detector_name%",
        "pre_record_body": "%detector_name% Alert at %timestamp%<br><br>",
        "post_record_subject": "Dispatch Alert - %detector_name%",
        "post_record_body": "%detector_name% Alert at %timestamp%<br><br> %mp3_url%"
    },
    "mqtt": {
        "enabled": 0,
        "mqtt_hostname": "192.168.1.88",
        "mqtt_port": 1883,
        "mqtt_username": "testing",
        "mqtt_password": "Testing3"
    },
    "mp3_settings": {
        "bitrate": 32,
        "fix_clipping": {
            "enabled": 0
        },
        "noise_filter": {
            "enabled": 0,
            "model": 0
        },
        "remove_silence": {
            "enabled": 0,
            "min_silence_length": 3.0,
            "silence_threshold": -35
        },
        "remove_tones": {
            "enabled": 0,
            "min_silence_length": 950,
            "silence_threshold": -37
        },
        "high_pass_filter": {
            "enabled": 0,
            "cutoff_freq": 200
        },
        "low_pass_filter": {
            "enabled": 0,
            "cutoff_freq": 3000
        },
        "gain_filter": {
            "enabled": 0,
            "gain_db": 3
        },
        "convert_to_stereo": {
            "enabled": 0
        },
        "append_text_to_speech": {
            "enabled": 0,
            "speech_rate": 125
        },
        "append_audio_file": {
            "enabled": 0
        }
    },
    "sftp_settings": {
        "enabled": 0,
        "sftp_hostname": "",
        "sftp_port": 22,
        "sftp_username": "",
        "sftp_password": "",
        "remote_path": "/var/www/bcfirewire.com/audio/",
        "private_key": "/home/user/.ssh/id_rsa"
    },
    "ftp_settings": {
        "ftp_enabled": 0,
        "ftp_hostname": "ftp.example.com",
        "ftp_port": 21,
        "ftp_username": "ftpuser",
        "ftp_password": "ftppassword",
        "remote_path": "/remote/directory/"
    },
    "mysql_settings": {
        "enabled": 0,
        "mysql_hostname": "192.168.1.107",
        "mysql_port": 3306,
        "mysql_username": "icad",
        "mysql_password": "password",
        "mysql_database": "icad_web",
        "mysql_table_prefix": ""
    },
    "redis_settings": {
        "enabled": 0,
        "redis_hostname": "192.168.1.107",
        "redis_port": 6379,
        "redis_password": "",
        "redis_key": "icad_incidents"
    },
    "rabbitmq_settings": {
        "hostname": "localhost",
        "port": 5672,
        "username": "tone_detect",
        "password": "rabbit_mq_password",
        "vhost": "/",
        "tone_detection_queue": "tone_detect"
    },
    "pushover_settings": {
        "enabled": 0,
        "all_detector_group": 0,
        "all_detector_group_token": "secretgrouptokengoeshere",
        "all_detector_app_token": "secretapptokengoeshere",
        "message_html_string": "<font color=\"red\"><b>%detector_name%</b></font><br><br><a href=\"%mp3_url%\">Click for Dispatch Audio</a>",
        "subject": "Alert!",
        "sound": "pushover",
    },
    "zello_settings": {
        "enabled": 0,
        "call_wait_time": 70,
        "username": "",
        "password": "",
        "channel": "",
        "issuer": "",
        "private_key": ""
    },
    "telegram_settings": {
        "enabled": 0,
        "call_wait_time": 70.0,
        "telegram_bot_token": "12345-12345-12345-12345",
        "telegram_channel_ids": [-9999, 8899]
    },
    "facebook_settings": {
        "enabled": 0,
        "call_wait_time": 70.0,
        "facebook_app_token_page": "",
        "facebook_page_id": 0
    },
    "cleanup_settings": {
        "local_enabled": 0,
        "local_cleanup_days": 7,
        "remote_enabled": 0,
        "remote_cleanup_days": 7
    }
}

default_detectors = {"Test Department": {"detector_id": 1,
                                         "station_number": 12,
                                         "a_tone": 2688.0,
                                         "b_tone": 1598.0,
                                         "a_tone_length": 0.6,
                                         "b_tone_length": 2.0,
                                         "tone_tolerance": 0.01,
                                         "ignore_time": 120.0,
                                         "pre_record_emails": [],
                                         "post_record_emails": [],
                                         "mqtt_topic": "dispatch/test_department",
                                         "mqtt_start_message": "ON",
                                         "mqtt_stop_message": "OFF",
                                         "mqtt_message_interval": 5.0,
                                         "pre_record_email_subject": "Dispatch Alert - %detector_name%",
                                         "pre_record_email_body": "%detector_name% Alert at %timestamp%<br><br>",
                                         "post_record_email_subject": "Dispatch Alert - %detector_name%",
                                         "post_record_email_body": "%detector_name% Alert at %timestamp%<br><br>",
                                         "pushover_subject": "Alert!",
                                         "pushover_body": "<font color=\"red\"><b>%detector_name%</b></font><br><br><a href=\"%mp3_url%\">Click for Dispatch Audio</a>",
                                         "pushover_sound": "pager",
                                         "pushover_group_token": "secrettoken",
                                         "pushover_app_token": "secrettoken",
                                         "post_to_facebook": 0,
                                         "twilio_sms_numbers": [],
                                         "mp3_append_file": ""}
                     }


def read_main_config():
    main_config = open('etc/config.json', 'r')
    config_data = json.load(main_config)
    return config_data


def create_main_config():
    if not os.path.exists('etc/'):
        os.mkdir('etc/')
    if not os.path.exists('etc/config.json'):
        with open('etc/config.json', "w+") as outfile:
            outfile.write(json.dumps(default_config, indent=4))
        outfile.close()


def read_tones_config():
    tones_config = open('etc/detectors.json', 'r')
    config_data = json.load(tones_config)
    return config_data


def create_tones_config():
    if not os.path.exists('etc/detectors.json'):
        with open('etc/detectors.json', "w+") as outfile:
            outfile.write(json.dumps(default_detectors, indent=4))
        outfile.close()
