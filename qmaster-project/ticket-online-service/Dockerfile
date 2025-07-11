# Usa una base Python leggera
FROM python:3.11-slim

# Imposta directory di lavoro
WORKDIR /app

# Copia i file dei requirements
COPY requirements.txt .

# Installa i pacchetti Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia tutto il contenuto nel container
COPY . .

# Espone la porta Flask
EXPOSE 5005

# Avvia l'app Flask
CMD ["python", "main.py"]