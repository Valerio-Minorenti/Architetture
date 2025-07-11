import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template
from flask_socketio import SocketIO
import redis
import pika
import json
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app)

r = redis.Redis(host='redis', port=6379, decode_responses=True)

display_data = {}

def listen_to_rabbitmq():
    while True:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host='rabbitmq', port=5672)
            )
            channel = connection.channel()
            channel.queue_declare(queue='queue_updates')

            def callback(ch, method, properties, body):
                data = json.loads(body)
                print("📩 Evento ricevuto:", data)

                queue_id = data.get("queue_id")
                if queue_id:
                    display_data[queue_id] = {
                        "serving": data.get("ticket_number"),
                        "waiting_list": r.lrange(f"queue:{queue_id}:tickets", 0, -1)
                    }

                    # 🔥 Invio aggiornamento via WebSocket
                    socketio.emit('display_update', {
                        "queue_id": queue_id,
                        "serving": display_data[queue_id]["serving"],
                        "waiting_list": display_data[queue_id]["waiting_list"]
                    })

            channel.basic_consume(
                queue='queue_updates',
                on_message_callback=callback,
                auto_ack=True
            )

            print("✅ In ascolto su RabbitMQ...")
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError:
            print("❌ Connessione a RabbitMQ fallita. Ritento tra 5s...")
            time.sleep(5)

@app.route('/')
def index():
    active_queues = []
    for key in r.keys("queue:*:status"):
        queue_id = key.split(":")[1]
        if r.get(key) == "active":
            serving = display_data.get(queue_id, {}).get("serving", "—")
            waiting = display_data.get(queue_id, {}).get("waiting_list", [])
            active_queues.append({
                "id": queue_id,
                "serving": serving,
                "waiting": waiting
            })
    return render_template("index.html", queues=active_queues)

if __name__ == '__main__':
    threading.Thread(target=listen_to_rabbitmq, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5003)