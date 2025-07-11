from flask import Flask, jsonify, request
import redis
import pika
import json

app = Flask(__name__)

# Redis client (nome host è quello del servizio docker)
r = redis.Redis(host='redis', port=6379, decode_responses=True)

# Funzione per inviare eventi a RabbitMQ
def publish_event(message):
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host='rabbitmq', port=5672)
        )
        channel = connection.channel()
        channel.queue_declare(queue='queue_updates')
        channel.basic_publish(
            exchange='',
            routing_key='queue_updates',
            body=json.dumps(message)
        )
        connection.close()
    except Exception as e:
        print(f"Errore durante la pubblicazione su RabbitMQ: {e}")

# 🔹 Ritorna le code attive
@app.route('/queues/active', methods=['GET'])
def get_active_queues():
    active_queues = []
    all_keys = r.keys("queue:*:status")
    
    for status_key in all_keys:
        queue_id = status_key.split(":")[1]
        if r.get(status_key) == 'active':
            length = r.llen(f"queue:{queue_id}:tickets")
            active_queues.append({
                "id": queue_id,
                "length": length
            })

    return jsonify(active_queues)

# 🔹 Assegna un nuovo ticket a una coda
@app.route('/queues/<queue_id>/assign', methods=['POST'])
def assign_ticket(queue_id):
    status_key = f"queue:{queue_id}:status"
    if r.get(status_key) != 'active':
        return jsonify({"error": "Queue not active"}), 400

    number_key = f"queue:{queue_id}:last_number"
    ticket_number = r.incr(number_key)
    r.rpush(f"queue:{queue_id}:tickets", ticket_number)

    return jsonify({
        "queue_id": queue_id,
        "ticket_number": ticket_number
    })

# 🔹 Aggiorna stato attivo/inattivo della coda
@app.route('/queues/<queue_id>/status', methods=['POST'])
def update_queue_status(queue_id):
    status = request.json.get("status")
    if status not in ['active', 'inactive']:
        return jsonify({"error": "Stato non valido"}), 400

    r.set(f"queue:{queue_id}:status", status)
    return jsonify({"queue_id": queue_id, "status": status})

# 🔹 Estrae il ticket da servire e lo pubblica su RabbitMQ
@app.route('/queues/<queue_id>/next', methods=['POST'])
def get_next_ticket(queue_id):
    key = f"queue:{queue_id}:tickets"
    if r.llen(key) == 0:
        return jsonify({"error": "Nessun ticket in attesa"}), 404

    ticket_number = r.lpop(key)

    # 📣 Pubblica evento
    publish_event({
        "event": "ticket_called",
        "queue_id": queue_id,
        "ticket_number": ticket_number
    })

    return jsonify({"ticket_number": ticket_number})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5004)