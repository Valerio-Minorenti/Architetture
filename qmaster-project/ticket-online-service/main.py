from flask import Flask, render_template, request, redirect, url_for
import redis
import requests
import uuid
import time

app = Flask(__name__, template_folder='templates')
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
        # Chiede tutte le code attive
        res = requests.get(f"{QUEUE_SERVICE_URL}/queues/active")
        queues = res.json()

        if not queues:
            return "Nessuna coda attiva."

        # Seleziona quella più corta (o casuale in caso di parità)
        min_len = min(q['length'] for q in queues)
        best_queues = [q for q in queues if q['length'] == min_len]
        queue = best_queues[0]  # o random.choice(best_queues)

        queue_id = queue['id']
        lock = acquire_lock(f"lock:{queue_id}")
        if not lock:
            return "Errore, riprova."

        try:
            res = requests.post(f"{QUEUE_SERVICE_URL}/queues/{queue_id}/assign")
            data = res.json()
        finally:
            release_lock(f"lock:{queue_id}", lock)

        # Salva in Redis il ticket per monitoraggio utente
        user_token = str(uuid.uuid4())
        r.hmset(f"user:{user_token}", {
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

    # Ottieni biglietti in attesa
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
                           notify=notify)
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005)