# stream-server — notas del evento Sucre U17 (oct 2026)

La documentación completa vive en el repo `kronnos-studio`: `docs/EVENTO-SUCRE-U17-2026.md` (estado final) y `docs/BITACORA-2026-10-19-20.md` (cronología).
Aquí solo lo que concierne al servidor de streaming.

## Dos servidores distintos
| | `korserver` (`ssh korserver`) | `aldemar` (`ssh aldemar`) |
|---|---|---|
| IP / DNS | 72.62.168.95 · `srt.kronnos.dev` | 2.25.113.70 · `srt.aldemaralfaro.com` |
| Uso | **el del evento** (SRS + OBS headless + marcador) | pruebas iniciales / independiente |

La cámara `cam2` publica a `korserver`: SRT `srt.kronnos.dev:10080` o RTMP `rtmp://srt.kronnos.dev:1935/live/cam2` (stream `live/cam2`).

## SRS (contenedor `stream-server-main-srs-1`)
Puertos: RTMP 1935, API 1985, HTTP-FLV 8080, SRT 10080/udp. En `korserver` el `srs.conf` activo tiene `latency 300 / peerlatency 300 / recvlatency 300`, `time_jitter zero`, `mix_correct on`, HLS 3 s/12 s y `http_remux` a `.flv`.
(El `srs.conf` y `README.md` locales de este repo tienen cambios sin commit del usuario; no se tocaron.)

## Comandos útiles (en `korserver`)
```bash
curl -s localhost:1985/api/v1/streams/                  # ¿publica cam2? video/audio no deben ser null
curl -s "localhost:1985/api/v1/clients/?count=20"       # publicadores y espectadores (srt-publish / rtmp-play)
# medir audio y video (desde cualquier equipo):
ffmpeg -t 8 -i http://srt.kronnos.dev:8080/live/cam2.flv -vn -af volumedetect -f null -   # media/pico en dB
# señal de prueba (NO usar mientras se transmite):
ffmpeg -re -f lavfi -i testsrc2=size=1280x720:rate=30 -f lavfi -i sine=frequency=440 -c:v libx264 -preset veryfast -g 60 -b:v 2000k -pix_fmt yuv420p -c:a aac -f flv rtmp://srt.kronnos.dev:1935/live/cam2
```
Valores de referencia: voz hablada con pico ≈ -6 a -3 dB; la primera prueba real daba pico -15.7 dB (bajo) y la cámara de prueba del 20 oct casi silencio (-57 dB media).
OBS lee la señal por `rtmp://srs:1935/live/cam2` dentro de la red Docker.
