from flask import Flask, render_template
import redis
import threading
import pika
import json

app = Flask(__name__)
r = redis.Redis(host='redis', port=6379, decode_responses=True)

# Stato aggiornato da RabbitMQ
display_data = {}

def listen_to_rabbitmq():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
    channel = connection.channel()
    channel.queue_declare(queue='queue_updates')

    def callback(ch, method, properties, body):
        message = json.loads(body)
        if message.get("event") == "ticket_called":
            queue_id = message["queue_id"]
            ticket_number = message["ticket_number"]
            display_data[queue_id] = {
                "current": ticket_number
            }

    channel.basic_consume(queue='queue_updates', on_message_callback=callback, auto_ack=True)
    channel.start_consuming()

@app.route('/')
def index():
    queues = []

    # Ottieni tutte le code attive
    keys = r.keys("queue:*:status")
    for status_key in keys:
        queue_id = status_key.split(":")[1]
        if r.get(status_key) == "active":
            current = display_data.get(queue_id, {}).get("current", "N/D")
            in_attesa = r.lrange(f"queue:{queue_id}:tickets", 0, -1)
            queues.append({
                "id": queue_id,
                "current": current,
                "waiting": in_attesa
            })

    return render_template("index.html", queues=queues)

if __name__ == '__main__':
    # Thread secondario che ascolta RabbitMQ
    t = threading.Thread(target=listen_to_rabbitmq)
    t.daemon = True
    t.start()

    app.run(host='0.0.0.0', port=5003)