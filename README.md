# stream-server — Servidor de transmisión en vivo

Servidor Docker para recibir y distribuir streams de video en vivo via SRT y RTMP. Backend del sistema KronnosStream, accesible en `srt.kronnos.dev`.

---

## Tabla de contenidos

1. [Para qué sirve](#para-qué-sirve)
2. [Arquitectura del servidor](#arquitectura-del-servidor)
3. [Servicios Docker](#servicios-docker)
4. [Puertos y protocolos](#puertos-y-protocolos)
5. [SRS — Simple Realtime Server](#srs--simple-realtime-server)
6. [Dashboard de monitoreo](#dashboard-de-monitoreo)
7. [nginx-rtmp (backup)](#nginx-rtmp-backup)
8. [Traefik y TLS](#traefik-y-tls)
9. [API de streams](#api-de-streams)
10. [Integración con stream-app](#integración-con-stream-app)
11. [Estructura de archivos](#estructura-de-archivos)
12. [Deploy y operación](#deploy-y-operación)

---

## Para qué sirve

Recibe streams de video enviados desde la app Android (`stream-app`) y los distribuye para visualización. Soporta:

- Ingesta SRT (protocolo primario, tolerante a pérdida de paquetes)
- Ingesta RTMP (protocolo secundario, amplia compatibilidad)
- RTMPS sobre TLS vía Traefik (port 443)
- HLS para reproducción en navegador
- Dashboard web para monitorear streams activos y generar QR de conexión

---

## Arquitectura del servidor

```
Internet
    │
    ▼
Traefik (TLS termination)
    │ HTTPS/443 → monitor (dashboard)
    │ TCP/443   → RTMPS passthrough
    │
    ├── SRS container
    │   ├── :1935  RTMP ingest + playback
    │   ├── :10080 SRT ingest + playback (UDP)
    │   ├── :8080  HTTP: HLS, HTTP-FLV, stats HTML
    │   └── :1985  HTTP API (streams, clients, config)
    │
    ├── monitor container (dashboard)
    │   └── :80 nginx → sirve index.html + proxy /api/srs → SRS :1985
    │
    └── nginx-rtmp container (backup)
        ├── :1936 RTMP backup
        └── :8081 stats
```

Todos los contenedores corren en la red `dokploy-network` (red externa de Dokploy/Traefik). Solo `monitor` tiene etiquetas Traefik — es el único servicio expuesto públicamente por HTTPS.

---

## Servicios Docker

### `srs` — motor de streaming

Imagen base: `ossrs/srs:5` (SRS versión 5).

Config personalizada en `srs/srs.conf`:
- Escucha RTMP en 1935
- Escucha SRT en 10080 (UDP)
- HTTP API en 1985
- HTTP server (HLS/stats) en 8080
- HLS habilitado: fragmentos de 3s, ventana de 12s
- HTTP-FLV habilitado (mount `[vhost]/[app]/[stream].flv`)
- Hasta 1000 conexiones simultáneas

### `monitor` — dashboard web

Nginx Alpine + HTML/JS estático. Sirve el panel de control en `https://srt.kronnos.dev`.

Al iniciar, `entrypoint.sh` resuelve la IP del contenedor `srs` por DNS interno Docker y la inyecta en la config nginx (reemplaza `SRS_PLACEHOLDER`). Esto evita hardcodear la IP del contenedor, que cambia en cada deploy.

El dashboard hace peticiones a `/api/srs/*` que nginx proxea a `http://srs:1985/api/*`.

### `srtla` — receptor de bonding (Belabox)

`srtla_rec` de BELABOX (commit fijado en `srtla/Dockerfile`). Recibe SRTLA en UDP 5000 y reenvía SRT normal a `srs:10080`; el streamid del equipo pasa intacto (`#!::r=live/cam1,m=publish`). SRS ve como publicador la IP del contenedor `srtla`, no la del Belabox. Probado de extremo a extremo en local (ffmpeg → `srtla_send` → `srtla_rec` → SRS). Requiere el puerto UDP 5000 abierto en el firewall del proveedor. Sin SRTLA, el Belabox también puede enviar SRT simple al 10080.

### `nginx-rtmp` — RTMP de backup

Imagen propia con nginx-rtmp. Corre en paralelo en el puerto 1936 (host). Útil como fallback si SRS tiene problemas, o para reproducción RTMP desde players que no soportan SRS.

---

## Puertos y protocolos

| Puerto (host) | Protocolo | Servicio | Uso |
|---------------|-----------|----------|-----|
| 443 (TCP) | HTTPS | Traefik → monitor | Dashboard público |
| 1935 (TCP) | RTMP | SRS | Publish + play |
| 1936 (TCP) | RTMP | nginx-rtmp | RTMP backup |
| 10080 (UDP) | SRT | SRS | Publish + play |
| 5000 (UDP) | SRTLA | srtla | Ingesta con bonding (Belabox); reenvía SRT a SRS:10080 |
| 8080 (TCP) | HTTP | SRS | HLS, HTTP-FLV, stats |
| 8081 (TCP, solo 127.0.0.1) | HTTP | nginx-rtmp | Stats nginx-rtmp |
| 1985 (TCP) | HTTP | SRS API | REST API; el monitor la usa por la red Docker (expuesta también en el host) |

---

## SRS — Simple Realtime Server

SRS es el motor central. Recibe streams y los convierte a múltiples formatos de salida.

### Configuración activa (`srs/srs.conf`)

```nginx
listen              1935;       # RTMP
max_connections     1000;
daemon              off;        # Docker: proceso en primer plano
srs_log_level       warn;

srt_server {
    enabled         on;
    listen          10080;      # UDP
}

vhost __defaultVhost__ {
    srt { enabled on; }
    hls {
        enabled      on;
        hls_fragment 3;         # segmentos de 3 segundos
        hls_window   12;        # ventana de 12 segundos (4 segmentos)
    }
    http_remux {
        enabled on;
        mount   [vhost]/[app]/[stream].flv;   # HTTP-FLV
    }
}
```

### Formatos de salida disponibles por stream

Un stream `cam1` publicado por SRT es automáticamente distribuible como:

| Formato | URL |
|---------|-----|
| SRT play | `srt://srt.kronnos.dev:10080?streamid=cam1` |
| RTMP play | `rtmp://srt.kronnos.dev:1935/live/cam1` |
| HLS | `http://srt.kronnos.dev:8080/live/cam1.m3u8` |
| HTTP-FLV | `http://srt.kronnos.dev:8080/live/cam1.flv` |

### StreamID SRT

SRS usa el streamid para identificar streams SRT:

```
Publicar:   #!::r=live/cam1,m=publish
Reproducir: cam1
```

La app Android publica con `m=publish`. Un player SRT reproduce con solo el nombre del stream.

---

## Dashboard de monitoreo

Accesible en `https://srt.kronnos.dev`. Single-page app HTML/JS sin frameworks.

**Funcionalidades:**
- Lista streams en tiempo real (polling a la API cada 2s); un stream sin publicador sale como `SIN SEÑAL`
- Por cada stream muestra: miniatura de vista previa, resolución + orientación (VERTICAL/HORIZONTAL), FPS reales medidos, bitrate, tiempo en vivo, códecs y estado del audio (con audio / señal baja / silencio / sin audio, con pico en dB)
- Genera QR con la URL de conexión para cada stream (cam1–cam10)
- URLs de publicación copiables (SRT publish, RTMP publish)
- Estadísticas globales: streams activos, clientes conectados

**Datos que SRS no entrega (servicio `probe`):** `probe/probe.py` (alpine + ffmpeg) abre cada 15 s el HTTP-FLV de cada publicador activo y escribe `<stream>.json` (fps medido, nivel de audio) y `<stream>.jpg` (miniatura) en el volumen `probe-data`; el monitor lo sirve en `/probe/`. Umbrales de audio por pico: ≤ -50 dB silencio, ≤ -18 dB señal baja.
**Tiempo en vivo:** el campo `live_ms` de SRS es la hora actual, no el inicio del stream; la duración sale del `alive` del cliente publicador en `/api/v1/clients/`.
**Viewers:** clientes no publicadores de `/api/v1/clients/` (el campo `clients` del stream incluye al publicador).
**Conexión rápida (QR):** panel plegado; lo usa stream-app (Android). Los QR se generan al abrirlo.

**Cómo funciona internamente:**

```
browser → GET /api/srs/v1/streams/ → nginx proxy → SRS HTTP API :1985
                                          ↓
                              JSON con lista de streams activos
                                          ↓
                              renderStream() → tarjeta HTML por stream
```

El QR de cada cámara contiene la URL SRT completa con streamid. Al escanearlo desde `stream-app`, la app parsea la URL y rellena la configuración automáticamente.

**Resolución de IP del SRS:** `entrypoint.sh` hace `getent hosts srs` para obtener la IP Docker interna, la inyecta en la config nginx con `sed`, luego arranca nginx. Reintentos cada 2s hasta 15 intentos.

---

## nginx-rtmp (backup)

Config en `nginx-rtmp/nginx.conf`:
- Application `live` con record off (no graba a disco)
- Permite publish y play desde cualquier IP
- Stats en `/stat` (XML)

Corre en puerto 1936 del host para no colisionar con SRS en 1935.
La imagen `alfg/nginx-rtmp` arranca con `envsubst` desde `nginx.conf.template`, por eso el Dockerfile copia la config ahí (copiarla a `nginx.conf` la dejaba sin efecto).

---

## Traefik y TLS

El servidor corre en un host con Dokploy + Traefik. Solo el servicio `monitor` tiene etiquetas Traefik:

```yaml
traefik.enable=true
traefik.docker.network=dokploy-network
traefik.http.routers.stream-monitor.rule=Host(`srt.kronnos.dev`)
traefik.http.routers.stream-monitor.entrypoints=websecure
traefik.http.routers.stream-monitor.tls.certresolver=letsencrypt
traefik.http.routers.stream-monitor.priority=100
traefik.http.services.stream-monitor.loadbalancer.server.port=80
```

Traefik maneja el certificado Let's Encrypt para `srt.kronnos.dev`. HTTPS en 443 termina en Traefik y llega al monitor en HTTP interno.

SRT (UDP) y RTMP (TCP) NO pasan por Traefik — los puertos 10080 y 1935 están expuestos directamente en el host.

---

## API de streams

SRS expone una REST API en el puerto 1985 (solo accesible internamente, el monitor la proxea):

```
GET /api/v1/streams/        → lista todos los streams activos
GET /api/v1/clients/        → lista clientes conectados
GET /api/v1/summaries/      → resumen global (streams, clientes)
```

La app Android consulta `https://srt.kronnos.dev/api/srs/v1/streams/` (que nginx proxea a SRS) para mostrar el estado en el dashboard y en el QR.

Respuesta típica de un stream activo:
```json
{
  "stream": "cam1",
  "app": "live",
  "live_ms": 1716990000000,
  "kbps": { "recv_30s": 4200 },
  "video": { "codec": "H264", "profile": "High", "width": 1920, "height": 1080, "fps": 30 },
  "audio": { "codec": "AAC", "sample_rate": 44100, "channel": 2 }
}
```

---

## Integración con stream-app

El flujo completo app → servidor:

```
stream-app (Android)
    │
    │  SRT: srt://srt.kronnos.dev:10080
    │  StreamID: #!::r=live/cam1,m=publish
    │  (o RTMP: rtmp://srt.kronnos.dev:1935/live/cam1)
    │
    ▼
SRS container
    │
    ├── HLS  → /live/cam1.m3u8  (reproducción en browser)
    ├── FLV  → /live/cam1.flv   (HTTP-FLV players)
    ├── SRT  → port 10080       (players SRT)
    ├── RTMP → port 1935        (OBS, VLC, etc.)
    └── API  → /api/v1/streams/ (dashboard + QR)
```

**QR del dashboard → app:**
El dashboard genera un QR con la URL SRT de publicación. La app Android lo escanea con ML Kit, parsea el host + streamid, y auto-configura la conexión.

**Convención de nombres:**
- `cam1` a `cam10`: streams predefinidos para el flujo normal
- Cualquier string alfanumérico es válido como nombre de stream

---

## Estructura de archivos

```
stream-server/
├── docker-compose.yml           # Define los servicios: srs, nginx-rtmp, probe, monitor
│
├── srs/
│   ├── Dockerfile               # FROM ossrs/srs:5, copia srs.conf
│   └── srs.conf                 # Config SRS: puertos, HLS, SRT, API
│
├── nginx-rtmp/
│   ├── Dockerfile               # nginx con módulo RTMP
│   └── nginx.conf               # Application live, stats
│
├── srtla/
│   └── Dockerfile               # Compila srtla_rec (BELABOX) y reenvía a SRS
│
├── probe/
│   ├── Dockerfile               # alpine + ffmpeg + python3
│   └── probe.py                 # Mide fps/audio y genera miniaturas de streams activos
│
└── monitor/
    ├── Dockerfile               # nginx:alpine + bind-tools
    ├── entrypoint.sh            # Resuelve IP SRS, inyecta en nginx.conf
    ├── nginx.conf               # Sirve HTML + proxy /api/srs (solo GET) → SRS:1985, /live/ → SRS:8080, /probe/
    └── index.html               # Dashboard SPA: streams, QR, stats (633 líneas)
```

---

## Deploy y operación

```bash
# Levantar todos los servicios
docker compose up -d

# Ver logs en tiempo real
docker compose logs -f srs
docker compose logs -f monitor

# Restart de un servicio específico
docker compose restart srs

# Ver streams activos desde el host
curl http://localhost:1985/api/v1/streams/

# Ver clientes conectados
curl http://localhost:1985/api/v1/clients/

# Bajar todo
docker compose down

# Rebuild tras cambios en config
docker compose up -d --build srs
docker compose up -d --build monitor
```

**Requisitos del host:**
- Docker + Docker Compose
- Dokploy con Traefik configurado y red `dokploy-network` existente
- Puerto UDP 10080 abierto en firewall (SRT)
- Puertos TCP 1935, 443 abiertos en firewall (RTMP, HTTPS)
