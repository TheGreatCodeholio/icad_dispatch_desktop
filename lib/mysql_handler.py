# Python Core
import datetime
import logging

# Python 3rd Party
from colorama import Fore, Style
import mysql.connector as mysql

# create logger
module_logger = logging.getLogger('icad_tone_detector.mysql')


class Database:
    def __init__(self, icad_config_data):
        self.logger = logging.getLogger('icad_tone_detector.mysql.Database')
        self.table_prefix = icad_config_data["mysql_settings"]["mysql_table_prefix"]
        self.connection = mysql.connect(
            host=icad_config_data["mysql_settings"]["mysql_hostname"],
            user=icad_config_data["mysql_settings"]["mysql_username"],
            password=icad_config_data["mysql_settings"]["mysql_password"],
            database=icad_config_data["mysql_settings"]["mysql_database"],
            auth_plugin='mysql_native_password'
        )
        self.cursor = self.connection.cursor(dictionary=True)

    def add_new_call(self, timestamp, detector_name, detector_data, mp3_url):
        self.logger.debug(Fore.YELLOW + "Adding Detection to Database" + Style.RESET_ALL)
        timestamp_formatted = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        query = f'INSERT INTO {self.table_prefix}incidents (station_number, station_name, audio_url, incident_time) VALUES (%s, %s, %s, %s)'
        self.cursor.execute(query, (detector_data["station_number"], detector_name, mp3_url, timestamp_formatted))
        self.connection.commit()
        self.cursor.close()
        self.connection.close()

    def update_transcribe_text(self, call_mp3_url, transcript):
        self.logger.debug(Fore.YELLOW + "Updating Transcription in Database" + Style.RESET_ALL)
        query = f'UPDATE {self.table_prefix}incidents set transcription = %s WHERE audio_url = %s'
        values = (transcript, call_mp3_url)
        self.cursor.execute(query, values)
        self.connection.commit()
        self.cursor.close()
        self.connection.close()

    def update_facebook_post(self, facebook_post_id, facebook_text, call_mp3_url):
        self.logger.debug(Fore.YELLOW + "Updating Facebook Post in Database" + Style.RESET_ALL)
        query = f'UPDATE {self.table_prefix}incidents set facebook_post_id = %s, facebook_post_text = %s WHERE audio_url = %s'
        values = (facebook_post_id, facebook_text, call_mp3_url)
        self.cursor.execute(query, values)
        self.connection.commit()
        self.cursor.close()
        self.connection.close()

    def update_facebook_comment(self, facebook_comment_id, call_mp3_url):
        self.logger.debug(Fore.YELLOW + "Updating Transcription Comment in Database" + Style.RESET_ALL)
        query = f'UPDATE {self.table_prefix}incidents set transcription_comment_id = %s WHERE audio_url = %s'
        values = (facebook_comment_id, call_mp3_url)
        self.cursor.execute(query, values)
        self.connection.commit()
        self.cursor.close()
        self.connection.close()

    def get_call_info(self, call_mp3_url):
        self.logger.debug(Fore.YELLOW + "Getting Detection Info" + Style.RESET_ALL)
        query = f"SELECT * from {self.table_prefix}incidents WHERE audio_url = %s"
        values = (call_mp3_url,)
        self.cursor.execute(query, values)
        data = self.cursor.fetchall()
        self.cursor.close()
        self.connection.close()
        if data:
            return data
        else:
            return False

    def check_for_table(self, table_name):
        self.logger.debug(Fore.YELLOW + "Checking for table icad_detections on database." + Style.RESET_ALL)
        query = f"SHOW TABLES LIKE '%{self.table_prefix}{table_name}%'"
        self.cursor.execute(query)
        result = self.cursor.fetchone()
        self.cursor.close()
        self.connection.close()
        if result:
            return True
        else:
            return False

    def create_database_detection_table(self):
        self.logger.debug(Fore.YELLOW + "Creating Database Table icad_detections" + Style.RESET_ALL)
        query_incidents_1 = f"CREATE TABLE {self.table_prefix}incidents (`incident_id` int(11) NOT NULL COMMENT 'Internal MySQL ID',`station_number` int(4) NOT NULL DEFAULT 99 COMMENT 'Number of Station being being called to the incident.', `station_name` varchar(255) NOT NULL DEFAULT 'Unknown' COMMENT 'Name of the station paged to the incident.', `audio_url` varchar(512) NOT NULL DEFAULT 'Unknown' COMMENT 'URL to audio file of dispatch. ', `incident_time` timestamp NOT NULL DEFAULT current_timestamp() COMMENT 'Time incident was paged.', `facebook_post_id` varchar(255) DEFAULT '0' COMMENT 'ID of the Facebook post made by tone detection', `location_latitude` decimal(10,6) NOT NULL DEFAULT 0.000000 COMMENT 'Incident location latitude', `location_longitude` decimal(10,6) NOT NULL DEFAULT 0.000000 COMMENT 'Incident Location longitude', `incident_type` int(2) NOT NULL DEFAULT 0 COMMENT 'Type of incident.', `description` text NOT NULL DEFAULT 'Unknown' COMMENT 'Short description of incident.', `facebook_post_text` longtext DEFAULT 'Unknown' COMMENT 'Text posted to Facebook', `mutual_aid` int(1) NOT NULL DEFAULT 0 COMMENT 'Was this a call for mutual aid?\r\n0 No\r\n1 Yes', `active` int(1) NOT NULL DEFAULT 0 COMMENT 'Is incident ongoing?\r\n0 No\r\n1 Yes', `reviewed` int(1) NOT NULL DEFAULT 0 COMMENT 'Incident reviewed in iCAD admin\r\n0 No\r\n1 Yes', `transcription` text DEFAULT 'Unknown' COMMENT 'Transcription of the dispatch from the incident.', `transcription_comment_id` varchar(255) NOT NULL DEFAULT '0' COMMENT 'Facebook Comment ID for Transcription Comment')"
        query_incidents_2 = f"ALTER TABLE {self.table_prefix}incidents ADD PRIMARY KEY (`incident_id`), ADD UNIQUE KEY `call_id` (`incident_id`), ADD KEY `call_time` (`incident_time`);"
        query_incidents_3 = f"ALTER TABLE {self.table_prefix}incidents MODIFY `incident_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Internal MySQL ID';"
        query_posts_1 = f"CREATE TABLE {self.table_prefix}posts ( `post_id` int(11) NOT NULL, `post_title` varchar(255) NOT NULL, `post_content` text NOT NULL, `post_time` timestamp NOT NULL DEFAULT current_timestamp())"
        query_posts_2 = f"ALTER TABLE {self.table_prefix}posts ADD PRIMARY KEY (`post_id`);"
        query_posts_3 = f"ALTER TABLE {self.table_prefix}posts MODIFY `post_id` int(11) NOT NULL AUTO_INCREMENT;"
        query_stations_1 = f"CREATE TABLE {self.table_prefix}stations ( `station_id` int(11) NOT NULL COMMENT 'Internal MySQL ID', `station_name` varchar(255) NOT NULL COMMENT 'Fire Department Name', `station_image` varchar(512) NOT NULL DEFAULT '/img/fd_cover/default.jpg' COMMENT 'Header image for department page\r\n', `station_pushover` varchar(512) NOT NULL DEFAULT '0' COMMENT 'Pushover Subscription Link', `station_region` int(11) NOT NULL COMMENT 'Fire Department Region\r\n0 None\r\n1 Central\r\n2 North\r\n3 East\r\n4 West\r\n5 South\r\n', `station_address` varchar(255) NOT NULL COMMENT 'Department Mailing Address', `station_phone` varchar(255) NOT NULL COMMENT 'Department Non Emergency Phone', `station_email` varchar(255) NOT NULL COMMENT 'Department Email Contact', `station_facebook` varchar(255) NOT NULL COMMENT 'Department Facebook Page/Group', `station_officers` longtext NOT NULL COMMENT 'Fire Department Officers (JSON)', `station_apparatus` longtext NOT NULL COMMENT 'Fire Department Apparatus (JSON)', `station_number` int(11) NOT NULL COMMENT 'Fire Department Number', `station_type` tinyint(1) NOT NULL DEFAULT 1 COMMENT 'Station Type: 0 None 1 Fire Station 2 EMS Station\r\n')"
        query_stations_2 = f"ALTER TABLE {self.table_prefix}stations ADD PRIMARY KEY (`station_id`);"
        query_stations_3 = f"ALTER TABLE {self.table_prefix}stations MODIFY `station_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Internal MySQL ID';"
        query_users_1 = f"CREATE TABLE {self.table_prefix}users ( `user_id` int(11) NOT NULL COMMENT 'Interal MySQL User ID', `user_email` varchar(255) NOT NULL COMMENT 'User Email Address', `user_password` varchar(255) NOT NULL COMMENT 'Users Password Hash', `user_name` varchar(255) NOT NULL COMMENT 'Users Username', `active` int(1) NOT NULL DEFAULT 0 COMMENT 'Account active?\r\n0 No\r\n1 Yes', `activation_token` char(32) DEFAULT NULL COMMENT 'Token used for activation link.', `account_level` int(1) NOT NULL DEFAULT 2 COMMENT 'Account Level\r\n0 None\r\n1 Admin\r\n2 User', `facebook_subscription` int(1) NOT NULL DEFAULT 0 COMMENT 'Facebook Subscription Status\r\n0 Unsubscribed\r\n1 Subscribed')"
        query_users_2 = f"ALTER TABLE {self.table_prefix}users ADD PRIMARY KEY (`user_id`);"
        query_users_3 = f"ALTER TABLE {self.table_prefix}users MODIFY `user_id` int(11) NOT NULL AUTO_INCREMENT COMMENT 'Interal MySQL User ID';"
        self.cursor.execute(query_incidents_1)
        self.cursor.execute(query_incidents_2)
        self.cursor.execute(query_incidents_3)
        self.cursor.execute(query_posts_1)
        self.cursor.execute(query_posts_2)
        self.cursor.execute(query_posts_3)
        self.cursor.execute(query_stations_1)
        self.cursor.execute(query_stations_2)
        self.cursor.execute(query_stations_3)
        self.cursor.execute(query_users_1)
        self.cursor.execute(query_users_2)
        self.cursor.execute(query_users_3)
        self.connection.commit()
        self.cursor.close()
        self.connection.close()



