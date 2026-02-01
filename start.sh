#!/bin/bash

# Crear config de nginx con el puerto correcto
cat > /etc/nginx/nginx.conf << EOF
events {
    worker_connections 1024;
}

http {
    server {
        listen $PORT;
        
        location = /ads.txt {
            alias /app/ads.txt;
            default_type text/plain;
        }
        
        location / {
            proxy_pass http://127.0.0.1:8501;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host \$host;
            proxy_read_timeout 86400;
        }
    }
}
EOF

echo "Iniciando Streamlit..."

# Iniciar Streamlit forzando el puerto con la variable de entorno
STREAMLIT_SERVER_PORT=8501 STREAMLIT_SERVER_ADDRESS=127.0.0.1 STREAMLIT_SERVER_HEADLESS=true streamlit run app.py &

echo "Esperando a que Streamlit arranque..."
sleep 15

echo "Iniciando nginx..."
nginx -g 'daemon off;'
