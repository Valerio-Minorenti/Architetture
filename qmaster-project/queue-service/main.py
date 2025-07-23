from flask import Flask, jsonify, request
import redis
import pika
import json
import random

app = Flask(__name__)

# Connessione a Redis
r = redis.Redis(host='redis', port=6379, decode_responses=True) #ottiene stringhe

# Pubblica eventi su RabbitMQ
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
    for status_key in r.keys("queue:*:status"): #  Controlla le chiavi Redis del tipo queue:<id>:status.
        queue_id = status_key.split(":")[1]
        if r.get(status_key) == 'active': #	Se una coda è attiva prende il numero di ticket nella lista
            length = r.llen(f"queue:{queue_id}:tickets")
            active_queues.append({"id": queue_id, "length": length})
    return jsonify(active_queues)

# Richiede un nuovo ticket
@app.route('/queues/<queue_id>/assign', methods=['POST'])
def assign_ticket(queue_id):
    if r.get(f"queue:{queue_id}:status") != 'active':
        return jsonify({"error": "Queue not active"}), 400

    # Genera ticket globale univoco
    ticket_number = r.incr("global_ticket_counter") # r.incr("global_ticket_counter") per avere un ID univoco globale.

    r.rpush(f"queue:{queue_id}:tickets", ticket_number) #ticket  aggiunto in fondo alla lista Redis 

    waiting_list = r.lrange(f"queue:{queue_id}:tickets", 0, -1)

    publish_event({
        "event": "ticket_assigned",
        "queue_id": queue_id,
        "ticket_number": ticket_number,
        "waiting_list": waiting_list
    })

    return jsonify({
        "queue_id": queue_id,
        "ticket_number": ticket_number
    })


#Cambia lo stato di una coda (active o inactive) e alloca urtnti.
@app.route('/queues/<queue_id>/status', methods=['POST'])
def update_queue_status(queue_id):
    status = request.json.get("status")
    if status not in ['active', 'inactive']:
        return jsonify({"error": "Stato non valido"}), 400

    r.set(f"queue:{queue_id}:status", status)

    if status == 'inactive':
        utenti_da_spostare = r.lrange(f"queue:{queue_id}:tickets", 0, -1)

        code_attive = {}
        for key in r.scan_iter("queue:*:status"):
            other_id = key.split(":")[1]
            if other_id != queue_id and r.get(key) == "active":
                code_attive[other_id] = True

        if code_attive:
            for utente in utenti_da_spostare:
                carichi_correnti = {
                    qid: r.llen(f"queue:{qid}:tickets")
                    for qid in code_attive
                }

                min_len = min(carichi_correnti.values())
                code_minime = [qid for qid, length in carichi_correnti.items() if length == min_len]

                scelta = random.choice(code_minime)
                r.rpush(f"queue:{scelta}:tickets", utente)

                #  Aggiorna il token dell'utente (se esiste)
                for token_key in r.scan_iter("user:*"):
                    user_data = r.hgetall(token_key)
                    if user_data.get("queue_id") == queue_id and user_data.get("ticket_number") == utente:
                        r.hset(token_key, mapping={
                            "queue_id": scelta,
                            "ticket_number": utente
                        })

            r.delete(f"queue:{queue_id}:tickets")

            publish_event({
                "event": "queue_closed_and_users_distributed",
                "from_queue": queue_id,
                "to_queues": list(code_attive.keys()),
                "moved_users": utenti_da_spostare
            })

            return jsonify({
                "queue_id": queue_id,
                "status": status,
                "users_moved": utenti_da_spostare,
                "distribution": {qid: r.lrange(f"queue:{qid}:tickets", 0, -1) for qid in code_attive}
            })

        else:
            publish_event({
                "event": "queue_closed_no_target",
                "from_queue": queue_id,
                "moved_users": utenti_da_spostare
            })

            return jsonify({
                "queue_id": queue_id,
                "status": status,
                "users_moved": utenti_da_spostare,
                "distribution": None
            })

    return jsonify({"queue_id": queue_id, "status": status})

#  Chiama il prossimo utente
@app.route('/queues/<queue_id>/next', methods=['POST'])
def get_next_ticket(queue_id):
    key = f"queue:{queue_id}:tickets"
    if r.llen(key) == 0:
        return jsonify({"error": "Nessun ticket in attesa"}), 404

    ticket_number = r.lpop(key) #  prossimo utente in attesa da una coda (lpop = prende il primo elemento).
    r.set(f"queue:{queue_id}:serving", ticket_number) #Aggiorna il valore queue:<queue_id>:serving in Redis.

    remaining_list = r.lrange(key, 0, -1)

    publish_event({
        "event": "ticket_called",
        "queue_id": queue_id,
        "ticket_number": int(ticket_number),
        "waiting_list": remaining_list
    })

    return jsonify({"ticket_number": ticket_number})

# ▶ Avvio servizio Flask
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5004)