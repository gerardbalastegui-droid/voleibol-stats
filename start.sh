#!/bin/bash

# Limpiar variable que interfiere
unset STREAMLIT_SERVER_PORT

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

# Iniciar Streamlit en segundo plano
streamlit run app.py --server.port=8501 --server.address=127.0.0.1 &

# Esperar a que Streamlit arranque
sleep 5

# Iniciar nginx
nginx -g 'daemon off;'
