from flask import Flask, request, render_template, redirect, url_for, session
import requests
import json
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = "supersegreta"  # Cambia con una chiave forte in produzione

QUEUE_SERVICE_URL = "http://queue-service:5004"
CREDENTIALS_FILE = "credenziali.json"

#  Decoratore per forzare il login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

#  Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        try:
            with open(CREDENTIALS_FILE, "r") as file:
                credentials = json.load(file)

            if credentials.get(username) == password:
                session["logged_in"] = True
                return redirect(url_for("index"))
            else:
                return render_template("login.html", error="Credenziali errate")
        except Exception as e:
            return render_template("login.html", error=f"Errore: {e}")

    return render_template("login.html")

#  Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

#  Home page (protetta)
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        queue_id = request.form['queue_id']

        try:
            res = requests.post(f"{QUEUE_SERVICE_URL}/queues/{queue_id}/status", json={"status": "active"})
            if res.ok:
                return redirect(url_for('gestione', queue_id=queue_id))
            else:
                return render_template("index.html", error="Errore: " + res.text)

        except Exception as e:
            return render_template("index.html", error=f"Errore di comunicazione: {e}")

    return render_template("index.html")

#  Gestione sportello (protetta)
@app.route('/gestione/<queue_id>', methods=['GET', 'POST'])
@login_required
def gestione(queue_id):
    result = None

    if request.method == 'POST':
        action = request.form['action']
        try:
            if action == 'next':
                res = requests.post(f"{QUEUE_SERVICE_URL}/queues/{queue_id}/next")
                data = res.json()
                if res.ok:
                    result = f" Numero chiamato: {data['ticket_number']}"
                else:
                    result = data.get("error", "Errore")

            elif action == 'close':
                res = requests.post(f"{QUEUE_SERVICE_URL}/queues/{queue_id}/status", json={"status": "inactive"})
                if res.ok:
                    data = res.json()
                    distribution = data.get("distribution")

                    if distribution:
                        queues = ", ".join(distribution.keys())
                        result = f"Coda chiusa. Utenti spostati nelle code: {queues}"
                    
                else:
                    result = res.text

        except Exception as e:
            result = f"Errore di comunicazione con queue-service: {e}"

    return render_template("gestisci_sportello.html", queue_id=queue_id, result=result)

#  Avvio servizio
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)
