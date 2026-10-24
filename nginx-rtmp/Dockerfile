FROM alfg/nginx-rtmp

# La imagen arranca con envsubst desde nginx.conf.template y sobrescribe nginx.conf;
# copiar a nginx.conf dejaba esta config sin efecto.
COPY nginx.conf /etc/nginx/nginx.conf.template
