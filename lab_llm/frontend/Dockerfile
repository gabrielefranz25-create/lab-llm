# Immagine del front-end (lezione 6, step 9): file statici e proxy /api/ verso il back-end.
#   docker compose build frontend
FROM nginx:1.27.5-alpine
ENV BACKEND_URL=http://backend:8080
COPY frontend/static/ /usr/share/nginx/html/
COPY frontend/nginx.conf.template /etc/nginx/templates/default.conf.template
