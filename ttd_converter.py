import configparser
import io
import json
import os
import re
import traceback

config_path = "tones.cfg"
output_file = "output.json"

detector_template = {"detector_id": 0, "station_number": 0, "a_tone": 0, "b_tone": 0,
                     "a_tone_length": 0.6, "b_tone_length": 1,
                     "tone_tolerance": 1, "ignore_time": 60, "pre_record_emails": [],
                     "pre_record_email_subject": "", "pre_record_email_body": "",
                     "post_record_emails": [], "post_record_email_subject": "", "post_record_email_body": "",
                     "mqtt_topic": "", "mqtt_start_message": "ON",
                     "mqtt_stop_message": "OFF", "mqtt_message_interval": 5, "pushover_group_token": "",
                     "pushover_app_token": "", "pushover_subject": "", "pushover_body": "",
                     "pushover_sound": "", "post_to_facebook": 0, "mp3_append_file": "", "detector_number": 0}

def load_config_from_file(file_path):
    """
    Load a configuration file from the local file system.

    Args:
        file_path (str): The path to the configuration file.

    Returns:
        configparser.ConfigParser: A ConfigParser object with the configuration loaded.
    """
    # Check if the file exists
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        raise FileNotFoundError(f"The file at {file_path} does not exist.")

    try:
        # Read the file data into a string
        with open(file_path, 'r', encoding='utf-8') as file:
            ttd_cfg_data = file.read()

        # Use an io.StringIO object to mimic a file
        ttd_cfg_object = io.StringIO(ttd_cfg_data)

        # Create a ConfigParser object
        ttd_config = configparser.ConfigParser()
        ttd_config.read_file(ttd_cfg_object)

        return ttd_config

    except Exception as e:
        print(f"Error loading configuration file: {e}")
        raise


def extract_emails(email_string):
    """
    Extracts email addresses from a given string.

    :param email_string: A string containing email addresses in various formats.
    :return: A list of extracted email addresses.
    """
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return re.findall(email_pattern, email_string)

def convert_ttd_config(ttd_config):
    # Process INI -> detector.json
    detector_data = {}

    # Assuming detector_template is defined elsewhere
    new_detector_template = detector_template.copy()

    # Generate a list of possible detector IDs
    detector_id_all = list(range(1, 200))

    count = 0
    for section in ttd_config.sections():
        print(f"Processing section: {section}")
        try:
            # Use the 'description' field as the unique key in detector_data
            description = ttd_config[section].get("description")
            if not description:
                print(f"Skipping section {section}: Missing description")
                continue

            if description not in detector_data:
                # Create a new detector entry
                detector_data[description] = new_detector_template.copy()
                detector_id = detector_id_all.pop(0)  # Assign the next available detector ID
                detector_data[description]["detector_id"] = detector_id

                # Add tone data
                if "atone" in ttd_config[section]:
                    detector_data[description]["a_tone"] = float(ttd_config[section]["atone"])
                    detector_data[description]["b_tone"] = float(ttd_config[section].get("btone", 0))
                elif "longtone" in ttd_config[section]:
                    print(f"Longtone Found")
                    detector_data[description]["a_tone"] = float(ttd_config[section]["longtone"])
                else:
                    # Remove incomplete detector and continue
                    del detector_data[description]
                    print(f"Skipping section {section}: Missing tone data")
                    continue

                # Add tone tolerance or use default
                detector_data[description]["tone_tolerance"] = float(
                    ttd_config[section].get("tone_tolerance", 0.02)
                )

                # Parse emails
                if "text_emails" in ttd_config[section]:
                    detector_data[description]["pre_record_emails"] = extract_emails(ttd_config[section]["text_emails"])
                if "mp3_emails" in ttd_config[section]:
                    detector_data[description]["post_record_emails"] = extract_emails(ttd_config[section]["mp3_emails"])

                count += 1
            else:
                print(f"Skipping {description}: Already in detectors")
        except ValueError as ve:
            print(f"Value error encountered while processing section {section}: {ve}")
        except KeyError as ke:
            print(f"Key error encountered while processing section {section}: {ke}")
        except Exception as e:
            print(f"Unexpected error while processing section {section}: {e}")
    return detector_data

def save_output_file(detector_data):
    """Creates a configuration file with default data if it doesn't exist."""
    try:
        with open(output_file, "w") as outfile:
            outfile.write(json.dumps(detector_data, indent=4))
        return True
    except Exception as e:
        print(f'Unexpected Exception Saving file {output_file} - {e}')
        return None

# Example usage
if __name__ == "__main__":
      # Replace with the actual file path
    try:
        ttd_config = load_config_from_file(config_path)

        detector_json = convert_ttd_config(ttd_config)
        print("Configuration converted successfully.")

        save_output_file(detector_json)
        print("Configuration saved successfully.")

    except Exception as e:
        traceback.print_exc()
        print(f"Failed to convert configuration: {e}")