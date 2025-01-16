import smtplib, ssl
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr



def send_email(icad_config, detector_data, detector_name, mp3_file_name, recipient_list, status):
    message = MIMEMultipart("alternative")

    timestamp = datetime.fromtimestamp(time.time())
    hr_timestamp = f'{timestamp.strftime("%H")}:{timestamp.strftime("%M")} {timestamp.strftime("%b %d %Y")}'
    if not mp3_file_name:
        mp3_url = ""
    else:
        mp3_url = icad_config["general"]["url_audio_path"] + mp3_file_name.split("/")[-1].replace(".wav", ".mp3")

    message['From'] = formataddr(
        (str(Header(icad_config["email"]["email_text_from"], 'utf-8')), icad_config["email"]["email_address_from"]))
    if len(recipient_list) == 1:
        message["To"] = recipient_list[0]
        to_recipient = recipient_list[0]
        bbc_recipient = ""
    elif len(recipient_list) >= 2:
        message["To"] = recipient_list[0]
        to_recipient = recipient_list[0]
        recipient_list.remove(recipient_list[0])
        message["Bcc"] = ', '.join(recipient_list)
        bbc_recipient = ', '.join(recipient_list)
    else:
        return

    if not status:
        if detector_data["pre_record_email_subject"] != "":
            subject = detector_data["pre_record_email_subject"]
        else:
            subject = icad_config["email"]["pre_record_subject"]

        if detector_data["pre_record_email_body"] != "":
            email_body = detector_data["pre_record_email_body"]
        else:
            email_body = icad_config["email"]["pre_record_body"]

    else:
        if detector_data["post_record_email_subject"] != "":
            subject = detector_data["post_record_email_subject"]
        else:
            subject = icad_config["email"]["post_record_subject"]

        if detector_data["post_record_email_body"] != "":
            email_body = detector_data["post_record_email_body"]
        else:
            email_body = icad_config["email"]["post_record_body"]

    message["Subject"] = subject.replace("%detector_name%", detector_name).replace("%timestamp%", hr_timestamp).replace(
        "%mp3_url%", mp3_url)

    email_message = email_body.replace("%detector_name%", detector_name).replace("%timestamp%", hr_timestamp).replace(
        "%mp3_url%", mp3_url)

    body = MIMEText(email_message, "html")
    message.attach(body)
    toaddrs = to_recipient + ", " + bbc_recipient
    context = ssl.create_default_context()
    with smtplib.SMTP(icad_config["email"]["smtp_hostname"], icad_config["email"]["smtp_port"]) as server:
        server.starttls(context=context)
        server.login(icad_config["email"]["smtp_username"], icad_config["email"]["smtp_password"])
        server.sendmail(icad_config["email"]["smtp_username"], toaddrs, message.as_string())
