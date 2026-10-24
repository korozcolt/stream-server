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

## Actualización 2026-10-20 (tarde): la cámara publica como `live/livestream`
- El stream de la cámara es **`live/livestream`** (no `cam2`). El OBS en marcha ya lo lee: SRS muestra un cliente `rtmp-play /live/livestream` desde `172.20.0.4` (contenedor `kronnos-studio-obs`). El JSON guardado de OBS y `ops/obs-restore.mjs` todavía dicen `rtmp://srs:1935/live/cam2` → **desfase**; no correr `obs-restore.mjs` sin cambiarlo antes (volvería `feed_cam1` a `cam2` y se perdería la señal).
- Publicar por SRT exige `m=publish` en el streamid. `?streamid=livestream` (plano) solo sirve para ver:
  `srt://srt.kronnos.dev:10080?streamid=#!::r=live/livestream,m=publish` (si el equipo lo exige, `#` como `%23`).
  Alternativa RTMP: `rtmp://srt.kronnos.dev:1935/live/livestream`. Ver sin tocar OBS: `http://srt.kronnos.dev:8080/live/livestream.flv`.
- Estado a las 17:04 UTC: `live/livestream` con `publish.active: false` (la cámara aún no llegaba). Pendiente medir audio (-57 dB la vez anterior) y confirmar 16:9.
- No se cambió nada en OBS ni en el servidor.

## Actualización 2026-10-24: auditoría y monitor
- Dashboard: orientación V/H, FPS reales, tiempo live (`alive` del publicador; `live_ms` de SRS es la hora actual), estado de audio y miniatura. Nuevo servicio `probe` (ffmpeg) + volumen `probe-data`.
- Proxy del monitor: `/api/srs` solo GET (antes permitía `DELETE /clients/<id>` = expulsar a la cámara), `/live/` por HTTPS (la URL HLS del dashboard devolvía el HTML) y `summaries` sin `/` final (con ella SRS devolvía el índice y uptime/versión salían `—`).
- Puerto 8081 (stats nginx-rtmp) ligado a 127.0.0.1; el 1985 de SRS se dejó público a propósito (no se toca SRS durante el evento). nginx-rtmp: la config del repo ahora sí se aplica (cambia las apps a `live`).
- **Desfase en korserver** (6 días sin rebuild): monitor con IP de SRS fija, SRS con `log_level info` y `latency 300`, nginx-rtmp con config por defecto. Un rebuild de `srs`, `nginx-rtmp`, `monitor` y `probe` lo alinea; hacerlo fuera de transmisión.
- Pendientes: autenticación de publish (hoy cualquiera puede publicar en `live/<nombre>`; requiere que cámaras/OBS envíen un secreto), OBS `feed_cam1` sigue leyendo `live/facebook` (el relay de Facebook ya está apagado).
