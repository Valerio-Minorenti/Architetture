from flask import Flask, request, render_template
import requests

app = Flask(__name__)

QUEUE_SERVICE_URL = "http://queue-service:5004"  # Assicurati che questo nome coincida con docker-compose

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None

    if request.method == 'POST':
        action = request.form['action']
        queue_id = request.form['queue_id']

        try:
            if action == 'open':
                # Attiva la coda
                res = requests.post(f"{QUEUE_SERVICE_URL}/queues/{queue_id}/status", json={"status": "active"})
                result = f"Coda '{queue_id}' attivata con successo!" if res.ok else res.text

            elif action == 'close':
                # Disattiva la coda
                res = requests.post(f"{QUEUE_SERVICE_URL}/queues/{queue_id}/status", json={"status": "inactive"})
                result = f"Coda '{queue_id}' disattivata." if res.ok else res.text

            elif action == 'next':
                # Chiama il prossimo ticket
                res = requests.post(f"{QUEUE_SERVICE_URL}/queues/{queue_id}/next")
                data = res.json()
                if res.ok:
                    result = f"Prossimo numero chiamato: {data['ticket_number']}"
                else:
                    result = data.get("error", "Errore")

        except Exception as e:
            result = f"Errore di comunicazione con queue-service: {e}"


    return render_template("index.html", result=result)
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)