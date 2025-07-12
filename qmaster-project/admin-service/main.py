from flask import Flask, request, render_template, redirect, url_for
import requests

app = Flask(__name__)
QUEUE_SERVICE_URL = "http://queue-service:5004"

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        queue_id = request.form['queue_id']

        try:
            # Attiva sportello
            res = requests.post(f"{QUEUE_SERVICE_URL}/queues/{queue_id}/status", json={"status": "active"})
            if res.ok:
                return redirect(url_for('gestione', queue_id=queue_id))
            else:
                return render_template("index.html", error="Errore: " + res.text)

        except Exception as e:
            return render_template("index.html", error=f"Errore di comunicazione: {e}")

    return render_template("index.html")

@app.route('/gestione/<queue_id>', methods=['GET', 'POST'])
def gestione(queue_id):
    result = None

    if request.method == 'POST':
        action = request.form['action']
        try:
            if action == 'next':
                res = requests.post(f"{QUEUE_SERVICE_URL}/queues/{queue_id}/next")
                data = res.json()
                if res.ok:
                    result = f"🎫 Numero chiamato: {data['ticket_number']}"
                else:
                    result = data.get("error", "Errore")

            elif action == 'close':
                res = requests.post(f"{QUEUE_SERVICE_URL}/queues/{queue_id}/status", json={"status": "inactive"})
                if res.ok:
                    return redirect(url_for('index'))
                else:
                    result = res.text

        except Exception as e:
            result = f"Errore di comunicazione con queue-service: {e}"

    return render_template("gestisci_sportello.html", queue_id=queue_id, result=result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)