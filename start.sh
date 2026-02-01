#!/bin/bash

# Reemplazar $PORT en nginx.conf
sed -i "s/\$PORT/$PORT/g" /app/nginx.conf
cp /app/nginx.conf /etc/nginx/nginx.conf

# Iniciar Streamlit en segundo plano
streamlit run app.py --server.port=8501 --server.address=127.0.0.1 &

# Esperar un poco a que Streamlit arranque
sleep 3

# Iniciar nginx en primer plano
nginx -g 'daemon off;'
