# Vortic

Sistema de gestión y priorización de órdenes de trabajo para un taller
oleohidráulico. Proyecto de Seminario Integrador, UTN FRSFCO, 2026.

| Parte | Tecnología | Carpeta |
|---|---|---|
| Backend (API REST) | Django + Django REST Framework, tokens JWT | `backend/` |
| Frontend | Vue 3 + TypeScript, aplicación web progresiva | `frontend/` |
| Motor de priorización | Flujo de n8n con un modelo de IA | `n8n/` |
| Base de datos | SQLite en local, PostgreSQL en producción | |
| Despliegue | Render | `render.yaml` |

## 1. Levantar el sistema en tu máquina

Desde la carpeta `vortic/`:

```bash
cp backend/.env.example backend/.env    # crea tu archivo de configuración local (solo la primera vez)
./run.sh                                # instala dependencias, aplica migraciones y levanta backend + frontend
```

- Backend: http://localhost:8000 (panel de administración en `/admin/`)
- Frontend: http://localhost:5173

Para crear el primer usuario jefe (en otra terminal):

```bash
cd backend && source venv/bin/activate   # entra al entorno de Python del proyecto
python manage.py createsuperuser         # pide usuario y contraseña
```

Después, en `/admin/` > Usuarios, cambiale el rol a "Jefe de Taller".

Sin n8n el sistema funciona igual: la prioridad la calcula la regla de
respaldo (sección 7.3 del informe).

## 2. Sumar el motor de priorización (n8n)

Necesitás Docker instalado.

**a) Levantar n8n**

```bash
cd n8n
docker compose up -d     # descarga n8n y lo deja corriendo en segundo plano
```

Abrí http://localhost:5678 y creá la cuenta de administrador (es local).

**b) Importar el flujo**

En n8n: menú de tres puntos arriba a la derecha > *Import from File* >
`n8n/vortic_priorizacion.json`.

**c) Crear las tres credenciales** (en n8n: *Credentials* > *Add credential* >
tipo *Header Auth*). El nombre de la credencial puede ser cualquiera; lo que
importa son los campos *Name* y *Value*:

| Credencial | Name | Value |
|---|---|---|
| Vortic - token del motor | `X-Motor-Token` | una clave que inventes (la misma que `MOTOR_TOKEN`) |
| Vortic - secreto del webhook | `X-Vortic-Secreto` | otra clave que inventes (la misma que `N8N_WEBHOOK_SECRETO`) |
| Anthropic - clave de API | `x-api-key` | tu clave de API de Anthropic (console.anthropic.com) |

Abrí cada nodo con un triángulo rojo y elegí la credencial que corresponde:
*Aviso de Vortic* usa el secreto del webhook; *Traer órdenes activas*,
*Guardar prioridades* y *Aplicar regla de respaldo* usan el token del motor;
*Consultar modelo de IA* usa la clave de Anthropic.

**d) Conectar el backend con n8n.** En `backend/.env`:

```
N8N_WEBHOOK_URL=http://localhost:5678/webhook/vortic-priorizar
N8N_WEBHOOK_SECRETO=<la misma clave del secreto del webhook>
MOTOR_TOKEN=<la misma clave del token del motor>
```

**e) Activar el flujo** con el interruptor *Active* / *Publish* de n8n y
reiniciar `./run.sh`.

Desde ese momento, cada vez que se crea o modifica una orden, el listado
muestra primero la regla de respaldo y, unos segundos después, el orden y la
justificación que decidió la IA (etiqueta "IA" junto al puntaje).

## 3. Cómo funciona la priorización

1. Un cambio en una orden o en el stock dispara una señal de Django
   (`taller/signals.py`).
2. El backend aplica la regla de respaldo para que el listado nunca quede
   viejo, y avisa a n8n por webhook (`taller/priorizacion.py`).
3. n8n pide las órdenes activas a `GET /api/motor/ordenes-activas/`. Esa
   respuesta trae las reglas del taller y las órdenes sin nombres ni
   teléfonos de clientes.
4. n8n le pide al modelo de IA un puntaje de 0 a 100 y una justificación por
   orden.
5. Si la respuesta sirve, la guarda con `POST /api/motor/prioridades/`. Si
   no sirve o la IA no responde, llama a `POST /api/motor/respaldo/`.
6. El backend valida cada resultado y completa con la regla los que falten.

Los endpoints `/api/motor/` se autentican con la cabecera `X-Motor-Token`
(`taller/motor.py`). El flujo también corre todos los días a las 7:30.

La versión anterior, con la red bayesiana, está en `docs/antecedentes/`.

## 4. Pruebas

```bash
cd backend && source venv/bin/activate
python manage.py test        # 24 pruebas automatizadas (casos de prueba del informe, sección 14)
cd ../frontend && npm run build   # control de tipos y compilación del frontend
```

## 5. Despliegue en Render

1. Subir el repositorio a GitHub.
2. En Render: *New* > *Blueprint* > elegir el repositorio. Render lee
   `render.yaml` y crea la base PostgreSQL, el backend (`vortic-api`) y el
   frontend (`vortic-web`).
3. Completar en el panel de `vortic-api` las variables `N8N_WEBHOOK_URL` y
   `N8N_WEBHOOK_SECRETO` (las de la instancia de n8n que se use) y copiar el
   `MOTOR_TOKEN` que generó Render a la credencial del motor en n8n.
4. Crear el primer usuario desde la consola de Render (*Shell*):
   `python manage.py createsuperuser`.

## Variables de entorno del backend

| Variable | Para qué | Local | Producción |
|---|---|---|---|
| `SECRET_KEY` | Firma de tokens y sesiones | cualquier texto | la genera Render |
| `DEBUG` | Modo desarrollo | `True` | `False` |
| `ALLOWED_HOSTS` | Dominios que atiende el backend | `localhost,127.0.0.1,host.docker.internal` | `.onrender.com` |
| `DATABASE_URL` | Base de datos | vacío (SQLite) | la completa Render |
| `CORS_ALLOWED_ORIGINS` | Desde dónde puede llamar el frontend | `http://localhost:5173` | URL del frontend |
| `FEATURE_STOCK_PROVEEDORES` | Prende o apaga stock y proveedores | `True` | `True` |
| `N8N_WEBHOOK_URL` | Dirección del webhook de n8n | vacío o la de Docker | la de n8n |
| `N8N_WEBHOOK_SECRETO` | Clave que el backend manda a n8n | | |
| `MOTOR_TOKEN` | Clave con la que n8n entra a `/api/motor/` | | la genera Render |
