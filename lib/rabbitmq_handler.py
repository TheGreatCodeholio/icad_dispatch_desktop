import json
import pika


def queue_for_detection(config_data, call_json):
    credentials = pika.PlainCredentials(config_data["rabbitmq_settings"]["username"],
                                        config_data["rabbitmq_settings"]["password"])
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=config_data["rabbitmq_settings"]["hostname"],
                                  port=config_data["rabbitmq_settings"]["port"], credentials=credentials))

    channel = connection.channel()

    channel.queue_declare(queue=config_data["rabbitmq_settings"]["tone_detection_queue"], durable=True)

    channel.basic_publish(
        exchange='',
        routing_key=config_data["rabbitmq_settings"]["tone_detection_queue"],
        body=json.dumps(call_json),
        properties=pika.BasicProperties(
            delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE
        ))
    connection.close()
