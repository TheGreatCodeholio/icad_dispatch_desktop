import json
import os
import sys
import pathlib

import pyaudio
import pygtail
import time
from threading import Thread
import subprocess
from flask import Flask, render_template, request, url_for, flash, redirect, Response
import logging

from lib.main_config_handler import read_main_config
from lib.mysql_handler import Database
from lib.rabbitmq_handler import queue_for_detection

flask_log = logging.getLogger("werkzeug")
flask_log.setLevel(logging.WARNING)

module_logger = logging.getLogger("icad_tone_detector.flask")

base_dir = "."
if hasattr(sys, "_MEIPASS"):
    base_dir = os.path.join(sys._MEIPASS)

app = Flask(__name__, static_url_path="", static_folder=os.path.join(base_dir, "static"),
            template_folder=os.path.join(base_dir, "templates"))

app.config["SESSION_TYPE"] = "filesystem"
app.config["SECRET_KEY"] = "622cb8ab390e0f4db2b5d94c06baf6a62a1e"

tone_config_path = "etc/config.json"
icad_config = "etc/detectors.json"


def get_audio_devices():
    p = pyaudio.PyAudio()
    input_devices = []
    output_devices = []
    input_device_indices = {}
    output_device_indices = {}
    inv_input_device_indices = {}
    inv_output_device_indices = {}

    info = p.get_host_api_info_by_index(0)
    numdevices = info.get("deviceCount")
    for i in range(0, numdevices):
        if (p.get_device_info_by_host_api_device_index(0, i).get("maxInputChannels")) > 0:
            input_devices.append(p.get_device_info_by_host_api_device_index(0, i).get("name"))
            input_device_indices[p.get_device_info_by_host_api_device_index(0, i).get("name")] = i
            inv_input_device_indices = dict((v, k) for k, v in input_device_indices.items())
        if p.get_device_info_by_host_api_device_index(0, i).get("maxOutputChannels") > 0:
            output_devices.append(p.get_device_info_by_host_api_device_index(0, i).get("name"))
            output_device_indices[p.get_device_info_by_host_api_device_index(0, i).get("name")] = i
            inv_output_device_indices = dict((v, k) for k, v in output_device_indices.items())

    return inv_output_device_indices, inv_input_device_indices


def restart_script():
    time.sleep(.5)
    pid = os.getpid()
    current_wd = pathlib.Path().resolve()
    if sys.platform == "linux":
        script_bin = "bin/restart.sh"
        subprocess.run(f'{script_bin} {pid} {current_wd}', shell=True)
    else:
        script_bin = "bin\\restart.bat"
        subprocess.run(f'{script_bin} {pid} {current_wd}', shell=True)


def exit_script():
    time.sleep(.5)
    os._exit(0)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/get_log")
def get_log():
    def generate():
        for line in pygtail.Pygtail("log/icad.log", every_n=1):
            yield "data:" + str(line) + "\n\n"
            time.sleep(0.5)

    return Response(generate(), mimetype="text/event-stream")


@app.route("/get_progress")
def progress():
    def generate():
        x = 0
        while x <= 100:
            yield "data:" + str(x) + "\n\n"
            x = x + 10
            time.sleep(0.5)

    return Response(generate(), mimetype="text/event-stream")


@app.route("/control/", methods=("GET", "POST"))
def control():
    if request.method == "POST":
        if "restart_button" in request.form:
            restart_status = True
        else:
            restart_status = False
        if "exit_button" in request.form:
            exit_status = True
        else:
            exit_status = False

        if restart_status:
            Thread(target=restart_script).start()
            return render_template("index.html")
        elif exit_status:
            Thread(target=exit_script).start()
            return redirect("https://bcfirewire.com/", 302)
        else:
            return render_template("index.html")
    else:
        return render_template("index.html")


@app.route("/api/detect", methods=("POST",))
def detect():
    data = open("etc/config.json", "r")
    icad_config_data = json.load(data)
    if icad_config_data["general"]["input_type"] == 1:
        print("Do Stuff")
    else:
        return Response(status=401)


@app.route("/notification_config/", methods=("GET", "POST"))
def notification_config():
    data = open("etc/config.json", "r")
    icad_config_data = json.load(data)
    telegram_channels_input = ", ".join(map(str, icad_config_data["telegram_settings"]["telegram_channel_ids"]))

    if request.method == "POST":
        print(request.form)
        if request.form["submit"] == "pushover_save":
            try:
                pushover_status = int(request.form["pushover_enable"])
                pushover_all_status = int(request.form["all_detector_enable"])
                pushover_all_token_group = request.form["all_detector_group_token"]
                pushover_all_token_app = request.form["all_detector_app_token"]
                pushover_message = request.form["html_message"]
            except ValueError as e:
                flash("Value Error adjust configuration and try again. " + str(e), "danger")
                return redirect(url_for("notification_config"), code=302)

            icad_config_data["pushover_settings"]["enabled"] = pushover_status
            icad_config_data["pushover_settings"]["all_detector_group"] = pushover_all_status
            icad_config_data["pushover_settings"]["all_detector_group_token"] = pushover_all_token_group
            icad_config_data["pushover_settings"]["all_detector_app_token"] = pushover_all_token_app
            icad_config_data["pushover_settings"]["message_html_string"] = pushover_message
            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved Pushover Configuration. Restarting iCAD.", "success")
            Thread(target=restart_script).start()

        elif request.form["submit"] == "telegram_save":
            try:
                telegram_status = int(request.form["telegram_enable"])
                telegram_call_wait = float(request.form["telegram_call_wait_time"])
                telegram_bot_token = request.form["telegram_bot_token"]
                telegram_channels = request.form["telegram_channels"]
            except ValueError as e:
                flash("Value Error adjust configuration and try again. " + str(e), "danger")
                return redirect(url_for("notification_config"), code=302)

            telegram_channels_list = []

            temp_tg_channels = telegram_channels.split(", ")
            for ch in temp_tg_channels:
                telegram_channels_list.append(int(ch))

            icad_config_data["telegram_settings"]["enabled"] = telegram_status
            icad_config_data["telegram_settings"]["call_wait_time"] = telegram_call_wait
            icad_config_data["telegram_settings"]["telegram_bot_token"] = telegram_bot_token
            icad_config_data["telegram_settings"]["telegram_channel_ids"] = telegram_channels_list

            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved Telegram Configuration. Restarting iCAD.", "success")
            Thread(target=restart_script).start()

        elif request.form["submit"] == "zello_save":
            try:
                zello_status = int(request.form["zello_enable"])
                zello_wait_time = float(request.form["zello_call_wait_time"])
                zello_username = request.form["zello_username"]
                zello_password = request.form["zello_password"]
                zello_channel = request.form["zello_channel"]
                zello_issuer = request.form["zello_issuer"]
                zello_key = request.form["zello_private_key"]
            except ValueError as e:
                flash("Value Error adjust configuration and try again. " + str(e), "danger")
                return redirect(url_for("notification_config"), code=302)

            icad_config_data["zello_settings"]["enabled"] = zello_status
            icad_config_data["zello_settings"]["call_wait_time"] = zello_wait_time
            icad_config_data["zello_settings"]["username"] = zello_username
            icad_config_data["zello_settings"]["password"] = zello_password
            icad_config_data["zello_settings"]["channel"] = zello_channel
            icad_config_data["zello_settings"]["issuer"] = zello_issuer
            icad_config_data["zello_settings"]["private_key"] = zello_key

            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved Zello Configuration. Restarting iCAD.", "success")
            Thread(target=restart_script).start()

        elif request.form["submit"] == "facebook_save":
            try:
                facebook_status = int(request.form["facebook_enable"])
                facebook_call_wait = float(request.form["facebook_call_wait_time"])
                facebook_page_token = request.form["facebook_page_token"]
                facebook_page_id = int(request.form["facebook_page"])
            except ValueError as e:
                flash("Value Error adjust configuration and try again. " + str(e), "danger")
                return redirect(url_for("notification_config"), code=302)

            icad_config_data["facebook_settings"]["enabled"] = facebook_status
            icad_config_data["facebook_settings"]["call_wait_time"] = facebook_call_wait
            icad_config_data["facebook_settings"]["facebook_app_token_page"] = facebook_page_token
            icad_config_data["facebook_settings"]["facebook_page_id"] = facebook_page_id

            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved Facebook Configuration. Restarting iCAD.", "success")
            Thread(target=restart_script).start()

        return redirect(url_for("notification_config"), code=302)

    return render_template("notification_config.html", telegram_channels=telegram_channels_input,
                           icad_config_data=icad_config_data)


@app.route("/mysql_config/", methods=("GET", "POST"))
def mysql_config():
    data = open("etc/config.json", "r")
    icad_config_data = json.load(data)
    if request.method == "POST":
        print(request.form)
        if request.form["submit"] == "save_mysql":
            try:
                mysql_enable = int(request.form["mysql_enable"])
                mysql_hostname = request.form["mysql_hostname"]
                mysql_port = int(request.form["mysql_port"])
                mysql_username = request.form["mysql_username"]
                mysql_password = request.form["mysql_password"]
                mysql_database = request.form["mysql_database"]
                mysql_table_prefix = request.form["mysql_table_prefix"]
            except ValueError as e:
                flash("Value Error adjust configuration and try again. " + str(e), "danger")
                return redirect(url_for("mysql_config"), code=302)

            icad_config_data["mysql_settings"]["enabled"] = mysql_enable
            icad_config_data["mysql_settings"]["mysql_hostname"] = mysql_hostname
            icad_config_data["mysql_settings"]["mysql_port"] = mysql_port
            icad_config_data["mysql_settings"]["mysql_username"] = mysql_username
            icad_config_data["mysql_settings"]["mysql_password"] = mysql_password
            icad_config_data["mysql_settings"]["mysql_database"] = mysql_database
            icad_config_data["mysql_settings"]["mysql_table_prefix"] = mysql_table_prefix

            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved MySQL Configuration. Restarting iCAD.", "success")
            Thread(target=restart_script).start()
        elif request.form["submit"] == "create_mysql":
            result = Database(icad_config_data).check_for_table("incidents")
            if not result:
                Database(icad_config_data).create_database_detection_table()
                flash("Created MySQL Database Tables.", "success")
            else:
                flash("Table Exists, Drop table and try again.", "warning")

        return redirect(url_for("mysql_config"), code=302)

    return render_template("mysql_config.html", icad_config_data=icad_config_data)


@app.route("/rabbitmq_config/", methods=("GET", "POST"))
def rabbitmq_config():
    data = open("etc/config.json", "r")
    icad_config_data = json.load(data)
    if request.method == "POST":
        if request.form["submit"] == "save_rabbitmq":
            try:
                rabbitmq_hostname = request.form["rabbitmq_hostname"]
                rabbitmq_port = int(request.form["rabbitmq_port"])
                rabbitmq_username = request.form["rabbitmq_username"]
                rabbitmq_password = request.form["rabbitmq_password"]
                rabbitmq_queue = request.form["rabbitmq_queue"]
            except ValueError as e:
                flash("Value Error adjust configuration and try again. " + str(e), "danger")
                return redirect(url_for("rabbitmq_config"), code=302)

            icad_config_data["rabbitmq_settings"]["hostname"] = rabbitmq_hostname
            icad_config_data["rabbitmq_settings"]["port"] = rabbitmq_port
            icad_config_data["rabbitmq_settings"]["username"] = rabbitmq_username
            icad_config_data["rabbitmq_settings"]["password"] = rabbitmq_password
            icad_config_data["rabbitmq_settings"]["tone_detection_queue"] = rabbitmq_queue

            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved RabbitmMQ Configuration. Restarting iCAD.", "success")
            Thread(target=restart_script).start()

        return redirect(url_for("rabbitmq_config"), code=302)

    return render_template("rabbitmq_config.html", icad_config_data=icad_config_data)

@app.route("/redis_config/", methods=("GET", "POST"))
def redis_config():
    data = open("etc/config.json", "r")
    icad_config_data = json.load(data)
    if request.method == "POST":
        if request.form["submit"] == "save_redis":
            try:
                redis_status = request.form["redis_status"]
                redis_hostname = request.form["redis_hostname"]
                redis_port = int(request.form["redis_port"])
                redis_password = request.form["redis_password"]
                redis_queue = request.form["redis_queue"]
            except ValueError as e:
                flash("Value Error adjust configuration and try again. " + str(e), "danger")
                return redirect(url_for("redis_config"), code=302)

            icad_config_data["redis_settings"]["enabled"] = redis_status
            icad_config_data["redis_settings"]["redis_hostname"] = redis_hostname
            icad_config_data["redis_settings"]["redis_port"] = redis_port
            icad_config_data["redis_settings"]["redis_password"] = redis_password
            icad_config_data["redis_settings"]["redis_key"] = redis_queue

            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved Redis Configuration. Restarting iCAD.", "success")
            Thread(target=restart_script).start()

        return redirect(url_for("redis_config"), code=302)

    return render_template("redis_config.html", icad_config_data=icad_config_data)

@app.route("/sftp_config/", methods=("GET", "POST"))
def sftp_config():
    data = open("etc/config.json", "r")
    icad_config_data = json.load(data)
    if request.method == "POST":
        print(request.form)
        if request.form["submit"] == "save_sftp":
            try:
                sftp_enable = int(request.form["sftp_enable"])
                sftp_hostname = request.form["sftp_hostname"]
                sftp_port = int(request.form["sftp_port"])
                sftp_username = request.form["sftp_username"]
                sftp_pasword = request.form["sftp_password"]
                sftp_remote_path = request.form["sftp_remote_path"]
                sftp_private_key = request.form["sftp_private_key"]

            except ValueError as e:
                flash("Value Error adjust configuration and try again. " + str(e), "danger")
                return redirect(url_for("sftp_config"), code=302)

            icad_config_data["sftp_settings"]["enabled"] = sftp_enable
            icad_config_data["sftp_settings"]["sftp_hostname"] = sftp_hostname
            icad_config_data["sftp_settings"]["sftp_port"] = sftp_port
            icad_config_data["sftp_settings"]["sftp_username"] = sftp_username
            icad_config_data["sftp_settings"]["sftp_password"] = sftp_pasword
            icad_config_data["sftp_settings"]["remote_path"] = sftp_remote_path
            icad_config_data["sftp_settings"]["private_key"] = sftp_private_key

            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved SFTP Configuration. Restarting iCAD.", "success")
            Thread(target=restart_script).start()
        return redirect(url_for("sftp_config"), code=302)

    return render_template("sftp_config.html", icad_config_data=icad_config_data)

@app.route("/ftp_config/", methods=("GET", "POST"))
def ftp_config():
    data = open("etc/config.json", "r")
    icad_config_data = json.load(data)
    if request.method == "POST":
        print(request.form)
        if request.form["submit"] == "save_ftp":
            try:
                ftp_enable = int(request.form["ftp_enable"])
                ftp_hostname = request.form["ftp_hostname"]
                ftp_port = int(request.form["ftp_port"])
                ftp_username = request.form["ftp_username"]
                ftp_pasword = request.form["ftp_password"]
                ftp_remote_path = request.form["ftp_remote_path"]

            except ValueError as e:
                flash("Value Error adjust configuration and try again. " + str(e), "danger")
                return redirect(url_for("ftp_config"), code=302)

            icad_config_data["ftp_settings"]["enabled"] = ftp_enable
            icad_config_data["ftp_settings"]["sftp_hostname"] = ftp_hostname
            icad_config_data["ftp_settings"]["sftp_port"] = ftp_port
            icad_config_data["ftp_settings"]["sftp_username"] = ftp_username
            icad_config_data["ftp_settings"]["sftp_password"] = ftp_pasword
            icad_config_data["ftp_settings"]["remote_path"] = ftp_remote_path


            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved SFTP Configuration. Restarting iCAD.", "success")
            Thread(target=restart_script).start()
        return redirect(url_for("ftp_config"), code=302)

    return render_template("ftp_config.html", icad_config_data=icad_config_data)

@app.route("/mp3_config/", methods=("GET", "POST"))
def mp3_config():
    data = open("etc/config.json", "r")
    icad_config_data = json.load(data)
    if request.method == "POST":
        print(request.form)
        if request.form["submit"] == "mp3_general":
            try:
                bitrate = int(request.form["bitrate"])
                icad_config_data["mp3_settings"]["bitrate"] = bitrate

            except ValueError as e:
                flash("Value Error adjust configuration and try again. " + str(e), "danger")
                return redirect(url_for("mp3_config"), code=302)

            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved MP3 General Configuration. Restarting iCAD.", "success")
            Thread(target=restart_script).start()
        elif request.form["submit"] == "mp3_clipping":
            try:
                clipping_status = int(request.form["mp3_clipping_status"])
                icad_config_data["mp3_settings"]["fix_clipping"]["enabled"] = clipping_status
            except ValueError as e:
                flash("Value Error adjust configuration and try again. " + str(e), "danger")
                return redirect(url_for("mp3_config"), code=302)

            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved MP3 Clipping Configuration. Restarting iCAD.", "success")
            Thread(target=restart_script).start()
        elif request.form["submit"] == "mp3_noise":
            try:
                noise_status = int(request.form["mp3_noise_filter_status"])
                noise_filter = int(request.form["noise_model"])
                icad_config_data["mp3_settings"]["noise_filter"]["enabled"] = noise_status
                icad_config_data["mp3_settings"]["noise_filter"]["model"] = noise_filter

            except ValueError as e:
                flash("Value Error adjust configuration and try again. " + str(e), "danger")
                return redirect(url_for("mp3_config"), code=302)

            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved MP3 Noise Filter Configuration. Restarting iCAD.", "success")
            Thread(target=restart_script).start()

        elif request.form["submit"] == "mp3_silence":
            try:
                remove_silence_enable = int(request.form["mp3_remove_silence_status"])
                min_silence_length = float(request.form["min_silence_length"])
                silence_threshold = int(request.form["silence_threshold"])

                icad_config_data["mp3_settings"]["remove_silence"]["enabled"] = remove_silence_enable
                icad_config_data["mp3_settings"]["remove_silence"]["min_silence_length"] = min_silence_length
                icad_config_data["mp3_settings"]["remove_silence"]["silence_threshold"] = silence_threshold

            except ValueError as e:
                flash("Value Error adjust configuration and try again. " + str(e), "danger")
                return redirect(url_for("mp3_config"), code=302)

            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved MP3 Remove Silence Configuration. Restarting iCAD.", "success")
            Thread(target=restart_script).start()

        elif request.form["submit"] == "mp3_remove_tones":
            try:
                remove_tones_enable = int(request.form["mp3_remove_tones_status"])
                min_silence_length = float(request.form["remove_tones_min_silence_length"])
                silence_threshold = int(request.form["remove_tones_silence_threshold"])

                icad_config_data["mp3_settings"]["remove_tones"]["enabled"] = remove_tones_enable
                icad_config_data["mp3_settings"]["remove_tones"]["min_silence_length"] = min_silence_length
                icad_config_data["mp3_settings"]["remove_tones"]["silence_threshold"] = silence_threshold

            except ValueError as e:
                flash("Value Error adjust configuration and try again. " + str(e), "danger")
                return redirect(url_for("mp3_config"), code=302)

            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved MP3 Remove Tones Configuration. Restarting iCAD.", "success")
            Thread(target=restart_script).start()

        elif request.form["submit"] == "mp3_text_2_speech":
            try:
                text_to_speech_enable = int(request.form["mp3_text_2_speech_status"])
                text_to_speech_rate = int(request.form["speech_rate"])

                icad_config_data["mp3_settings"]["append_text_to_speech"]["enabled"] = text_to_speech_enable
                icad_config_data["mp3_settings"]["append_text_to_speech"]["speech_rate"] = text_to_speech_rate

            except ValueError as e:
                flash("Value Error adjust configuration and try again. " + str(e), "danger")
                return redirect(url_for("mp3_config"), code=302)

            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved MP3 Text To Speech Configuration. Restarting iCAD.", "success")
            Thread(target=restart_script).start()

        elif request.form["submit"] == "mp3_append_file":
            try:
                mp3_append_file_enable = int(request.form["mp3_append_audio_file_status"])
                icad_config_data["mp3_settings"]["append_audio_file"]["enabled"] = mp3_append_file_enable

            except ValueError as e:
                flash("Value Error adjust configuration and try again. " + str(e), "danger")
                return redirect(url_for("mp3_config"), code=302)

            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved MP3 Append Audio File Configuration. Restarting iCAD.", "success")
            Thread(target=restart_script).start()

        elif request.form["submit"] == "mp3_convert_stereo":
            try:
                mp3_convert_stereo = int(request.form["mp3_convert_stereo_status"])
                icad_config_data["mp3_settings"]["convert_to_stereo"]["enabled"] = mp3_convert_stereo
            except ValueError as e:
                flash("Value Error adjust configuration and try again. " + str(e), "danger")
                return redirect(url_for("mp3_config"), code=302)

            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved MP3 Convert Stereo Configuration. Restarting iCAD.", "success")
            Thread(target=restart_script).start()

        elif request.form["submit"] == "mp3_high_pass":
            try:
                high_pass_enabled = int(request.form["mp3_high_pass_status"])
                high_pass_cutoff = int(request.form["high_cutoff_freq"])

                icad_config_data["mp3_settings"]["high_pass_filter"]["enabled"] = high_pass_enabled
                icad_config_data["mp3_settings"]["high_pass_filter"]["cutoff_freq"] = high_pass_cutoff

            except ValueError as e:
                flash("Value Error adjust configuration and try again. " + str(e), "danger")
                return redirect(url_for("mp3_config"), code=302)

            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved MP3 High Pass Configuration. Restarting iCAD.", "success")
            Thread(target=restart_script).start()

        elif request.form["submit"] == "mp3_low_pass":
            try:
                low_pass_enabled = int(request.form["mp3_low_pass_status"])
                low_pass_cutoff = int(request.form["low_cutoff_freq"])

                icad_config_data["mp3_settings"]["low_pass_filter"]["enabled"] = low_pass_enabled
                icad_config_data["mp3_settings"]["low_pass_filter"]["cutoff_freq"] = low_pass_cutoff

            except ValueError as e:
                flash("Value Error adjust configuration and try again. " + str(e), "danger")
                return redirect(url_for("mp3_config"), code=302)

            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved MP3 Low Pass Configuration. Restarting iCAD.", "success")
            Thread(target=restart_script).start()

        elif request.form["submit"] == "mp3_gain":
            try:
                gain_enabled = int(request.form["mp3_gain_status"])
                gain_db = int(request.form["gain_db"])

                icad_config_data["mp3_settings"]["gain_filter"]["enabled"] = gain_enabled
                icad_config_data["mp3_settings"]["gain_filter"]["gain_db"] = gain_db

            except ValueError as e:
                flash("Value Error adjust configuration and try again. " + str(e), "danger")
                return redirect(url_for("mp3_config"), code=302)

            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved MP3 Gain Configuration. Restarting iCAD.", "success")
            Thread(target=restart_script).start()

        return redirect(url_for("mp3_config"), code=302)

    return render_template("mp3_config.html", icad_config_data=icad_config_data)


@app.route("/email_config/", methods=("GET", "POST"))
def email_config():
    data = open("etc/config.json", "r")
    icad_config_data = json.load(data)
    if request.method == "POST":
        if request.form["submit"] == "save_email":
            print(request.form)
            try:
                pre_record_enabled = int(request.form["pre_email_enable"])
                post_record_enabled = int(request.form["post_email_enable"])
                send_as_single_email = int(request.form["send_as_single_enable"])
                smtp_hostname = request.form["email_hostname"]
                smtp_port = int(request.form["email_port"])
                smtp_username = request.form["email_username"]
                smtp_password = request.form["email_password"]
                email_address_from = request.form["email_address"]
                email_text_from = request.form["email_address_text"]
                pre_record_subject = request.form["pre_record_subject"]
                pre_record_body = request.form["pre_record_body"]
                post_record_subject = request.form["post_record_subject"]
                post_record_body = request.form["post_record_body"]

                icad_config_data["email"]["pre_record_enabled"] = pre_record_enabled
                icad_config_data["email"]["post_record_enabled"] = post_record_enabled
                icad_config_data["email"]["send_as_single_email"] = send_as_single_email
                icad_config_data["email"]["smtp_hostname"] = smtp_hostname
                icad_config_data["email"]["smtp_port"] = smtp_port
                icad_config_data["email"]["smtp_username"] = smtp_username
                icad_config_data["email"]["smtp_password"] = smtp_password
                icad_config_data["email"]["email_address_from"] = email_address_from
                icad_config_data["email"]["email_text_from"] = email_text_from
                icad_config_data["email"]["pre_record_subject"] = pre_record_subject
                icad_config_data["email"]["pre_record_body"] = pre_record_body
                icad_config_data["email"]["post_record_subject"] = post_record_subject
                icad_config_data["email"]["post_record_body"] = post_record_body

            except ValueError as e:
                flash("Value Error adjust configuration and try again. " + str(e), "danger")
                return redirect(url_for("email_config"), code=302)

            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved Email Configuration. Restarting iCAD.", "success")
            Thread(target=restart_script).start()

        return redirect(url_for("email_config"), code=302)

    return render_template("email_config.html", icad_config_data=icad_config_data)


@app.route("/mqtt_config/", methods=("GET", "POST"))
def mqtt_config():
    data = open("etc/config.json", "r")
    icad_config_data = json.load(data)
    if request.method == "POST":

        if request.form["submit"] == "save_mqtt":
            mqtt_enable = request.form["mqtt_enable"]
            mqtt_hostname = request.form["mqtt_hostname"]
            mqtt_port = request.form["mqtt_port"]
            mqtt_username = request.form["mqtt_username"]
            mqtt_password = request.form["mqtt_password"]

            if int(mqtt_enable) == 1:
                if not mqtt_hostname or not mqtt_username or not mqtt_password or not mqtt_port:
                    flash("All required fields not filled.", "danger")
                    return redirect(url_for("mqtt_config"), code=302)
                try:
                    icad_config_data["mqtt"]["enabled"] = int(mqtt_enable)
                    icad_config_data["mqtt"]["mqtt_hostname"] = str(mqtt_hostname)
                    icad_config_data["mqtt"]["mqtt_port"] = int(mqtt_port)
                    icad_config_data["mqtt"]["mqtt_username"] = str(mqtt_username)
                    icad_config_data["mqtt"]["mqtt_password"] = str(mqtt_password)
                except ValueError as e:
                    flash("Value Error adjust configuration and try again. " + str(e), "danger")
                    return redirect(url_for("mqtt_config"), code=302)

                with open("etc/config.json", "w") as outfile:
                    outfile.write(json.dumps(icad_config_data, indent=4))
                outfile.close()
                flash("Saved MQTT Configuration. Restarting iCAD.", "success")
                Thread(target=restart_script).start()
            else:
                try:
                    icad_config_data["mqtt"]["enabled"] = int(mqtt_enable)
                except ValueError as e:
                    flash("Value Error adjust configuration and try again. " + str(e), "danger")
                    return redirect(url_for("mqtt_config"), code=302)

                with open("etc/config.json", "w") as outfile:
                    outfile.write(json.dumps(icad_config_data, indent=4))
                outfile.close()
                flash("Saved MQTT Configuration. Restarting iCAD.", "success")
                Thread(target=restart_script).start()

        return redirect(url_for("mqtt_config"), code=302)

    return render_template("mqtt_config.html", icad_config_data=icad_config_data)


@app.route("/detector_config/", methods=("GET", "POST"))
def detector_config():
    data = open("etc/detectors.json", "r")
    detector_config_data = json.load(data)
    icad_detector_template = {"detector_id": 0, "station_number": 0, "a_tone": 0, "b_tone": 0,
                              "a_tone_length": 0.6, "b_tone_length": 1,
                              "tone_tolerance": 0.01, "ignore_time": 60, "pre_record_emails": [],
                              "pre_record_email_subject": "", "pre_record_email_body": "",
                              "post_record_emails": [], "post_record_email_subject": "", "post_record_email_body": "",
                              "mqtt_topic": "", "mqtt_start_message": "ON",
                              "mqtt_stop_message": "OFF", "mqtt_message_interval": 5, "pushover_group_token": "",
                              "pushover_app_token": "", "pushover_subject": "", "pushover_body": "",
                              "pushover_sound": "", "post_to_facebook": 0, "mp3_append_file": ""}

    detector_id_all = list(range(1, 200))
    detector_id_used = []
    for det in detector_config_data:
        if "detector_id" in detector_config_data[det]:
            detector_id_used.append(detector_config_data[det]["detector_id"])
    for det_id in detector_id_used:
        detector_id_all.remove(det_id)
    icad_detector_template["detector_id"] = detector_id_all[0]

    if request.method == "POST":
        if request.form["submit"] == "detector_save":
            detector_id = request.form["detector_id"]
            detector_name = request.form["detector_name"]
            detector_number = request.form["detector_number"]
            detector_tone_a = request.form["detector_tone_a"]
            detector_tone_a_length = request.form["detector_tone_a_length"]
            detector_tone_b = request.form["detector_tone_b"]
            detector_tone_b_length = request.form["detector_tone_b_length"]
            detector_tolerance = request.form["detector_tolerance"]
            detector_ignore_time = request.form["detector_ignore_time"]
            detector_prerecord_emails = request.form["detector_prerecord_emails"]
            detector_prerecord_email_subject = request.form["pre_record_subject"]
            detector_prerecord_email_body = request.form["pre_record_body"]
            detector_postrecord_emails = request.form["detector_postrecord_emails"]
            detector_postrecord_email_subject = request.form["post_record_subject"]
            detector_postrecord_email_body = request.form["post_record_body"]
            detector_mqtt_topic = request.form["detector_mqtt_topic"]
            detector_mqtt_start_message = request.form["detector_mqtt_start_message"]
            detector_mqtt_stop_message = request.form["detector_mqtt_stop_message"]
            detector_mqtt_interval_time = request.form["detector_mqtt_interval_time"]
            detector_pushover_group_token = request.form["detector_pushover_group_token"]
            detector_pushover_app_token = request.form["detector_pushover_app_token"]
            detector_pushover_subject = request.form["detector_pushover_subject"]
            detector_facebook_post = request.form["det_facebook_status"]
            detector_pushover_body = request.form["html_message"]
            detector_pushover_sound = request.form["detector_pushover_sound"]
            detector_mp3_append = request.form["detector_mp3_append"]

            if not detector_id or not detector_name:
                flash("All required fields not filled.", "danger")
                return redirect(url_for("icad_config"), code=302)
            detector_removable = []
            for det in detector_config_data:
                print(det)
                if detector_config_data[det]["detector_id"] == int(detector_id):
                    if det != detector_name:
                        detector_removable.append(det)
            for rem in detector_removable:
                del detector_config_data[rem]
            try:
                detector_config_data[detector_name] = icad_detector_template
                detector_config_data[detector_name]["detector_id"] = int(detector_id)
                detector_config_data[detector_name]["station_number"] = int(detector_number)

                if detector_tone_a == 0:
                    detector_config_data[detector_name]["a_tone"] = 0
                    detector_config_data[detector_name]["a_tone_length"] = 0
                else:
                    detector_config_data[detector_name]["a_tone"] = float(detector_tone_a)
                    detector_config_data[detector_name]["a_tone_length"] = float(detector_tone_a_length)

                if detector_tone_b == 0:
                    detector_config_data[detector_name]["b_tone"] = 0
                    detector_config_data[detector_name]["b_tone_length"] = 0
                else:
                    detector_config_data[detector_name]["b_tone"] = float(detector_tone_b)
                    detector_config_data[detector_name]["b_tone_length"] = float(detector_tone_b_length)

                if not detector_tolerance:
                    detector_config_data[detector_name]["tone_tolerance"] = 0.02
                else:
                    detector_config_data[detector_name]["tone_tolerance"] = float(detector_tolerance)

                if not detector_ignore_time:
                    detector_config_data[detector_name]["ignore_time"] = 60
                else:
                    detector_config_data[detector_name]["ignore_time"] = float(detector_ignore_time)

                pre_record_emails = []
                if len(detector_prerecord_emails) >= 1:
                    temp_pre_emails = detector_prerecord_emails.split(", ")
                    for em in temp_pre_emails:
                        pre_record_emails.append(em)
                post_record_emails = []
                if len(detector_postrecord_emails) >= 1:
                    temp_post_emails = detector_postrecord_emails.split(", ")
                    for em in temp_post_emails:
                        post_record_emails.append(em)

                detector_config_data[detector_name]["pre_record_emails"] = pre_record_emails

                detector_config_data[detector_name]["pre_record_email_subject"] = detector_prerecord_email_subject
                detector_config_data[detector_name]["pre_record_email_body"] = detector_prerecord_email_body

                detector_config_data[detector_name]["post_record_emails"] = post_record_emails
                detector_config_data[detector_name]["post_record_email_subject"] = detector_postrecord_email_subject
                detector_config_data[detector_name]["post_record_email_body"] = detector_postrecord_email_body

                detector_config_data[detector_name]["mqtt_topic"] = detector_mqtt_topic
                detector_config_data[detector_name]["mqtt_start_message"] = detector_mqtt_start_message
                detector_config_data[detector_name]["mqtt_stop_message"] = detector_mqtt_stop_message
                if detector_mqtt_interval_time != "":
                    detector_config_data[detector_name]["mqtt_message_interval"] = float(detector_mqtt_interval_time)
                else:
                    detector_config_data[detector_name]["mqtt_message_interval"] = 0
                detector_config_data[detector_name]["post_to_facebook"] = int(detector_facebook_post)
                detector_config_data[detector_name]["pushover_group_token"] = detector_pushover_group_token
                detector_config_data[detector_name]["pushover_app_token"] = detector_pushover_app_token
                detector_config_data[detector_name]["pushover_subject"] = detector_pushover_subject
                detector_config_data[detector_name]["pushover_body"] = detector_pushover_body
                detector_config_data[detector_name]["pushover_sound"] = detector_pushover_sound

                if sys.platform == "linux":
                    detector_config_data[detector_name]["mp3_append_file"] = detector_mp3_append
                else:
                    detector_config_data[detector_name]["mp3_append_file"] = detector_mp3_append.replace("\\", "\\")

            except ValueError as e:
                flash("Value Error adjust detector configuration and try again: " + str(e), "danger")
                return redirect(url_for("icad_config"), code=302)

            with open("etc/detectors.json", "w") as outfile:
                outfile.write(json.dumps(detector_config_data, indent=4))
            outfile.close()
            flash("Saved Detector: " + str(detector_name) + " restarting iCAD.", "success")
            Thread(target=restart_script).start()

        elif request.form["submit"] == "detector_delete":
            detector_id = request.form["detector_id"]
            detector_name = request.form["detector_name"]
            if detector_name in detector_config_data:
                if detector_config_data[detector_name]["detector_id"] == int(detector_id):
                    del detector_config_data[detector_name]

                    with open("etc/detectors.json", "w") as outfile:
                        outfile.write(json.dumps(detector_config_data, indent=4))
                    outfile.close()
                    flash("Saved Detector: " + str(detector_name) + " restarting iCAD.", "success")
                    Thread(target=restart_script).start()
                else:
                    flash("Detector: " + str(detector_name) + " ID doesn't match.", "danger")
            else:
                flash("Detector: " + str(detector_name) + " not in config.", "danger")

        return redirect(url_for("detector_config"), code=302)

    return render_template("detector_config.html", detector_template=icad_detector_template,
                           detector_config_data=detector_config_data)


@app.route("/icad_config/", methods=("GET", "POST"))
def icad_config():
    data = open("etc/config.json", "r")
    icad_config_data = json.load(data)
    icad_exclusion_template = {"exclude_days": [], "exclude_time_start": "", "exclude_time_end": ""}
    output_devices, input_devices = get_audio_devices()

    if request.method == "POST":
        if request.form["submit"] == "icad_general_config":
            config_log_debug = request.form["config_log_debug"]
            config_headless = request.form["config_headless"]
            config_base_url = request.form["config_base_url"]
            config_url_audio_path = request.form["config_url_audio_path"]
            config_ip = request.form["config_ip"]
            config_port = request.form["config_port"]
            config_input_device_index = request.form["config_input_device_index"]
            config_output_device_index = request.form["config_output_device_index"]
            config_trunk_recorder_enable = request.form["config_trunk_recorder"]
            config_trunk_recorder_pa_sink = request.form["config_trunk_recorder_pa_sink"]
            config_mode = request.form["config_mode"]
            config_rounded_detection = request.form["config_rounded_detection"]
            config_rounded_range = request.form["config_rounded_detection_range"]
            config_find_long_tones = request.form["config_find_long_tones"]
            config_rounded_long_tone_range = request.form["config_rounded_long_tone_range"]
            config_silence_threshold = request.form["config_silence_threshold"]
            config_recording = request.form["config_recording"]
            config_recording_path = request.form["config_recording_path"]
            config_recording_max_length = request.form["config_recording_max_length"]
            config_recording_min_length = request.form["config_recording_min_length"]
            config_recording_start_delay = request.form["config_recording_start_delay"]
            config_recording_silence_release = request.form["config_recording_silence_release"]
            config_local_cleanup_status = request.form["config_local_clean"]
            config_local_cleanup_days = request.form["config_local_clean_days"]
            config_remote_cleanup_status = request.form["config_remote_clean"]
            config_remote_cleanup_days = request.form["config_remote_clean_days"]

            if not config_ip or not config_port or not config_silence_threshold or not config_recording_path or not config_recording_max_length or not config_recording_min_length or not config_recording_start_delay or not config_recording_silence_release or not config_base_url or not config_url_audio_path:
                flash("All fields need filled.", "danger")
                return redirect(url_for("icad_config"), code=302)
            else:
                try:
                    icad_config_data["general"]["log_debug"] = int(config_log_debug)
                    icad_config_data["general"]["headless"] = int(config_headless)
                    icad_config_data["general"]["base_url"] = str(config_base_url)
                    icad_config_data["general"]["url_audio_path"] = str(config_url_audio_path)
                    icad_config_data["web_gui"]["ip"] = str(config_ip)
                    icad_config_data["web_gui"]["port"] = int(config_port)
                    icad_config_data["audio"]["input_device_index"] = int(config_input_device_index)
                    icad_config_data["audio"]["output_device_index"] = int(config_output_device_index)
                    icad_config_data["audio"]["trunk_recorder"]["enabled"] = int(config_trunk_recorder_enable)
                    icad_config_data["audio"]["trunk_recorder"]["pulse_sink"] = config_trunk_recorder_pa_sink
                    icad_config_data["detection"]["mode"] = int(config_mode)
                    icad_config_data["detection"]["rounded_detection"] = int(config_rounded_detection)
                    icad_config_data["detection"]["rounded_detection_range"] = int(config_rounded_range)
                    icad_config_data["detection"]["find_long_tones"] = int(config_find_long_tones)
                    icad_config_data["detection"]["long_tone_range"] = int(config_rounded_long_tone_range)
                    icad_config_data["detection"]["silence_threshold"] = int(config_silence_threshold)
                    icad_config_data["recording"]["enabled"] = int(config_recording)
                    if sys.platform == "linux":
                        icad_config_data["recording"]["path"] = str(config_recording_path)
                    else:
                        icad_config_data["recording"]["path"] = str(config_recording_path).replace("\\", "\\")
                    icad_config_data["recording"]["max_length"] = float(config_recording_max_length)
                    icad_config_data["recording"]["min_length"] = float(config_recording_min_length)
                    icad_config_data["recording"]["start_delay"] = float(config_recording_start_delay)
                    icad_config_data["recording"]["silence_release"] = float(config_recording_silence_release)
                    icad_config_data["cleanup_settings"]["local_enabled"] = int(config_local_cleanup_status)
                    icad_config_data["cleanup_settings"]["local_cleanup_days"] = int(config_local_cleanup_days)
                    icad_config_data["cleanup_settings"]["remote_enabled"] = int(config_remote_cleanup_status)
                    icad_config_data["cleanup_settings"]["remote_cleanup_days"] = int(config_remote_cleanup_days)


                except ValueError as e:
                    flash("Value Error adjust setting and try again: " + str(e), "danger")
                    return redirect(url_for("icad_config"), code=302)

                with open("etc/config.json", "w") as outfile:
                    outfile.write(json.dumps(icad_config_data, indent=4))
                outfile.close()
                flash("Saved configuration restarting iCAD.", "success")
                Thread(target=restart_script).start()
        elif request.form["submit"] == "save_exclude":
            exclude_days = []
            exclude_name = request.form["exclude_name"]
            if "exclude_sunday" in request.form:
                exclude_days.append(0)
            if "exclude_monday" in request.form:
                exclude_days.append(1)
            if "exclude_tuesday" in request.form:
                exclude_days.append(2)
            if "exclude_wednesday" in request.form:
                exclude_days.append(3)
            if "exclude_thursday" in request.form:
                exclude_days.append(4)
            if "exclude_friday" in request.form:
                exclude_days.append(5)
            if "exclude_saturday" in request.form:
                exclude_days.append(6)
            exclude_time_start = request.form["exclude_from"]
            exclude_time_end = request.form["exclude_to"]

            if not exclude_name or not exclude_time_start or not exclude_time_end or len(exclude_days) <= 0:
                flash("All required fields not filled.", "danger")
                return redirect(url_for("icad_config"), code=302)

            icad_config_data["alerting"]["exclude_times"][exclude_name] = icad_exclusion_template
            icad_config_data["alerting"]["exclude_times"][exclude_name]["exclude_days"] = exclude_days
            icad_config_data["alerting"]["exclude_times"][exclude_name]["exclude_time_start"] = exclude_time_start
            icad_config_data["alerting"]["exclude_times"][exclude_name]["exclude_time_end"] = exclude_time_end

            with open("etc/config.json", "w") as outfile:
                outfile.write(json.dumps(icad_config_data, indent=4))
            outfile.close()
            flash("Saved Exclusion: " + str(exclude_name), "success")
            Thread(target=restart_script).start()
        elif request.form["submit"] == "delete_exclude":
            exclude_name = request.form["exclude_name"]
            if not exclude_name:
                flash("Exclude name empty.", "danger")
                return redirect(url_for("icad_config"), code=302)

            if exclude_name in icad_config_data["alerting"]["exclude_times"]:
                del icad_config_data["alerting"]["exclude_times"][exclude_name]
                with open("etc/config.json", "w") as outfile:
                    outfile.write(json.dumps(icad_config_data, indent=4))
                outfile.close()
                flash("Removed Exclusion: " + str(exclude_name), "success")
                Thread(target=restart_script).start()
            else:
                flash("Exclude doesn't exist in config.", "danger")
                return redirect(url_for("icad_config"), code=302)

        return redirect(url_for("icad_config"), code=302)

    return render_template("icad_config.html", input_devices=input_devices, output_devices=output_devices,
                           exclude_template=icad_exclusion_template, icad_config_data=icad_config_data)


@app.route('/process', methods=["POST"])
def process():
    if request.method == 'POST':
        content = request.json
        if content:
            data = open("etc/config.json", "r")
            icad_config_data = json.load(data)
            if icad_config_data["audio"]["trunk_recorder"]["enabled"] == 1:
                queue_for_detection(icad_config_data, content)
                json_status = {"status": "Request has been queued for processing"}
                return json_status, 200
            else:
                json_status = {"status": "Unknown request."}
                return json_status, 200

        else:
            json_status = {"status": "Unknown request."}
            return json_status, 200
    else:
        json_status = {"status": "Not Authorized."}
        return json_status, 403


def init_flask(icad_config):
    Thread(
        target=lambda: app.run(host=icad_config["web_gui"]["ip"], port=icad_config["web_gui"]["port"],
                               debug=False,
                               use_reloader=False)).start()
