import logging
from lib.mp3_handler import add_id_tags, soften_clipping, noise_filter, remove_silence, high_pass_filter, \
    low_pass_filter, convert_wav_mp3, gain_filter, append_audio_file, append_text2speech_audio, remove_tones
from colorama import Fore, Style
module_logger = logging.getLogger('icad_tone_detector.tone_finder_process')


def process_tone_finder_actions(icad_config, freq_name, wav_file_path):
    module_logger.icad_info(Fore.GREEN + "Processing Tone Finder Audio" + Style.RESET_ALL)

    if icad_config["mp3_settings"]["fix_clipping"]["enabled"] == 1:
        module_logger.debug(Fore.YELLOW + "Starting Audio Clipping Softening" + Style.RESET_ALL)
        soften_clipping(wav_file_path)
    else:
        module_logger.debug(Fore.YELLOW + "Audio Clipping Softening Disabled" + Style.RESET_ALL)

    if icad_config["mp3_settings"]["noise_filter"]["enabled"] == 1:
        module_logger.debug(Fore.YELLOW + "Starting Audio Noise Reduction" + Style.RESET_ALL)
        noise_filter(icad_config, wav_file_path)
    else:
        module_logger.debug(Fore.YELLOW + "Audio Noise Reduction Disabled" + Style.RESET_ALL)
    if icad_config["mp3_settings"]["remove_silence"]["enabled"] == 1:
        module_logger.debug(Fore.YELLOW + "Starting Audio Remove Silence" + Style.RESET_ALL)
        remove_silence(icad_config, wav_file_path)
    else:
        module_logger.debug(Fore.YELLOW + "Audio Remove Silence Disabled" + Style.RESET_ALL)

    if icad_config["mp3_settings"]["high_pass_filter"]["enabled"] == 1:
        module_logger.debug(Fore.YELLOW + "Starting High Pass Filter" + Style.RESET_ALL)
        high_pass_filter(icad_config, wav_file_path)
    else:
        module_logger.debug(Fore.YELLOW + "Audio High Pass Filter Disabled" + Style.RESET_ALL)

    if icad_config["mp3_settings"]["low_pass_filter"]["enabled"] == 1:
        module_logger.debug(Fore.YELLOW + "Starting Low Pass Filter" + Style.RESET_ALL)
        low_pass_filter(icad_config, wav_file_path)
    else:
        module_logger.debug(Fore.YELLOW + "Audio Low Pass Filter Disabled" + Style.RESET_ALL)

    if icad_config["mp3_settings"]["gain_filter"]["enabled"] == 1:
        module_logger.debug(Fore.YELLOW + "Starting Gain Filter" + Style.RESET_ALL)
        gain_filter(icad_config, wav_file_path)
    else:
        module_logger.debug(Fore.YELLOW + "Audio Gain Filter Disabled" + Style.RESET_ALL)

    if icad_config["mp3_settings"]["remove_tones"]["enabled"] == 1:
        module_logger.debug(Fore.YELLOW + "Starting Remove Tones File" + Style.RESET_ALL)
        remove_tones(icad_config, wav_file_path)
    else:
        module_logger.debug(Fore.YELLOW + "Audio remove Tones Disabled" + Style.RESET_ALL)

    convert_wav_mp3(icad_config, wav_file_path)

    add_id_tags(icad_config, freq_name, wav_file_path.replace(".wav", ".mp3"))

    module_logger.icad_info(Fore.BLUE + "Finder Alerts Complete." + Style.RESET_ALL)