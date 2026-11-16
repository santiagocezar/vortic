# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Dos roles con el mismo peso en el diseño:

- **Jefe de taller.** Carga y edita órdenes, decide prioridades, importa listas de precios, avisa al cliente y gestiona usuarios. Trabaja en escritorio (notebook), en la oficina del taller, intercalando atención al mostrador con la carga de trabajo del día.
- **Técnico.** Consulta el listado priorizado y su trabajo pendiente, cambia el estado de una orden, registra horas y marca repuestos usados. Trabaja en el piso del taller, con el celular, de pie y con las manos ocupadas. No crea ni edita órdenes ni avisa al cliente.

Ambos son usuarios diarios, no ocasionales.

## Product Purpose

Vortic gestiona y prioriza órdenes de trabajo de un taller oleohidráulico: registra el ingreso de un cliente y su equipo, ordena las órdenes activas por urgencia real, y conserva el rastro de todo lo que pasó con cada trabajo (estados, horas, repuestos, costos, aviso al cliente).

El sistema existe porque el orden de atención en el taller se decidía de memoria y en papel: el trabajo que más apuraba un cliente podía tapar uno más crítico o más rentable. El éxito es que el jefe abra el listado y acepte el orden propuesto sin recalcularlo a mano, y que el técnico sepa qué hacer a continuación sin preguntar.

Proyecto de Seminario Integrador, UTN FRSFCO, 2026. Hoy es una pieza académica con miras a un piloto en un taller concreto: no hay usuarios externos todavía, pero el diseño no puede asumir un entorno de demo controlado.

## Positioning

Lo que un cuaderno o una planilla no pueden dar:

1. **Priorización con justificación.** Un motor de IA (flujo n8n) puntúa de 0 a 100 cada orden activa y escribe por qué. El listado muestra puntaje y justificación, con una regla determinista de respaldo que garantiza que el orden nunca quede viejo si la IA falla o no está configurada. La prioridad no se edita desde la interfaz: se calcula.
2. **Trazabilidad de punta a punta.** Cliente → equipo → orden → repuestos (con proveedor y precio pagado) → sesiones de horas → historial de estados. Nada se pierde y todo queda atribuido a un usuario.
3. **Operación completa, no un tablero suelto.** Stock con umbral de alerta, precios de costo por proveedor importados desde planillas heterogéneas, y aviso al cliente por WhatsApp forman parte del mismo flujo.

## Operating Context

- Taller oleohidráulico monotaller: reparación de cilindros, bombas, motores, mangueras y válvulas, con clientes empresa y teléfono como dato operativo central.
- El aviso al cliente se hace por WhatsApp (`wa.me`), con teléfonos argentinos cargados de forma libre; el sistema normaliza el número.
- Cada proveedor manda su lista de precios con columnas propias; el usuario confirma el mapeo de columnas en la primera importación de ese proveedor y se reutiliza después.
- Un mismo repuesto tiene precio de costo distinto según proveedor; el proveedor de una compra puntual lo elige el jefe, no el sistema.
- El motor de IA corre en una instancia local de n8n y es opcional: sin n8n el sistema funciona igual con la regla de respaldo.
- Stock y proveedores se pueden apagar con un feature flag; el resto del producto sigue operativo.
- Demo y defensa: el sistema se muestra proyectado ante un tribunal y, a la vez, tiene que poder usarse en el celular del taller.

## Capabilities and Constraints

- Roles: `jefe` y `técnico`. El técnico puede leer todo y operar sobre una orden existente (estado, horas, repuestos usados); crear/editar/eliminar órdenes y avisar al cliente es exclusivo del jefe. La gestión de usuarios es solo del jefe.
- Órdenes con estado pendiente / en curso / bloqueado / terminado; `bloqueado` exige motivo. Criticidad del trabajo (no del cliente) en escala 1–5.
- Prioridad: `indice_prioridad`, `justificacion_prioridad`, `prioridad_origen` (`ia` o `respaldo`) y `prioridad_actualizada`, todos de solo lectura en la interfaz.
- Costos y tiempos no negativos; tiempo estimado mínimo 0,1 h. Precio de costo de una orden es foto histórica del momento de la compra.
- Stack fijado por el proyecto: Django + DRF con JWT en el backend, Vue 3 + TypeScript + Vite en el frontend, SQLite local y PostgreSQL en producción, despliegue en Render.
- Frontend como PWA instalable en el celular del técnico; la misma app tiene que resolver el escritorio del jefe.
- Idioma: español rioplatense en toda la interfaz (voseo). Moneda: pesos argentinos.
- Monotaller, sin multi-tenant ni separación por sucursal.
- Sin datos reales de clientes: la demo se carga con datos de prueba. Nada de la interfaz puede depender de datos productivos reales.
- Restricciones de accesibilidad específicas del producto: no establecidas todavía.

## Brand Commitments

- El nombre **Vortic** es fijo.
- No hay logo, paleta ni tipografía definidos: no existe un compromiso visual que preservar.
- El registro verbal del producto es directo y profesional, en español rioplatense, sin jerga técnica innecesaria para el jefe de taller.

## Evidence on Hand

- `README.md`: descripción del sistema, puesta en marcha, arquitectura del motor de priorización y despliegue.
- `backend/taller/tests.py`: 24 pruebas automatizadas que cubren los casos del informe.
- `n8n/vortic_priorizacion.json`: flujo real de priorización (webhook, consulta a la IA, guardado, respaldo).
- `docs/antecedentes/`: versión anterior con red bayesiana y su revisión.
- Ausencias que no se deben inventar: no hay clientes reales, testimonios, métricas de uso, benchmarks, precios de venta del producto ni activos de marca.

## Product Principles

1. **La prioridad se explica.** Cada orden muestra por qué está donde está; un puntaje sin justificación no sirve en el taller.
2. **El sistema nunca queda mudo.** Si la IA falla, la regla de respaldo mantiene el listado útil; si stock o proveedores están apagados, el resto sigue funcionando.
3. **Trazabilidad sobre comodidad.** Los datos históricos (precio pagado, quién cambió qué estado) no se pisan para simplificar una pantalla.
4. **El jefe decide, el sistema propone.** La IA sugiere orden y argumento; las decisiones de compra, aviso y alta de trabajo son humanas.
5. **Un celular en el taller y una notebook en la oficina son el mismo producto.** Ningún flujo central puede exigir un mouse o una pantalla grande.

## Accessibility & Inclusion

No hay requisitos de accesibilidad establecidos por el producto. El uso real en el piso del taller (celular, de pie, con guantes, con luz variable) es contexto operativo y debe guiar tamaños de objetivo táctil y contraste, no un estándar formal acordado.
