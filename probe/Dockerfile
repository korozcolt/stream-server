FROM alpine:3.20
RUN apk add --no-cache ffmpeg python3
COPY probe.py /probe.py
CMD ["python3", "-u", "/probe.py"]
