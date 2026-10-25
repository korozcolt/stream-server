# Auditoría y mejoras del stream-server — 24 oct 2026

Sesión de revisión con el servidor en uso (pruebas simultáneas durante el evento Sucre U17). Todo lo medido se hizo en modo lectura sobre `korserver`; los cambios llegaron por `git push` a `main` (Dokploy hace auto deploy).

Commits: `7bbd3a5` (monitor + probe), `a834155` (fix nginx-rtmp), `330348c` y `fbaa705` (srtla + docs).

---

## 1. Resumen de lo pedido y estado

| # | Pedido | Estado |
|---|--------|--------|
| 1 | Auditoría completa | Hecha (sección 2). Pendientes en sección 7 |
| 2 | FPS reales y orientación V/H | Hecho: servicio `probe` + etiqueta VERTICAL/HORIZONTAL |
| 3 | Tiempo live en −1 s | Corregido: se usa el `alive` del publicador |
| 4 | Saber si viene audio | Hecho: estado CON AUDIO / SEÑAL BAJA / SILENCIO / SIN AUDIO con pico en dB |
| 5 | Ventana de preview | Hecho: miniatura 360 px refrescada cada 15 s (no es video en vivo) |
| 6 | Apagar el enlace con Facebook | Hecho: relay apagado, nadie lee `live/facebook` (OBS lo cambió el usuario) |
| 7 | Conexión rápida (QR) | Se conserva plegada: la usa stream-app en Android; en iPhone no sirve |
| + | Belabox | Servicio `srtla` (UDP 5000) para bonding; probado en local, falta Belabox real |

---

## 2. Hallazgos de la auditoría

### 2.1 Bugs del dashboard (corregidos)
- **Tiempo live en −1 s:** `live_ms` de SRS no es el inicio del stream, es la hora actual (`live_ms` = `date +%s` × 1000 en la misma consulta). El dashboard restaba `Date.now() - live_ms` → ≈ −1 s siempre. Ahora se usa `alive` (segundos) del cliente con `publish: true` en `/api/v1/clients/`.
- **FPS inexistentes:** SRS 5.0.213 no expone fps y el contador `frames` vale 0 en streams SRT; el cálculo `frames / duración` no podía funcionar. Ahora los mide `probe`.
- **Uptime y versión de SRS siempre `—`:** el dashboard pedía `/v1/summaries/` con barra final; SRS responde con el índice de la API. Sin barra devuelve `data.self`.
- **URL HLS rota:** `https://srt.kronnos.dev/live/<stream>.m3u8` caía en el `try_files` del monitor y devolvía el HTML. Se agregó `location /live/` que proxea a `srs:8080`.
- **Streams fantasma como LIVE:** `live/facebook` se mostraba LIVE con `publish.active: false` (solo tenía a OBS leyéndolo). Ahora el badge sale de `publish.active` y las tarjetas sin publicador son `SIN SEÑAL`.
- **Viewers inflados:** el campo `clients` del stream incluye al publicador. Ahora se cuentan los clientes no publicadores.
- **Repintado completo cada 2 s:** parpadeo y reinicio de los botones "Copiar". Las tarjetas se crean una vez y solo se actualizan los textos.
- **Streamid en URLs:** los nombres se codifican con `encodeURIComponent`.

### 2.2 Seguridad
| Hallazgo | Estado |
|----------|--------|
| El proxy `/api/srs/` pasaba cualquier método: `DELETE /api/srs/v1/clients/<id>` expulsa al publicador | **Corregido:** `limit_except GET { deny all; }` (verificado: DELETE → 403) |
| XSS almacenado: el nombre del stream (lo elige el publicador, sin autenticar) se insertaba con `innerHTML` | **Corregido:** tarjetas con `textContent` / DOM API; `probe` solo acepta nombres `[A-Za-z0-9_-]{1,64}` |
| Cualquiera puede publicar en `live/<nombre>` (SRS y nginx-rtmp sin autenticación) | **Pendiente** (7) |
| Puertos 1985 (API SRS), 8080 y 8081 (stats nginx-rtmp) abiertos a internet | 8081 ahora solo en 127.0.0.1; 1985 se deja abierto a propósito (no se toca SRS en evento) |
| Librería QR cargada de CDN sin SRI | Pendiente menor |

### 2.3 Desfase repo ↔ servidor
Estado de `korserver` antes de esta sesión (contenedores con 6 días):
- **monitor:** `nginx.conf` con la IP de SRS fija (`172.20.0.3`) en vez del entrypoint que resuelve la IP. Si el contenedor SRS se recrea, el dashboard dejaba de ver la API.
- **SRS:** corría `srs_log_level info` y `latency 300` (los cambios locales a `warn` y `120` no estaban commiteados).
- **nginx-rtmp:** corría la configuración por defecto de la imagen (apps `stream` y `hls`, con transcodificación ffmpeg a 5 variantes), **no** la del repo. Causa: `alfg/nginx-rtmp` arranca con `envsubst < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf`, y el Dockerfile copiaba a `nginx.conf`, que se sobrescribía. Corregido copiando a `nginx.conf.template`.
- **docker-compose.yml del servidor:** modificado solo de formato (comillas); más un `.env` sin versionar (APP_NAME, COMPOSE_PROJECT_NAME, DOCKER_CONFIG).

### 2.4 Otros
- OBS headless (`kronnos-studio-obs`) usaba ~90 % de CPU en el host de 4 núcleos y 16 GB; SRS ~8 % y 57 MB. Es de otro proyecto, anotado.
- Logs Docker: `json-file` con `max-size 10m`, `max-file 3` en los tres contenedores (OK).
- README desactualizado: decía `log_level info`, polling de 5 s y no incluía probe/srtla.
- `docker-compose.local.yml` (red local del partido, IP 192.168.112.212) sigue sin versionar; se le agregó `probe` para paridad.

---

## 3. Dashboard: qué muestra ahora

Por cada stream (`monitor/index.html`):
- Badge `LIVE` o `SIN SEÑAL` (según `publish.active`), viewers reales.
- **Preview:** miniatura 360 px, con antigüedad ("hace Ns").
- **Resolución + orientación:** `1080×1920 · VERTICAL · 9:16` (amarillo vertical, verde horizontal, gris cuadrado; tolerancia 2 %).
- **FPS reales** medidos por `probe` (`—` si la medición tiene más de 60 s).
- **Video:** códec y perfil. **Audio:** códec, frecuencia, canales y estado.
- **Bitrate** (`kbps.recv_30s`), **tiempo live** (`alive` del publicador).
- URLs copiables SRT / RTMP / HLS (HLS por HTTPS ya funciona).
- Cabecera: streams activos, viewers, ancho de banda ↓↑, uptime y versión de SRS.
- Panel de QR plegado (se dibujan al abrirlo). Sección de conexión manual con bloque SRTLA/Belabox.

Estados de audio (`probe`, por pico `max_volume`):
| Estado | Condición | Color |
|--------|-----------|-------|
| SIN AUDIO | SRS no reporta pista de audio | rojo |
| SILENCIO | pico ≤ −50 dB | rojo |
| SEÑAL BAJA | pico ≤ −18 dB | amarillo |
| CON AUDIO | pico > −18 dB | verde |
| midiendo… | aún sin medición | gris |
Referencia: voz sana con pico ≈ −6 a −3 dB. Valores vistos: cam2 pico −20 dB (baja), cam1 pico −5 a −14 dB (ok).

---

## 4. Servicio `probe`

`probe/` (alpine 3.20 + ffmpeg + python3, sin dependencias externas).
- Cada `PROBE_INTERVAL` (15 s) consulta `http://srs:1985/api/v1/streams/` y, por cada stream de la app `live` con publicador activo, abre `http://srs:8080/live/<stream>.flv` dos veces ~4 s:
  1. `ffprobe -show_entries packet=pts_time` sobre el video → fps = (paquetes − 1) / (último pts − primer pts).
  2. `ffmpeg` → 1 frame escalado a 360 px (JPEG) y, si SRS reporta audio, `volumedetect` (mean y max en dB).
- Escribe `<stream>.json` y `<stream>.jpg` en el volumen `probe-data` (escritura atómica con `os.replace`); el monitor lo monta solo-lectura y lo sirve en `/probe/` con `Cache-Control: no-store`. Los archivos de streams que ya no están activos se borran.
- Coste: un cliente HTTP-FLV extra durante ~8 s cada 15 s por stream; aparece en la lista de clientes de SRS. Si hay mucha carga conviene subir `PROBE_INTERVAL`.
- Limitación: la miniatura necesita un keyframe dentro de los 4 s de muestra; si no llega, conserva la anterior. El tipo `HEVC` no se ha probado.
- Los fps medidos reflejan la entrega real al servidor: `cam1` osciló entre 16 y 37 fps el 24 oct (cámara o red inestable), dato que antes no se veía.

---

## 5. Cambios de configuración

| Archivo | Cambio |
|---------|--------|
| `docker-compose.yml` | + servicios `probe` y `srtla`; volumen `probe-data`; `8081` solo en 127.0.0.1; SRS sin cambios |
| `monitor/nginx.conf` | `/api/srs/` solo GET; `+ /probe/`; `+ /live/` (HLS/FLV por HTTPS) |
| `monitor/index.html` | Reescrito el script; CSS de preview/orientación/audio; QR plegado; bloque SRTLA |
| `nginx-rtmp/Dockerfile` | Copia a `nginx.conf.template` |
| `nginx-rtmp/nginx.conf` | `+ daemon off;` y `error_log /dev/stdout info;` |
| `probe/`, `srtla/` | Nuevos |
| `srs/srs.conf` | **Sin subir** (cambios locales `warn` y `latency 120` del usuario). Se mantiene baja latencia a propósito: una app envía datos directamente y necesita resultados inmediatos |

### Incidentes del deploy (24 oct)
1. **El primer deploy (`7bbd3a5`) reinició SRS** (18:55 UTC) aunque su servicio no cambió; Dokploy recrea más de lo que cambió. La cámara se reconectó sola. Los deploys siguientes (`a834155`, `330348c`, `fbaa705`) no lo reiniciaron (SRS siguió con 36+ min de uptime). **Lección:** el primer deploy tras un desfase largo puede recrear todo; hacerlo fuera de transmisión.
2. **nginx-rtmp en bucle de reinicio** tras el primer deploy: al aplicarse por fin la config del repo, faltaba `daemon off;` (el CMD de la imagen no lo agrega) y el contenedor terminaba con código 0 sin logs. Corregido en `a834155`.

---

## 6. Belabox / SRTLA

BELABOX (belaUI + belacoder + srtla) envía MPEG-TS por SRT, con bonding de varios módems vía SRTLA. Esto se documentó **sin tener registros previos** del equipo en el proyecto; lo siguiente salvo prueba real es conocimiento general.

- **SRT simple** (un enlace): funciona desde siempre: `srt.kronnos.dev:10080`, streamid `#!::r=live/<nombre>,m=publish`.
- **SRTLA** (bonding): servicio `srtla/` (alpine, `srtla_rec` de `github.com/BELABOX/srtla` fijado al commit `37862da3d0c13b46956efd3f88877053293d97d6`). `srtla_rec 5000 srs 10080`: recibe en UDP 5000 y reenvía SRT normal a SRS. El streamid pasa intacto.
- **Prueba local** (ffmpeg → `srtla_send` → `srtla_rec` → SRS): el stream entró como H264 720p + AAC y SRS lo mostró `srt-publish`. SRS ve la IP del contenedor `srtla` como publicador, no la del Belabox.
- **Latencia:** SRT negocia la mayor de las dos partes; los 1–2 s que pide Belabox para celular prevalecen sobre los 120 ms de `srs.conf`.
- **Bitrate variable:** belacoder adapta el bitrate; el dashboard lo verá subir y bajar.
- **HEVC:** SRS 5 probablemente no lo ingiere; usar H.264 (no verificado).
- **BELABOX Cloud** (panel remoto y relay propio) es independiente de este servidor; no hay integración.
- Estado en producción: `stream-server-main-srtla-1` arriba, escuchando UDP 5000 y conectado a `srs:10080`. **Sin probar con un Belabox real** y sin confirmar que el firewall del proveedor deja pasar UDP 5000.

---

## 7. Pendientes

1. **Autenticación de publish** (hoy cualquiera puede publicar en `live/<nombre>`): SRS `http_hooks.on_publish` con un secreto en el stream (`cam1?secret=…` / streamid). Exige que todas las cámaras, apps y OBS lo envíen; hacerlo fuera de evento y con el secreto generado por el sistema.
2. **OBS `feed_cam1`:** ya no lee `live/facebook` (lo cambió el usuario). Verificar a qué stream apunta el JSON de OBS en `kronnos-studio` para que `obs-restore.mjs` no lo revierta.
3. **Alinear `srs.conf` de producción** (`info`/300) con el repo (`warn`/120) cuando se pueda reiniciar SRS sin cortar la transmisión.
4. Probar SRTLA con un Belabox real y abrir UDP 5000 en el firewall del proveedor si hace falta.
5. Cerrar 1985 y 8080 si ya nadie los usa desde fuera (comprobar primero con el equipo que consume la API).
6. Versionar `docker-compose.local.yml` o sacarlo del repo; quitar la IP fija.
7. Preview en vivo (player flv.js) en vez de miniatura, si se necesita.
8. SRI o copia local de la librería QR.

---

## 8. Comandos útiles

```bash
# Estado del servicio (korserver)
ssh korserver 'docker ps --format "{{.Names}}\t{{.Status}}" | grep stream-server'
ssh korserver 'docker logs --tail 20 stream-server-main-probe-1'
ssh korserver 'docker logs --tail 20 stream-server-main-srtla-1'

# Streams y clientes (públicos por el proxy del monitor)
curl -s https://srt.kronnos.dev/api/srs/v1/streams/
curl -s "https://srt.kronnos.dev/api/srs/v1/clients/?count=50"
curl -s https://srt.kronnos.dev/api/srs/v1/summaries        # sin "/" final

# Medición del probe
curl -s https://srt.kronnos.dev/probe/<stream>.json
curl -s -o preview.jpg https://srt.kronnos.dev/probe/<stream>.jpg

# Medir fps y audio a mano (desde cualquier equipo con ffmpeg)
ffprobe -v error -select_streams v:0 -show_entries packet=pts_time -of csv=p=0 -read_intervals "%+4" http://srt.kronnos.dev:8080/live/<stream>.flv
ffmpeg -t 8 -i http://srt.kronnos.dev:8080/live/<stream>.flv -vn -af volumedetect -f null -
```

Despliegue: `git push origin main` dispara el auto deploy. Un push que cambie un servicio lo recrea; el primero tras mucho tiempo sin deploy puede recrear SRS (ver 5). No desplegar durante una transmisión.
