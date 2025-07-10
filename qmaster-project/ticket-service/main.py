from flask import Flask, render_template, request
import requests

app = Flask(__name__)

QUEUE_SERVICE_URL = "http://queue-service:5004"  # Usa il nome del servizio Docker

@app.route('/', methods=['GET', 'POST'])
def index():
    ticket_info = None

    if request.method == 'POST':
        # Richiedi sportelli attivi
        try:
            response = requests.get(f"{QUEUE_SERVICE_URL}/queues/active")
            active_queues = response.json()

            if not active_queues:
                ticket_info = {"error": "Nessuno sportello attivo"}
            else:
                # Seleziona la coda con meno ticket (con logica random su parità)
                best_queue = min(active_queues, key=lambda q: q["length"])
                
                # Chiedi al queue-service di assegnare un numero
                assign = requests.post(f"{QUEUE_SERVICE_URL}/queues/{best_queue['id']}/assign")
                ticket_data = assign.json()

                ticket_info = {
                    "number": ticket_data["ticket_number"],
                    "queue_id": ticket_data["queue_id"]
                }

        except Exception as e:
            ticket_info = {"error": f"Errore: {e}"}

    return render_template('index.html', ticket_info=ticket_info)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)