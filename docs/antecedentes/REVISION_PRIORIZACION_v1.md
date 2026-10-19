# Revisión de diseño — Priorización (Vortic)

Disparado por: agregaste una manguera y quedó al final del listado pese a ser de los trabajos más rápidos. Causa raíz encontrada + otros problemas relacionados que aparecieron al revisar el módulo.

## 1. [CRÍTICO] El índice está dominado por el costo absoluto, no por la urgencia

```
Índice = (Costo × Criticidad) / T_estimado
```

`Criticidad` después de `CRITICIDAD_A_ESCALA` solo vale 1, 2 o 3. `T_estimado` son horas (típicamente 0,5–20). `Costo` está en pesos y puede valer de $1.000 a $150.000+ — órdenes de magnitud más grande que los otros dos factores juntos. En la práctica el índice es casi `Costo / T_estimado`, y la criticidad/tiempo apenas mueven la aguja.

Ejemplo con los números que describís:
- Manguera: costo $3.000, tiempo 1h, criticidad 2 → índice = 6.000
- Motor: costo $150.000, tiempo 10h, criticidad 2 → índice = 30.000

El motor gana 5 a 1 aunque tarde 10 veces más. Cualquier trabajo caro le gana a cualquier trabajo rápido-y-barato, sin importar cuánto más rápido sea. Esto contradice la lógica de taller de "sacate de encima lo rápido primero" que mencionás, y probablemente contradice lo que el informe quiere transmitir con la fórmula (no hay una justificación en 7.3 de por qué el costo debería pesar tanto más que el tiempo).

**No es un bug de la red bayesiana** — viene de la fórmula 7.3 tal cual está en el informe, que arrastra este problema desde antes del modelo bayesiano. El cambio a pgmpy no lo introdujo, pero tampoco lo corrige.

## 2. [ALTO] `tipo_equipo` es texto libre, no un catálogo

El formulario de alta de orden (`OrdenesView.vue`, línea ~200) es un `<input>` de texto libre: *"Tipo de equipo (ej. Cilindro)"*. Nada valida contra los 5 tipos que conoce el modelo (`manguera`, `cilindro`, `bomba`, `motor`, `valvula`).

`_normalizar_tipo()` en `priorizacion.py` hace un matching muy básico (minúsculas + saca tildes de á/í) y todo lo que no calce exacto cae en el bucket `"otro"` con un prior genérico (0,20) — sin avisar a nadie. "Mangera" (typo), "Manguera hidráulica", "Manguera de alta presión" o "MANGUERA " (con espacio) hoy caen todas en `"otro"`, no en `"manguera"`. Silencioso: la orden se guarda bien, pero el cálculo de prioridad usa un prior distinto al que el jefe cree que está usando, y nadie se entera.

## 3. [MEDIO] Una orden recién creada siempre "tiene stock"

`hay_stock_disponible()` recorre `orden.repuestos_usados` — pero una orden nueva todavía no tiene repuestos cargados (se cargan después, durante el diagnóstico). Un `for` sobre una lista vacía nunca entra al loop, así que la función devuelve `True` por defecto: **toda orden nueva arranca marcada "con stock"**, aunque en realidad todavía no se sepa si va a faltar un repuesto o no. Esto le da a todas las órdenes recién creadas el prior más optimista de bloqueo (`FACTOR_STOCK_CON_STOCK = 0.3`) hasta que alguien carga el primer repuesto — que puede ser recién cuando el técnico ya empezó a trabajar.

## 4. [MEDIO] El bucket "otro" mezcla tipos de equipo sin relación entre sí

Por el problema del punto 2, todo lo que no matchea el catálogo (typos, sinónimos, equipos nuevos como "acoplamiento" o "filtro") termina compartiendo una sola fila de `EstadisticaTipoStock` (`tipo_equipo='otro'`). Si el taller empieza a recibir muchas órdenes de "filtro" y "acoplamiento" además de typos de "manguera", el aprendizaje bayesiano de la sección 7.5 mezcla el historial de bloqueo de cosas completamente distintas en una sola estadística — contamina el aprendizaje en vez de mejorarlo.

## 5. [BAJO] La escala de criticidad 1–5 de la UI en realidad tiene 3 niveles de efecto

`CRITICIDAD_A_ESCALA = {1:1, 2:1, 3:2, 4:3, 5:3}` — elegir 1 o 2 da exactamente el mismo resultado en el índice, e igual 4 o 5. El jefe de taller ve un selector de 1 a 5 (o input numérico) sin saber que en la práctica solo hay 3 niveles reales. No es grave, pero puede generar confusión o falsa sensación de control fino sobre la priorización.

## Resuelto en esta ronda

**Sectorización previa:** stock/proveedores se desactivó temporalmente (no se borró nada) detrás de un flag —
`FEATURE_STOCK_PROVEEDORES` en `config/settings.py` (backend, apaga rutas de repuestos/proveedores y la action
`registrar_repuesto`) y `CONSIDERAR_STOCK` en `taller/priorizacion.py` (apaga la variable Stock de la red). Volver
ambos a `True` reactiva todo sin reescribir código. Mientras está apagado, `calc_indice_prioridad` consulta la red
bayesiana marginalizando Stock (sin condicionar por él) en vez de usar `hay_stock_disponible()`.

- **#1 [CRÍTICO] resuelto:** `Índice = log1p(Costo) × Criticidad / T_estimado`. El log1p comprime el rango dinámico
  del costo para que criticidad y tiempo vuelvan a influir en el resultado, sin dejar de ser cierto que "más caro =
  más prioridad". Con los números del ejemplo original (manguera $3.000/1h vs. motor $150.000/10h), la manguera
  ahora queda arriba — se probó explícitamente en `test_sectorizacion.py`.
- **#2 [ALTO] resuelto:** `OrdenesView.vue` ahora tiene un `<select>` con el catálogo de `TIPOS_CONOCIDOS`
  (Manguera/Cilindro/Bomba/Motor/Válvula) + una opción "Otro" explícita con campo de texto. Ya no hay forma de que
  un typo caiga silenciosamente en el bucket "otro" — si el equipo no está en el catálogo, el jefe lo elige a
  conciencia.
- **#3 [MEDIO] resuelto (como efecto colateral de apagar Stock):** con `CONSIDERAR_STOCK=False`,
  `registrar_resultado_historico` no escribe nada — evita grabar el falso "con stock" que daba
  `hay_stock_disponible()` en órdenes sin repuestos cargados. Se retoma al reactivar el módulo de stock.
- **#4 [MEDIO] mitigado:** consecuencia directa de #2 — al ya no haber typos cayendo en "otro", ese bucket va a
  mezclar mucho menos historial de tipos distintos. Sigue existiendo como categoría legítima para equipos fuera de
  catálogo (eso es intencional).
- **#5 [BAJO] resuelto:** `CRITICIDAD_A_ESCALA` pasó a ser 1:1 (`{1:1, 2:2, 3:3, 4:4, 5:5}`) — las 5 opciones del
  selector de criticidad ahora pesan distinto en el índice, antes dos pares de opciones daban exactamente lo mismo.

Todo probado contra Django real (no solo funciones sueltas): rutas de stock devuelven 404, `registrar_repuesto`
devuelve 403, `manage.py check`/`makemigrations --check` limpios, `vue-tsc -b` y `vite build` sin errores.

**Nota de esta revisión:** el párrafo original de esta sección decía que el hallazgo #1 "se probó explícitamente en
`test_sectorizacion.py`" — ese archivo nunca se llegó a commitear, así que esa verificación no era repetible. Los
tests reales están ahora en `taller/tests.py` (ver ronda de abajo).

## Ronda 2 — Testing práctico (uso real del taller, no solo lectura de código)

Disparado por: pedido de probar el sistema en términos prácticos ("¿lo podría usar el cliente?"), corriendo
`calc_indice_prioridad` con casos reales en vez de solo revisar el código.

- **[CRÍTICO] resuelto — tiempo/costo estimado sin piso mínimo:** `tiempo_estimado=0` (typo, o el campo dejado en
  blanco por error) hacía que el índice se disparara por división cercana a cero — en la prueba, quedaba **por
  encima** de cualquier trabajo urgente real. `costo_estimado` negativo pasaba derecho y se pisaba en silencio a 0.
  Se agregó `MinValueValidator` a ambos campos en el modelo (0 para costo, 0.1h para tiempo — mismo criterio que ya
  se había aplicado a `criticidad` en la ronda 1, pero no se había extendido acá) + `min` en los inputs del
  frontend. Migración `taller/migrations/0009_alter_ordentrabajo_costo_estimado_and_more.py`.
- **[ALTO] resuelto — no había forma de cargar costo/tiempo después de crear la orden:** el alta los deja opcionales
  a propósito (muchas veces se sabe recién después del diagnóstico), pero `OrdenDetalleView.vue` solo los mostraba
  como texto — la orden quedaba con `indice_prioridad=null` para siempre. Se agregó un formulario editable en el
  detalle (solo Jefe, PATCH a `/ordenes/{id}/`, que ya dispara el recálculo vía el signal existente) con un aviso
  visible mientras falte la estimación.
- **[ALTO] resuelto — el índice seguía pudiendo quedar dominado por un solo factor, ahora el tiempo:** un trabajo
  carísimo pero muy rápido y de baja criticidad (ej. $500.000, 0,5h, criticidad 1) le ganaba a uno genuinamente
  urgente y largo (ej. $150.000, 10h, criticidad 5) — mismo problema del hallazgo #1 original, en sentido opuesto.
  Se le aplicó el mismo tratamiento que al costo: piso (`PISO_TIEMPO_HORAS=1.0`) + `log1p` para comprimir el otro
  extremo, así un trabajo de 10h no pesa 10 veces más que uno de 1h en el denominador.
- **[MEDIO] resuelto — teléfono sin dígitos rompía el aviso por WhatsApp en silencio:** el campo exigía no estar
  vacío pero no que tuviera dígitos; `avisar_cliente` armaba `wa.me/?text=...` sin destinatario. Se agregó
  `validar_telefono` (mínimo 8 dígitos) en el modelo + un chequeo defensivo en `avisar_cliente` para clientes
  cargados antes de este fix.
- **[MEDIO] resuelto — sin detección de cliente duplicado:** nada impedía crear una segunda ficha con el mismo
  teléfono. `ClienteSerializer.validate_telefono` ahora compara por dígitos (ignora formato) contra los clientes
  activos existentes.
- **[MEDIO] resuelto — sin gestión de usuarios en la interfaz:** alta de técnicos, contraseña y baja dependían de
  `/admin/` de Django. Se agregó `usuarios/urls.py` + `UsuarioViewSet` (Jefe únicamente, con baja lógica vía
  `is_active`) y una vista mínima en el frontend (`UsuariosView.vue`, ruta `/usuarios`).
- **[BAJO] resuelto — código muerto:** `OrdenTrabajoDetailSerializer.create()` tenía un `return attrs` inalcanzable
  con una variable sin definir, resto de un refactor sin terminar de limpiar.
- **[BAJO] resuelto — reabrir una orden Terminada:** no limpiaba `fecha_aviso_cliente` (mensaje confuso en el
  mostrador) y, de reactivarse el módulo de stock, una orden que se reabre y se vuelve a terminar contaría dos veces
  en `EstadisticaTipoStock`. Se limpia la fecha al salir de Terminado y se agregó un guard contra el doble conteo.

Todo cubierto con tests reales contra Django (`taller/tests.py`, `python manage.py test taller clientes` — 11/11 OK,
incluye los casos exactos que expusieron cada hallazgo) además de verificación manual vía API/serializers,
`manage.py check`, `makemigrations` sin cambios pendientes, `vue-tsc -b` y `vite build` sin errores.
