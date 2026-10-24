FROM alpine:3.20 AS build
RUN apk add --no-cache build-base git
# Receptor SRTLA de BELABOX, fijado a un commit para builds reproducibles.
ARG SRTLA_COMMIT=37862da3d0c13b46956efd3f88877053293d97d6
RUN git clone https://github.com/BELABOX/srtla.git /src \
 && cd /src && git checkout "$SRTLA_COMMIT" \
 && make srtla_rec

FROM alpine:3.20
COPY --from=build /src/srtla_rec /usr/local/bin/srtla_rec
EXPOSE 5000/udp
# Uso: srtla_rec <puerto_srtla> <host_srt> <puerto_srt>. Reenvía SRT normal a SRS (el streamid pasa intacto).
CMD ["srtla_rec", "5000", "srs", "10080"]
