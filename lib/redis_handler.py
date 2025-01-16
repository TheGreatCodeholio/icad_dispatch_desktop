# Python 3 Core Libraries
import json

# Python 3 Third Party Libraries
import redis


# Python 3 Project Libraries

class RedisCache:
    def __init__(self, icad_config_data):
        self.redis_key = icad_config_data["redis_settings"]["redis_key"]
        self.redis_host = icad_config_data["redis_settings"]["redis_hostname"]
        self.redis_port = icad_config_data["redis_settings"]["redis_port"]
        self.redis_password = icad_config_data["redis_settings"]["redis_password"]

        if self.redis_password != "":
            self.r = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                password=self.redis_password)
        else:
            self.r = redis.Redis(
                host=self.redis_host,
                port=self.redis_port)

    def add_call_to_redis(self, service, call_tone_name, call_data):
        self.r.hset(self.redis_key + "_" + service, call_tone_name, json.dumps(call_data))

    def get_single_call(self, service, call_tone_name):
        call = self.r.hget(self.redis_key + "_" + service, call_tone_name)
        result = json.loads(call)
        if result:
            return result
        else:
            return None

    def get_all_call(self, service):
        result = self.r.hgetall(self.redis_key + "_" + service)
        if result is not None:
            return result
        else:
            return None

    def delete_all_calls(self, service):
        self.r.delete(self.redis_key + "_" + service)


