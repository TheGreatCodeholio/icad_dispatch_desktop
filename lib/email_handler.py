import logging
import smtplib, ssl
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr


module_logger = logging.getLogger('icad_tone_detector.email')


def send_email(icad_config, detector_data, detector_name, mp3_file_name, recipient_list, status):
    """
    Send an email with support for HTML and plain text content using SMTP.

    Parameters:
        icad_config (dict): Configuration dictionary for email settings.
        detector_data (dict): Data specific to the detector.
        detector_name (str): Name of the detector.
        mp3_file_name (str or None): Path to the MP3 file to include in the email body.
        recipient_list (list): List of email recipients.
        status (bool): Indicates whether the email is pre-record or post-record.

    Raises:
        ValueError: If an unsupported SMTP port is provided.
        smtplib.SMTPException: If there is an error during email transmission.
    """
    message = MIMEMultipart("alternative")

    # Generate timestamp for email content
    timestamp = datetime.fromtimestamp(time.time())
    hr_timestamp = f'{timestamp.strftime("%H:%M %b %d %Y")}'

    # Generate MP3 URL if file is provided
    mp3_url = (
        icad_config["general"]["url_audio_path"] + mp3_file_name.split("/")[-1].replace(".wav", ".mp3")
        if mp3_file_name
        else ""
    )

    # Set sender details
    message['From'] = formataddr(
        (str(Header(icad_config["email"]["email_text_from"], 'utf-8')), icad_config["email"]["email_address_from"])
    )

    # Set recipient details
    if len(recipient_list) == 1:
        message["To"] = recipient_list[0]
        to_recipient = recipient_list[0]
        bcc_recipient = ""
    elif len(recipient_list) >= 2:
        message["To"] = recipient_list[0]
        to_recipient = recipient_list[0]
        bcc_recipient_list = recipient_list[1:]
        message["Bcc"] = ', '.join(bcc_recipient_list)
        bcc_recipient = ', '.join(bcc_recipient_list)
    else:
        module_logger.error("Recipient list is empty. Cannot send email.")
        return

    # Determine email subject and body based on status
    if status:
        subject = detector_data.get("post_record_email_subject", icad_config["email"]["post_record_subject"])
        email_body = detector_data.get("post_record_email_body", icad_config["email"]["post_record_body"])
    else:
        subject = detector_data.get("pre_record_email_subject", icad_config["email"]["pre_record_subject"])
        email_body = detector_data.get("pre_record_email_body", icad_config["email"]["pre_record_body"])

    # Replace placeholders in subject and body
    subject = subject.replace("%detector_name%", detector_name).replace("%timestamp%", hr_timestamp).replace(
        "%mp3_url%", mp3_url)
    email_body = email_body.replace("%detector_name%", detector_name).replace("%timestamp%", hr_timestamp).replace(
        "%mp3_url%", mp3_url)

    # Attach plain text and HTML versions of the email body
    plain_text = email_body

    html_content = email_body

    message["Subject"] = subject
    message.attach(MIMEText(plain_text, "plain"))
    message.attach(MIMEText(html_content, "html"))

    # Prepare recipient addresses
    toaddrs = f"{to_recipient}, {bcc_recipient}" if bcc_recipient else to_recipient

    # Establish secure connection and send email
    context = ssl.create_default_context()
    try:
        smtp_host = icad_config["email"]["smtp_hostname"]
        smtp_port = icad_config["email"]["smtp_port"]

        if smtp_port == 465:
            # Use SSL
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
                server.login(icad_config["email"]["smtp_username"], icad_config["email"]["smtp_password"])
                server.sendmail(icad_config["email"]["smtp_username"], toaddrs.split(', '), message.as_string())
        elif smtp_port == 587:
            # Use TLS
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls(context=context)
                server.login(icad_config["email"]["smtp_username"], icad_config["email"]["smtp_password"])
                server.sendmail(icad_config["email"]["smtp_username"], toaddrs.split(', '), message.as_string())
        else:
            raise ValueError(f"Unsupported SMTP port {smtp_port}. Use 465 for SSL or 587 for TLS.")

    except smtplib.SMTPException as e:
        module_logger.error(f"Failed to send email: {e}")
        raise