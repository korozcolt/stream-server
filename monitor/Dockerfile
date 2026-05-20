FROM nginx:alpine
RUN apk add --no-cache bind-tools
COPY nginx.conf /etc/nginx/nginx.conf.template
COPY index.html /usr/share/nginx/html/index.html
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
