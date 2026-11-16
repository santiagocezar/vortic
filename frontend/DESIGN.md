---
name: Vortic
description: Gestión y priorización de órdenes de trabajo para un taller oleohidráulico.
colors:
  ink: "#0f172a"
  paper: "#f8fafc"
  surface: "#ffffff"
  wash: "#f1f5f9"
  line: "#e2e8f0"
  line-strong: "#cbd5e1"
  muted: "#64748b"
  muted-soft: "#94a3b8"
  body-soft: "#475569"
  danger: "#991b1b"
  danger-wash: "#fee2e2"
  danger-row: "#fef2f2"
  success: "#166534"
  success-wash: "#dcfce7"
  info: "#1e40af"
  info-wash: "#dbeafe"
  whatsapp: "#16a34a"
  warning: "#b45309"
typography:
  title:
    fontFamily: "Inter Variable, system-ui, -apple-system, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.2
  heading:
    fontFamily: "Inter Variable, system-ui, -apple-system, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 700
    lineHeight: 1.35
  body:
    fontFamily: "Inter Variable, system-ui, -apple-system, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Inter Variable, system-ui, -apple-system, sans-serif"
    fontSize: "0.85rem"
    fontWeight: 600
    lineHeight: 1.4
  small:
    fontFamily: "Inter Variable, system-ui, -apple-system, sans-serif"
    fontSize: "0.8rem"
    fontWeight: 400
    lineHeight: 1.45
  control:
    fontFamily: "Inter Variable, system-ui, -apple-system, sans-serif"
    fontSize: "0.9rem"
    fontWeight: 400
    lineHeight: 1.45
  badge:
    fontFamily: "Inter Variable, system-ui, -apple-system, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.3
  chip:
    fontFamily: "Inter Variable, system-ui, -apple-system, sans-serif"
    fontSize: "0.7rem"
    fontWeight: 600
    lineHeight: 1.3
rounded:
  xs: "4px"
  sm: "6px"
  md: "8px"
  lg: "12px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  xxl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    padding: "8px 16px"
    typography: "{typography.label}"
  button-primary-hover:
    backgroundColor: "#1e293b"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
  button-primary-disabled:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "3px 6px"
    typography: "{typography.small}"
  button-whatsapp:
    backgroundColor: "{colors.whatsapp}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    padding: "8px 16px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "6px 10px"
  badge-bloqueado:
    backgroundColor: "{colors.danger-wash}"
    textColor: "{colors.danger}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  badge-pendiente:
    backgroundColor: "{colors.line}"
    textColor: "#334155"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  badge-en_curso:
    backgroundColor: "{colors.info-wash}"
    textColor: "{colors.info}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  badge-terminado:
    backgroundColor: "{colors.success-wash}"
    textColor: "{colors.success}"
    rounded: "{rounded.pill}"
    padding: "2px 8px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "16px"
  nav-link:
    textColor: "{colors.line-strong}"
    typography: "{typography.label}"
---

# Design System: Vortic

## Overview

**Creative North Star: "La pizarra de taller"**

Vortic es la pizarra donde el taller anota el trabajo del día: se lee de un vistazo, desde la puerta, y cada trabajo tiene un lugar y un motivo. La interfaz no compite con los datos. El gris claro del fondo hace de pared, las superficies blancas hacen de hojas, y el azul de fundición marca lo que se toca. Nada flota si no tiene que flotar.

La densidad es deliberada pero no apretada: el listado principal es una tabla, no una grilla de tarjetas, y la primera columna útil es el orden de prioridad. El tono es industrial y táctil sin disfrazarse de industria: una sola tipografía neutra y variable (Inter), los bordes son honestos, y no hay texturas de metal, stencil ni óxido.

Este sistema se niega a dos cosas. No es un dashboard SaaS: no hay tarjetas KPI de colores, gradientes ni métricas decorativas; un número aparece porque se usa. Y no es una estética industrial decorativa: la herramienta se ve como herramienta, no como utilería.

**Key Characteristics:**

- Tabla como unidad de lectura principal; el orden de las filas es la información más importante.
- Fondo gris frío (`#f8fafc`) y superficies blancas; la elevación se resuelve por capas tonales, no por sombras.
- Un solo color con saturación real: el semáforo de estado. El resto es la familia slate.
- Tipografía del sistema, jerarquía por tamaño y peso; nada de fuentes decorativas.
- Radios cortos (6–8px) y bordes de 1px; targets táctiles generosos en el celular del técnico.

## Colors

Una paleta de acero: la familia slate completa funciona como escala neutral, y el color aparece únicamente para decir qué le pasa a una orden.

### Primary

- **Azul de fundición** (`#0f172a`): tinta del encabezado superior, botones primarios, texto de títulos y enlaces. Es el color de "esto se toca" y de "esto es un encabezado"; no es un color de marca ornamental.
- **Azul de fundición profundo** (`#1e293b`): reservado para el hover/active del botón primario y para texto sobre fondo claro cuando se necesita un paso menos que la tinta.

### Neutral

- **Pared de taller** (`#f8fafc`): fondo de la aplicación. Nunca se usa para una tarjeta.
- **Hoja** (`#ffffff`): tarjetas, formularios, filas de menú desplegable y bloques de contenido. Es la superficie de lectura.
- **Lavado** (`#f1f5f9`): hover de filas y de sugerencias, fondo de sub-formularios anidados y separadores suaves.
- **Línea** (`#e2e8f0`): borde de tablas, separadores de lista y bordes de dropdown.
- **Línea fuerte** (`#cbd5e1`): borde de campos de entrada y de cualquier control que necesite distinguirse del fondo.
- **Gris de lectura** (`#334155`): texto secundario sobre lavados y etiquetas de badge pendiente.
- **Gris de apoyo** (`#475569`): justificación de prioridad, texto auxiliar de filas y etiquetas de origen.
- **Gris apagado** (`#64748b`): subtítulos, hints y etiquetas de formulario.
- **Gris tenue** (`#94a3b8`): hints de menor jerarquía y texto de "sin datos" dentro de tarjetas.

### Semantic

- **Rojo de bloqueo** (`#991b1b` sobre `#fee2e2`): estado bloqueado, motivo de bloqueo, errores de formulario y fila de stock bajo (`#fef2f2` como fondo de fila).
- **Azul de curso** (`#1e40af` sobre `#dbeafe`): estado en curso.
- **Verde de cierre** (`#166534` sobre `#dcfce7`): estado terminado.
- **Verde de aviso** (`#16a34a`): único uso propio, el botón de aviso por WhatsApp cuando la orden está terminada.
- **Ámbar de advertencia** (`#b45309`): avisos que no son error, como una orden sin estimación cargada.

### Named Rules

**La Regla del Semáforo Único.** El color saturado pertenece al estado de la orden y a los errores. Si un elemento no comunica estado, error o la acción de WhatsApp, es slate.

**La Regla de la Pared y la Hoja.** El fondo de la app es siempre `#f8fafc`; el contenido legible vive sobre `#ffffff`. Una tarjeta blanca dentro de otra tarjeta blanca está prohibida: se resuelve con `#f1f5f9`.

## Typography

**Display Font:** Inter Variable (con `system-ui, -apple-system, sans-serif` como respaldo)
**Body Font:** la misma pila
**Label/Mono Font:** no hay fuente mono separada; los códigos (OT-0001, códigos de repuesto) usan la misma pila en peso 600.

**Character:** Una sola familia variable, Inter, servida desde el propio proyecto (`@fontsource-variable/inter`), no desde un CDN: carga con la app y sigue disponible sin conexión en la PWA. Su rango de pesos 100–900 cubre toda la jerarquía y sus cifras tabulares alinean puntajes y posiciones en la tabla. La jerarquía se construye con dos ejes —tamaño y peso—, no con familias distintas.

### Hierarchy

- **Title** (700, `1.5rem`, 1.2): título de vista (`h2`) y de la orden en el detalle. Es el ancla de la pantalla.
- **Heading** (700, `0.95rem`, 1.35): títulos de tarjeta y de grupo del listado ("Activas, en orden de prioridad sugerida", "Bloqueadas"). Deliberadamente chico: agrupa sin gritar.
- **Body** (400, `1rem`, 1.5): descripción de falla, valores de tabla, texto corrido. En tablas se hereda el tamaño del cuerpo.
- **Label** (600, `0.85rem`): etiquetas de formulario y encabezados de tabla. Las etiquetas de campo del alta usan `0.8rem` para no competir con el dato.
- **Small** (400, `0.8rem`): justificación de prioridad, hints, motivos de bloqueo, fechas y metadatos. Es el tamaño mínimo aceptado para información que se lee.
- **Control** (400, `0.9rem`): texto de botones, campos de entrada y selectores. Es el tamaño de toda la superficie interactiva.
- **Badge** (600, `0.75rem`): píldoras de estado.
- **Chip** (600, `0.7rem`): anotaciones de 1px de borde como "Sin estimación". No se usa para información que se lea de corrido.

### Named Rules

**La Regla de los Dos Ejes.** La jerarquía tipográfica se logra con tamaño y peso, nunca con una segunda familia ni con mayúsculas sostenidas. Los estados usan el vocabulario del backend con su etiqueta legible ("En curso", no `en_curso`): el valor que viaja a la API no cambia, la pantalla no muestra guiones bajos.

**La Regla del 0,8.** Ningún texto informativo baja de `0.8rem`. Los tamaños de badge (`0.75rem`) y chip (`0.7rem`) existen solo para etiquetas cortas que acompañan a un dato ya legible.

## Layout

El contenido vive en una columna centrada: `max-width: 900px` para las vistas de trabajo (órdenes, stock, proveedores, clientes, detalle) y `700px` para usuarios. El margen vertical es `2rem` y el gutter lateral `1rem`; no hay contenedores anidados con su propio ancho máximo.

El ritmo espacial es una escala de 4px: `0.25rem` entre un label y su campo, `0.5rem` entre campos de una misma grilla, `0.75rem` entre bloques internos de una tarjeta, `1rem` entre tarjetas y secciones, `1.25rem` antes de un grupo de tabla y `1.5rem`–`2rem` para separar bloques mayores.

Las vistas usan dos modelos:

- **Tabla apilada** (listado de órdenes, stock, usuarios, historial de cliente): encabezado de página, acciones, filtros y tabla a ancho completo. La tabla es la protagonista y no se envuelve en tarjeta.
- **Grilla de dos columnas** (detalle de orden, formulario de nueva orden): `grid-template-columns: 1fr 1fr` con `gap: 1rem`. Un formulario denso puede usar `1fr 2fr 1fr 1fr auto` (alta de repuesto) cuando los campos tienen anchos naturales distintos.

**Estado declarado:** el listado de órdenes, su detalle y la barra superior ya introducen el quiebre de 640px; stock, proveedores, clientes, usuarios e historial todavía no lo tienen. Cualquier trabajo nuevo en esas pantallas debe introducir el quiebre, no imitar la ausencia.

## Elevation & Depth

El sistema es plano con capas tonales. La profundidad se comunica con el contraste entre pared (`#f8fafc`), hoja (`#ffffff`) y lavado (`#f1f5f9`), más bordes de 1px. Una tarjeta no proyecta sombra para separarse del fondo: se separa porque es blanca sobre gris.

La sombra existe solo para lo que realmente flota sobre el contenido y puede taparlo: menús de sugerencias y la tarjeta de login.

### Shadow Vocabulary

- **Flotante** (`box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08)`): menús de autocompletado de cliente y de repuesto.
- **Modal** (`box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08)`): tarjeta de login, única superficie centrada sobre el viewport completo.

### Named Rules

**La Regla del Plano.** Una tarjeta en reposo no tiene sombra. Si una superficie necesita una sombra para entenderse, el problema es el contraste tonal, no la falta de sombra.

## Shapes

El lenguaje de formas es de herramienta: esquinas cortas, bordes finos, nada de cápsulas salvo donde el contenido es una etiqueta.

- **`4px`**: chips de origen de prioridad ("IA", "Regla"), que deben leerse como anotación, no como botón.
- **`6px`**: botones, campos de entrada, menús de sugerencias y sub-formularios anidados. Es el radio por defecto de todo control.
- **`8px`**: tarjetas, formularios de alta y bloques de contenido. Un paso más suave porque son superficies, no controles.
- **`12px`**: solo la tarjeta de login, la única superficie que se presenta sola.
- **`999px`**: badges de estado ("bajo", `pendiente`, `en_curso`…), que son píldoras de lectura rápida.

No hay clipping, ni máscaras, ni bordes decorativos de más de 1px. El borde es información (separa filas, delimita campos), nunca adorno.

## Components

### Buttons

- **Shape:** rectángulo de esquinas cortas (6px), sin sombra.
- **Primary:** fondo azul de fundición (`#0f172a`), texto blanco, padding `0.5rem 1rem`, tamaño `0.9rem`. Es la acción por defecto de cada pantalla ("+ Nueva orden", "Registrar", "Guardar estado").
- **Hover / Focus:** el hover oscurece un paso a `#1e293b`; el foco usa el anillo del navegador. No hay transiciones declaradas hoy: el cambio es instantáneo, coherente con el tono de herramienta.
- **Disabled:** opacidad `0.5` y cursor `not-allowed`. Es el único tratamiento de deshabilitado.
- **Ghost / Link:** sin fondo y sin borde, texto azul de fundición subrayado a `0.8rem`. Se usa para acciones secundarias dentro de tablas ("Editar", "Eliminar", "Desactivar") y para cancelar. Nunca reemplaza al primario en la acción principal de la vista.
- **WhatsApp:** verde `#16a34a` con texto blanco, mismo tamaño que el primario. Aparece solo cuando la orden está terminada y el usuario es jefe.

### Chips (badges de estado)

- **Style:** píldora (`999px`), padding `0.15rem 0.5rem`, `0.75rem` en peso 600. Fondo lavado y texto en el tono fuerte del mismo matiz.
- **State:** `pendiente` gris, `en_curso` azul, `bloqueado` rojo, `terminado` verde. El badge de stock bajo reutiliza el tratamiento rojo con la palabra "bajo".
- **Procedencia con IA:** el puntaje calculado por el modelo lleva un destello de cuatro puntas de Material Symbols (`auto-awesome`, 0.9em ≈ 14px) en gris de apoyo (`#475569`). No hay chip de texto ni variante para la regla de respaldo: su ausencia es la señal, y el detalle la nombra con palabras ("regla de respaldo"). El destello nunca usa color de acento.
- **Cálculo en curso:** una orden creada en la sesión que todavía no recibió índice muestra "Calculando prioridad…" en gris apagado (`#64748b`), no en ámbar: esperar al motor no es un dato faltante ni un error. Si a los 45 s el índice no llegó, pasa a "Sin estimación" en ámbar.

### Cards / Containers

- **Corner Style:** 8px.
- **Background:** blanco (`#ffffff`) sobre pared (`#f8fafc`).
- **Shadow Strategy:** ninguna en reposo; ver Elevation & Depth.
- **Border:** ninguno por defecto. El borde de 1px se reserva para tablas y campos.
- **Internal Padding:** `1rem`; `0.75rem` en sub-bloques anidados con fondo lavado.

### Inputs / Fields

- **Style:** fondo blanco, borde de 1px `#cbd5e1`, radio 6px, padding `0.4rem 0.6rem`, texto `0.9rem`. Los campos dentro de una tarjeta ocupan el ancho completo con `margin-bottom: 0.5rem`.
- **Focus:** el anillo nativo del navegador; no se dibuja un glow propio.
- **Error:** no se marca el campo; el mensaje aparece debajo del formulario en rojo `#991b1b` a `0.85rem`. El borde del campo no cambia.
- **Disabled:** hereda el tratamiento del botón cuando corresponde; los campos de solo lectura se muestran como texto, no como input deshabilitado (por ejemplo, prioridad y justificación en el detalle).

### Navigation

- **Style:** barra superior de ancho completo, fondo azul de fundición, texto claro. Marca "Vortic" en peso 700 con `letter-spacing: 0.05em`, enlaces en `#cbd5e1` a `0.9rem`, activo en blanco y peso 600.
- **Role marker:** cuando el usuario es técnico, un badge de borde 1px `#334155` y texto `0.7rem` dice "Técnico". Es el único indicador de rol en la barra.
- **Mobile treatment:** la barra no colapsa a un menú: la tira de enlaces se desplaza en horizontal (targets de 44px) y un degradado de 20px en el borde derecho avisa que hay más destinos. "Salir" es un icono de 44×44 con `aria-label`, fuera de la zona desplazable, para que no se pierda ni se confunda con un enlace.

### Table

- **Style:** ancho completo, `border-collapse: collapse`, encabezados y celdas alineados a la izquierda con padding `0.5rem 0.75rem` y separador inferior de 1px `#e2e8f0`.
- **Row behavior:** las filas navegables llevan `cursor: pointer` y hover `#f1f5f9`. No hay zebra striping: el separador alcanza.
- **Empty state:** una fila con `colspan` y texto plano ("No hay órdenes activas."). No se usan ilustraciones ni íconos.
- **Secondary row:** la justificación de prioridad ocupa una fila propia debajo de la orden, sin borde superior, en `0.8rem` gris `#475569`, alineada bajo la columna de cliente.

### Búsqueda con autocompletado

Un solo componente (`src/components/BuscadorCombobox.vue`) implementa el patrón completo: input con icono de búsqueda, dropdown de sugerencias con opción activa, ARIA de combobox (flechas, Enter, Escape, `aria-activedescendant`), debounce de 250 ms, guarda de secuencia contra respuestas obsoletas, mensaje de error de red y anuncio de "N resultados" para lectores de pantalla. Cada vista aporta únicamente `cargar`, `etiqueta`, `clave` y el texto accesible; no se reimplementa el teclado ni el anuncio. Se usa en alta de orden, historial de cliente y registro de repuestos.

### Grouped List (signature)

El listado de órdenes no es una tabla única: es un documento en tres bloques. "Activas, en orden de prioridad sugerida" es una tabla con columna de posición (`1`, `2`, `3`…); "Bloqueadas" es una tabla aparte con el motivo como columna; "Terminadas" vive dentro de un `<details>` colapsado con el conteo en el summary. El orden de los bloques es parte del sistema: lo accionable primero, lo trabado visible, lo cerrado fuera del camino.

## Do's and Don'ts

### Do:

- **Do** resolver la separación entre superficies con los tres tonos (`#f8fafc`, `#ffffff`, `#f1f5f9`) antes de recurrir a una sombra.
- **Do** mostrar el puntaje de prioridad y marcar con la estrella solo las prioridades decididas por IA; cuando exista, mostrar la justificación en la fila de abajo.
- **Do** usar la tabla como unidad de lectura para cualquier conjunto de registros; una grilla de tarjetas solo si cada registro tiene imagen o contenido heterogéneo.
- **Do** mantener los botones y campos en 6px de radio y las tarjetas en 8px.
- **Do** dejar los estados en minúscula y con el vocabulario del backend (`pendiente`, `en_curso`, `bloqueado`, `terminado`).
- **Do** dar al menos `0.5rem` de separación entre controles y usar padding de `0.5rem 1rem` en botones, para que funcionen con el pulgar y con guantes.
- **Do** repetir el patrón de autocompletado con debounce y guarda de secuencia (buscador de cliente, de repuesto) en cualquier búsqueda nueva.

### Don't:

- **Don't** introducir tarjetas KPI, gradientes, gráficos decorativos ni métricas que no se accionen: es la anti-referencia explícita del sistema.
- **Don't** usar texturas de metal, óxido, stencil, cintas de peligro ni tipografía condensada "industrial": la herramienta se ve como herramienta.
- **Don't** poner una tarjeta blanca dentro de otra tarjeta blanca.
- **Don't** usar el verde de WhatsApp para otra cosa que el aviso al cliente, ni el rojo para acciones que no sean error o bloqueo.
- **Don't** agregar una segunda familia tipográfica ni mayúsculas sostenidas para dar énfasis.
- **Don't** bajar texto informativo de `0.8rem` ni usar `rem` fuera de la escala de 4px.
- **Don't** envolver la tabla principal en una tarjeta con sombra: el listado es el documento, no un widget.
