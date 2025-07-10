from flask import Flask, jsonify, request
import redis

app = Flask(__name__)

# Connessione a Redis (nome del servizio docker)
r = redis.Redis(host='redis', port=6379, decode_responses=True)

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


@app.route('/queues/<queue_id>/assign', methods=['POST'])
def assign_ticket(queue_id):
    # Verifica se la coda è attiva
    status_key = f"queue:{queue_id}:status"
    if r.get(status_key) != 'active':
        return jsonify({"error": "Queue not active"}), 400

    # Recupera il numero corrente, incrementa e salva
    number_key = f"queue:{queue_id}:last_number"
    ticket_number = r.incr(number_key)

    # Aggiunge il ticket alla lista della coda
    r.rpush(f"queue:{queue_id}:tickets", ticket_number)

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
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5004)