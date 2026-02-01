FROM python:3.11-slim

# Instalar nginx y envsubst
RUN apt-get update && apt-get install -y nginx gettext-base && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requirements e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto de archivos
COPY . .

# Dar permisos al script
RUN chmod +x start.sh

# Exponer puerto
EXPOSE $PORT

# Comando de inicio
CMD ["./start.sh"]
