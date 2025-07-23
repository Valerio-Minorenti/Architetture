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

def emit_all_queues():
    while True:
        time.sleep(3)
        for key in r.keys("queue:*:status"):
            queue_id = key.split(":")[1]
            if r.get(key) != "active":
                continue

            waiting_list = r.lrange(f"queue:{queue_id}:tickets", 0, -1)
            serving = r.get(f"queue:{queue_id}:serving") or display_data.get(queue_id, {}).get("serving", "—")

            display_data.setdefault(queue_id, {
                "serving": serving,
                "waiting_list": []
            })

            display_data[queue_id]["serving"] = serving
            display_data[queue_id]["waiting_list"] = waiting_list

            print(f" Aggiornamento forzato per coda {queue_id}: {waiting_list} | In servizio: {serving}")

            socketio.emit('display_update', {
                "queue_id": queue_id,
                "serving": serving,
                "waiting_list": waiting_list
            })

def listen_to_rabbitmq():
    while True:
        try:
            print(" Connessione a RabbitMQ...")
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host='rabbitmq', port=5672)
            )
            channel = connection.channel()
            channel.queue_declare(queue='queue_updates')

            print(" In ascolto sulla coda 'queue_updates'")

            def callback(ch, method, properties, body):
                data = json.loads(body)
                print(" Evento ricevuto:", data)

                event_type = data.get("event")
                queue_id = data.get("queue_id")
                ticket_number = data.get("ticket_number")

                if event_type == "ticket_called" and queue_id:
                    serving = ticket_number
                    waiting_list = r.lrange(f"queue:{queue_id}:tickets", 0, -1)

                    display_data.setdefault(queue_id, {"serving": "—", "waiting_list": []})
                    display_data[queue_id]["serving"] = serving
                    display_data[queue_id]["waiting_list"] = waiting_list

                    socketio.emit('display_update', {
                        "queue_id": queue_id,
                        "serving": serving,
                        "waiting_list": waiting_list
                    })

                elif event_type == "ticket_assigned" and queue_id:
                    serving = r.get(f"queue:{queue_id}:serving") or "—"
                    waiting_list = r.lrange(f"queue:{queue_id}:tickets", 0, -1)

                    display_data.setdefault(queue_id, {"serving": serving, "waiting_list": []})
                    display_data[queue_id]["waiting_list"] = waiting_list

                    socketio.emit('display_update', {
                        "queue_id": queue_id,
                        "serving": serving,
                        "waiting_list": waiting_list
                    })

                elif event_type == "queue_closed_and_users_distributed":
                    from_queue = data.get("from_queue")
                    to_queues = data.get("to_queues", [])
                    moved_users = data.get("moved_users", [])

                    # Rimuovi la coda chiusa
                    if from_queue in display_data:
                        display_data.pop(from_queue)
                        socketio.emit("queue_closed", {"queue_id": from_queue})
                        print(f" La coda '{from_queue}' è stata chiusa.")

                    # Aggiorna le code di destinazione
                    for qid in to_queues:
                        waiting = r.lrange(f"queue:{qid}:tickets", 0, -1)
                        serving = r.get(f"queue:{qid}:serving") or display_data.get(qid, {}).get("serving", "—")

                        display_data[qid] = {
                            "serving": serving,
                            "waiting_list": waiting
                        }

                        socketio.emit('display_update', {
                            "queue_id": qid,
                            "serving": serving,
                            "waiting_list": waiting
                        })

                    socketio.emit("notification", {
                        "type": "distribution",
                        "from_queue": from_queue,
                        "to_queues": to_queues,
                        "users": moved_users
                    })

                elif event_type == "queue_closed_no_target":
                    from_queue = data.get("from_queue")
                    moved_users = data.get("moved_users", [])

                    if from_queue in display_data:
                        display_data.pop(from_queue)
                        socketio.emit("queue_closed", {"queue_id": from_queue})
                        print(f" Coda '{from_queue}' chiusa ma nessuna destinazione.")

                    socketio.emit("notification", {
                        "type": "no_target",
                        "from_queue": from_queue,
                        "users": moved_users
                    })

            channel.basic_consume(
                queue='queue_updates',
                on_message_callback=callback,
                auto_ack=True
            )

            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError:
            print(" Errore RabbitMQ. Ritento tra 5s...")
            time.sleep(5)

@app.route('/')
def index():
    active_queues = []
    for key in r.keys("queue:*:status"):
        queue_id = key.split(":")[1]
        if r.get(key) == "active":
            serving = r.get(f"queue:{queue_id}:serving") or display_data.get(queue_id, {}).get("serving", "—")
            waiting = display_data.get(queue_id, {}).get("waiting_list", [])
            active_queues.append({
                "id": queue_id,
                "serving": serving,
                "waiting": waiting
            })
    return render_template("index.html", queues=active_queues)

def emit_removed_queues():
    while True:
        time.sleep(3)
        active_ids = {key.split(":")[1] for key in r.keys("queue:*:status") if r.get(key) == "active"}
        known_ids = set(display_data.keys())

        removed_ids = known_ids - active_ids
        for queue_id in removed_ids:
            print(f" Coda {queue_id} è stata chiusa, la rimuovo dal display.")
            display_data.pop(queue_id, None)
            socketio.emit("queue_closed", {"queue_id": queue_id})

if __name__ == '__main__':
    threading.Thread(target=listen_to_rabbitmq, daemon=True).start()
    threading.Thread(target=emit_all_queues, daemon=True).start()
    threading.Thread(target=emit_removed_queues, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5003)