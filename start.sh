#!/bin/bash

# Reemplazar $PORT en nginx.conf
envsubst '$PORT' < /app/nginx.conf > /etc/nginx/nginx.conf

# Iniciar Streamlit en segundo plano
streamlit run app.py --server.port=8501 --server.address=127.0.0.1 &

# Iniciar nginx en primer plano
nginx -g 'daemon off;'
