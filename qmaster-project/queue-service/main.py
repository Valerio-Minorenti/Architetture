from flask import Flask, jsonify, request
import redis
import pika
import json

app = Flask(__name__)
r = redis.Redis(host='redis', port=6379, decode_responses=True)

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

@app.route('/queues/active', methods=['GET'])
def get_active_queues():
    active_queues = []
    for status_key in r.keys("queue:*:status"):
        queue_id = status_key.split(":")[1]
        if r.get(status_key) == 'active':
            length = r.llen(f"queue:{queue_id}:tickets")
            active_queues.append({"id": queue_id, "length": length})
    return jsonify(active_queues)

@app.route('/queues/<queue_id>/assign', methods=['POST'])
def assign_ticket(queue_id):
    if r.get(f"queue:{queue_id}:status") != 'active':
        return jsonify({"error": "Queue not active"}), 400

    ticket_number = r.incr(f"queue:{queue_id}:last_number")
    r.rpush(f"queue:{queue_id}:tickets", ticket_number)

    waiting_list = r.lrange(f"queue:{queue_id}:tickets", 0, -1)

    publish_event({
        "event": "ticket_assigned",
        "queue_id": queue_id,
        "ticket_number": int(ticket_number),
        "waiting_list": waiting_list
    })

    return jsonify({
        "queue_id": queue_id,
        "ticket_number": ticket_number
    })

@app.route('/queues/<queue_id>/status', methods=['POST'])
def update_queue_status(queue_id):
    status = request.json.get("status")
    if status not in ['active', 'inactive']:
        return jsonify({"error": "Stato non valido"}), 400

    r.set(f"queue:{queue_id}:status", status)
    return jsonify({"queue_id": queue_id, "status": status})

@app.route('/queues/<queue_id>/next', methods=['POST'])
def get_next_ticket(queue_id):
    key = f"queue:{queue_id}:tickets"
    if r.llen(key) == 0:
        return jsonify({"error": "Nessun ticket in attesa"}), 404

    ticket_number = r.lpop(key)

    # ⏺️ Salva il ticket attualmente servito su Redis
    r.set(f"queue:{queue_id}:serving", ticket_number)

    remaining_list = r.lrange(key, 0, -1)

    publish_event({
        "event": "ticket_called",
        "queue_id": queue_id,
        "ticket_number": int(ticket_number),
        "waiting_list": remaining_list
    })

    return jsonify({"ticket_number": ticket_number})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5004)