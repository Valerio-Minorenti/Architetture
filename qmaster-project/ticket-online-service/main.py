import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit, join_room
import redis
import requests
import uuid
import time
import threading
import pika
import json

app = Flask(__name__, template_folder='templates')
socketio = SocketIO(app, async_mode="eventlet")

r = redis.Redis(host='redis', port=6379, decode_responses=True)
QUEUE_SERVICE_URL = "http://queue-service:5004"

def acquire_lock(lock_name, acquire_timeout=5, lock_timeout=5):
    identifier = str(uuid.uuid4())
    end = time.time() + acquire_timeout
    while time.time() < end:
        if r.set(lock_name, identifier, nx=True, ex=lock_timeout):
            return identifier
        time.sleep(0.01)
    return None

def release_lock(lock_name, identifier):
    if r.get(lock_name) == identifier:
        r.delete(lock_name)

@app.route('/', methods=['GET', 'POST'])
def request_ticket():
    if request.method == 'POST':
        res = requests.get(f"{QUEUE_SERVICE_URL}/queues/active")
        queues = res.json()

        if not queues:
            return "Nessuna coda attiva."

        min_len = min(q['length'] for q in queues)
        best_queues = [q for q in queues if q['length'] == min_len]
        queue = best_queues[0]

        queue_id = queue['id']
        lock = acquire_lock(f"lock:{queue_id}")
        if not lock:
            return "Errore, riprova."

        try:
            res = requests.post(f"{QUEUE_SERVICE_URL}/queues/{queue_id}/assign")
            data = res.json()
        finally:
            release_lock(f"lock:{queue_id}", lock)

        user_token = str(uuid.uuid4())
        r.hset(f"user:{user_token}", mapping={
            "queue_id": data['queue_id'],
            "ticket_number": data['ticket_number']
        })

        return redirect(url_for('ticket_status', token=user_token))

    return render_template("index.html")

@app.route('/status/<token>')
def ticket_status(token):
    user_data = r.hgetall(f"user:{token}")
    if not user_data:
        return "Token non valido."

    queue_id = user_data['queue_id']
    ticket_number = int(user_data['ticket_number'])

    tickets = r.lrange(f"queue:{queue_id}:tickets", 0, -1)
    waiting_before = [int(t) for t in tickets if int(t) < ticket_number]

    notify = None
    if len(waiting_before) <= 3:
        notify = "⚠️ Il tuo turno si avvicina!"
    if ticket_number not in map(int, tickets):
        notify = "✅ È il tuo turno! Presentati allo sportello."

    return render_template("ticket_status.html",
                           queue_id=queue_id,
                           ticket_number=ticket_number,
                           people_before=len(waiting_before),
                           notify=notify,
                           token=token)

@socketio.on('join')
def on_join(token):
    print(f"✅ Utente con token {token} si è unito alla stanza WebSocket.")
    join_room(token)

def listen_to_rabbitmq():
    connection = None
    while not connection:
        try:
            print("⏳ Connessione a RabbitMQ...")
            connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
        except pika.exceptions.AMQPConnectionError:
            print("🔁 RabbitMQ non pronto. Riprovo tra 2s...")
            time.sleep(2)

    channel = connection.channel()
    channel.queue_declare(queue='queue_updates')

    def callback(ch, method, properties, body):
        try:
            data = json.loads(body)
            queue_id = data['queue_id']
            ticket_number = int(data['ticket_number'])

            all_users = r.keys("user:*")
            for user_key in all_users:
                user_data = r.hgetall(user_key)
                if user_data.get("queue_id") == queue_id and int(user_data.get("ticket_number")) == ticket_number:
                    token = user_key.replace("user:", "")
                    print(f"📢 Notifico utente {token}: è il suo turno.")
                    socketio.emit('update', {
                        "event": "ticket_called",
                        "ticket_number": ticket_number,
                        "queue_id": queue_id
                    }, room=token)
                    break
        except Exception as e:
            print(f"❌ Errore nel callback RabbitMQ: {e}")

    channel.basic_consume(queue='queue_updates', on_message_callback=callback, auto_ack=True)
    print("📡 Listener RabbitMQ attivo.")
    channel.start_consuming()

def periodic_status_updates():
    while True:
        time.sleep(3)
        all_users = r.keys("user:*")
        for user_key in all_users:
            token = user_key.replace("user:", "")
            user_data = r.hgetall(user_key)
            if not user_data:
                continue

            queue_id = user_data['queue_id']
            ticket_number = int(user_data['ticket_number'])

            tickets = r.lrange(f"queue:{queue_id}:tickets", 0, -1)
            people_before = len([int(t) for t in tickets if int(t) < ticket_number])

            if ticket_number not in map(int, tickets):
                notify = "✅ È il tuo turno! Presentati allo sportello."
            elif people_before <= 3:
                notify = "⚠️ Il tuo turno si avvicina!"
            else:
                notify = None

            socketio.emit("status_update", {
                "people_before": people_before,
                "notify": notify
            }, room=token)

threading.Thread(target=listen_to_rabbitmq, daemon=True).start()
threading.Thread(target=periodic_status_updates, daemon=True).start()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5005)