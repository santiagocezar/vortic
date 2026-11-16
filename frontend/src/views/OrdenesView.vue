<script setup lang="ts">
// HU-01 (registrar ingreso), HU-02 (autocompletar cliente existente al
// escribir), HU-05 (consultar trabajos del día) y HU-13 (ver prioridad
// sugerida) en una sola vista: el listado viene ordenado por
// indice_prioridad (default del ViewSet) y desde acá se da de alta
// cliente + orden.
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api/client'
import BuscadorCombobox from '../components/BuscadorCombobox.vue'
import { useAuthStore } from '../stores/auth'
import { etiquetaEstado } from '../utils/estados'
import IconSparkle from '~icons/material-symbols/auto-awesome'
import IconAdd from '~icons/material-symbols/add'
import IconClose from '~icons/material-symbols/close'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

interface Cliente {
  id: number
  razon_social: string
  telefono: string
}

interface OrdenListado {
  id: number
  cliente: number
  cliente_nombre: string
  tipo_equipo: string | null
  estado: string
  motivo_bloqueo: string | null
  fecha_ingreso: string
  criticidad: number
  indice_prioridad: number | null
  justificacion_prioridad: string
  prioridad_origen: '' | 'ia' | 'respaldo'
  prioridad_actualizada: string | null
}

const ordenes = ref<OrdenListado[]>([])
// El filtro vive en la URL (?estado=) para que sobreviva al ir y volver
// del detalle, al refrescar y a compartir el enlace con otro usuario.
const estadoQuery = typeof route.query.estado === 'string' ? route.query.estado : ''
const filtroEstado = ref(estadoQuery)
const cargando = ref(false)
const mostrarForm = ref(false)
const guardando = ref(false)
const errorForm = ref('')

// Estado del listado: error de red visible (antes se tragaba en un catch
// vacío), momento de la última actualización aplicada, y cambios que llegaron
// por el refresco automático pero todavía no se muestran para no re-ordenar
// la lista debajo del cursor.
const errorCarga = ref('')
const actualizadoEn = ref<Date | null>(null)
const cambiosPendientes = ref<OrdenListado[] | null>(null)
const mensajeExito = ref('')
let timerExito: ReturnType<typeof setTimeout> | undefined
let firmaActual = ''

// Órdenes creadas en esta sesión que todavía no tienen índice: mientras el
// motor responde, "Sin estimación" mentiría (parece un dato faltante cargado
// por el usuario). Se muestran como "Calculando prioridad…" y se refresca el
// listado completo en tandas cortas, porque al priorizar una orden nueva el
// motor también puede mover a las demás.
const recienCreadas = ref<number[]>([])
const VENTANA_CALCULO_MS = 45000
let timersPostAlta: ReturnType<typeof setTimeout>[] = []

// HU-02: buscador de cliente existente (en vez de un <select> con todos
// los clientes) — a medida que se escribe, sugiere coincidencias por
// razón social o teléfono; si no existe, se puede cargar uno nuevo.
const clienteSeleccionado = ref<Cliente | null>(null)
const buscadorCliente = ref<{ limpiar: () => void } | null>(null)

async function cargarClientes(q: string): Promise<Cliente[]> {
  const { data } = await api.get('/clientes/', { params: { search: q } })
  return data
}

const etiquetaCliente = (c: Cliente) => `${c.razon_social} (${c.telefono})`
const claveCliente = (c: Cliente) => c.id

const mostrarNuevoCliente = ref(false)
const nuevoCliente = ref({
  razon_social: '',
  telefono: '',
})

// Catálogo cerrado de tipos de equipo (relevamiento) más "Otro" explícito,
// para que el tipo llegue limpio al motor de priorización.
const TIPOS_EQUIPO = ['Manguera', 'Cilindro', 'Bomba', 'Motor', 'Válvula']
const OTRO_VALOR = '__otro__'
const tipoEquipoSeleccionado = ref('')
const tipoEquipoOtro = ref('')

const nuevaOrden = ref({
  descripcion_falla: '',
  costo_estimado: null as number | null,
  tiempo_estimado: null as number | null,
  criticidad: 2, // criticidad DEL TRABAJO, no del cliente
})

function firmaDe(list: OrdenListado[]) {
  return list.map((o) => `${o.id}:${o.estado}:${o.indice_prioridad ?? '-'}:${o.prioridad_origen}`).join('|')
}

async function cargarOrdenes(silencioso = false, aplicarDirecto = false) {
  if (!silencioso) cargando.value = true
  try {
    const params = filtroEstado.value ? { estado: filtroEstado.value } : {}
    const { data } = await api.get('/ordenes/', { params })
    errorCarga.value = ''
    limpiarRecienCreadas(data)
    if (silencioso) {
      // El refresco automático NO pisa la lista: si el orden cambió, se
      // avisa y el usuario decide cuándo aplicarlo. La excepción es la
      // ventana posterior a un alta, donde el reorden es lo que el usuario
      // está esperando y se aplica sin preguntar.
      if (aplicarDirecto) {
        ordenes.value = data
        firmaActual = firmaDe(data)
        cambiosPendientes.value = null
        actualizadoEn.value = new Date()
        return
      }
      if (firmaActual && firmaDe(data) !== firmaActual) {
        cambiosPendientes.value = data
      }
      return
    }
    ordenes.value = data
    firmaActual = firmaDe(data)
    cambiosPendientes.value = null
    actualizadoEn.value = new Date()
  } catch {
    // Si el token venció y el refresh también falla, el interceptor de
    // api/client.ts ya redirige al login. Acá solo evitamos quedarnos en
    // "Cargando…" para siempre y damos una salida visible.
    if (!silencioso) {
      errorCarga.value = ordenes.value.length
        ? 'No se pudo actualizar el listado. Mostrando los datos de la última carga.'
        : 'No se pudo cargar el listado de órdenes.'
    }
  } finally {
    if (!silencioso) cargando.value = false
  }
}

// Una orden deja de estar "calculando" cuando el listado ya trae su índice.
function limpiarRecienCreadas(list: OrdenListado[]) {
  if (!recienCreadas.value.length) return
  recienCreadas.value = recienCreadas.value.filter((id) => {
    const orden = list.find((o) => o.id === id)
    return !orden || orden.indice_prioridad == null
  })
}

// Tandas cortas después del alta: el motor responde en segundos y al
// recalcular puede mover también otras órdenes, así que se pide el listado
// completo (no una sola orden) y se aplica sin pedir confirmación.
const REFRESCOS_POST_ALTA = [2000, 5000, 10000]

function programarRefrescosPostAlta() {
  timersPostAlta.forEach(clearTimeout)
  timersPostAlta = REFRESCOS_POST_ALTA.map((ms) =>
    setTimeout(async () => {
      if (document.hidden) return
      await cargarOrdenes(true, true)
    }, ms),
  )
  // Pasada la ventana, lo que siga sin índice vuelve a leerse como
  // "Sin estimación": ya no es un cálculo en curso sino un dato que falta.
  timersPostAlta.push(
    setTimeout(() => {
      recienCreadas.value = []
    }, VENTANA_CALCULO_MS),
  )
}

function aplicarCambios() {
  if (!cambiosPendientes.value) return
  ordenes.value = cambiosPendientes.value
  firmaActual = firmaDe(cambiosPendientes.value)
  cambiosPendientes.value = null
  actualizadoEn.value = new Date()
  limpiarRecienCreadas(ordenes.value)
}

const horaActualizacion = computed(() =>
  actualizadoEn.value
    ? actualizadoEn.value.toLocaleTimeString('es-AR', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      })
    : '',
)

// "hace 3 h" / "hace 7 días": la antigüedad es un dato de decisión, no una
// fecha que el jefe tenga que restar mentalmente.
function hace(fecha: string | null): string {
  if (!fecha) return 'sin calcular'
  const minutos = Math.floor((Date.now() - new Date(fecha).getTime()) / 60000)
  if (minutos < 1) return 'recién'
  if (minutos < 60) return `hace ${minutos} min`
  const horas = Math.floor(minutos / 60)
  if (horas < 24) return `hace ${horas} h`
  const dias = Math.floor(horas / 24)
  return dias === 1 ? 'hace 1 día' : `hace ${dias} días`
}

function elegirCliente(c: Cliente) {
  clienteSeleccionado.value = c
}

// Un error de DRF llega como `{campo: ["mensaje"]}`. Mostrar el JSON crudo
// obliga al jefe a interpretar la estructura; acá se extraen los mensajes.
function mensajeDeError(data: unknown, fallback: string): string {
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (typeof data === 'object') {
    const mensajes = Object.values(data as Record<string, unknown>)
      .flat()
      .filter((v): v is string => typeof v === 'string')
    if (mensajes.length) return mensajes.join(' ')
  }
  return fallback
}

const creandoCliente = ref(false)

async function crearCliente() {
  if (creandoCliente.value) return // evita duplicar el cliente con doble click
  if (!nuevoCliente.value.razon_social || !nuevoCliente.value.telefono) return
  creandoCliente.value = true
  try {
    const { data } = await api.post('/clientes/', nuevoCliente.value)
    elegirCliente(data)
    nuevoCliente.value = { razon_social: '', telefono: '' }
    mostrarNuevoCliente.value = false
  } catch (e: any) {
    // Hallazgo E: el caso más común de error acá es teléfono duplicado
    // (ClienteSerializer.validate_telefono) — se muestra el mensaje del
    // backend tal cual en vez de un JSON crudo, para que el jefe de
    // taller entienda que probablemente ya existe ese cliente y lo
    // busque en vez de reintentar crear uno nuevo.
    errorForm.value = mensajeDeError(e?.response?.data, 'No se pudo crear el cliente. Revisá los datos e intentá de nuevo.')
  } finally {
    creandoCliente.value = false
  }
}

async function crearOrden() {
  if (!clienteSeleccionado.value) {
    errorForm.value = 'Buscá y elegí un cliente existente, o creá uno nuevo, antes de registrar la orden.'
    return
  }
  if (!tipoEquipoSeleccionado.value) {
    errorForm.value = 'Elegí el tipo de equipo.'
    return
  }
  const tipoEquipoFinal = tipoEquipoSeleccionado.value === OTRO_VALOR ? tipoEquipoOtro.value.trim() : tipoEquipoSeleccionado.value
  if (tipoEquipoSeleccionado.value === OTRO_VALOR && !tipoEquipoFinal) {
    errorForm.value = 'Especificá el tipo de equipo.'
    return
  }
  errorForm.value = ''
  guardando.value = true
  try {
    // CU-01: alta del equipo y de la orden en un solo POST atómico (el
    // backend crea el Equipo dentro de la misma transacción) — antes eran
    // dos requests separados y si el segundo fallaba quedaba un Equipo
    // huérfano sin ninguna orden asociada.
    const { data: creada } = await api.post('/ordenes/', {
      cliente: clienteSeleccionado.value.id,
      nuevo_tipo_equipo: tipoEquipoFinal,
      descripcion_falla: nuevaOrden.value.descripcion_falla,
      costo_estimado: nuevaOrden.value.costo_estimado,
      tiempo_estimado: nuevaOrden.value.tiempo_estimado,
      criticidad: nuevaOrden.value.criticidad,
    })

    recienCreadas.value = [...recienCreadas.value, creada.id]
    nuevaOrden.value = {
      descripcion_falla: '',
      costo_estimado: null,
      tiempo_estimado: null,
      criticidad: 2,
    }
    tipoEquipoSeleccionado.value = ''
    tipoEquipoOtro.value = ''
    clienteSeleccionado.value = null
    buscadorCliente.value?.limpiar()
    mostrarForm.value = false
    mensajeExito.value = 'Orden registrada. La prioridad se recalcula en unos segundos.'
    clearTimeout(timerExito)
    timerExito = setTimeout(() => {
      mensajeExito.value = ''
    }, 6000)
    await cargarOrdenes()
    programarRefrescosPostAlta()
  } catch (e: any) {
    errorForm.value = mensajeDeError(e?.response?.data, 'No se pudo registrar la orden. Revisá los datos e intentá de nuevo.')
  } finally {
    guardando.value = false
  }
}

// CU-08: sin filtro, el listado se separa en tres grupos. Las activas
// vienen ordenadas por prioridad desde el backend; las bloqueadas no
// compiten en el orden y se muestran aparte con su motivo.
const activas = computed(() => ordenes.value.filter((o) => o.estado === 'pendiente' || o.estado === 'en_curso'))
const bloqueadas = computed(() => ordenes.value.filter((o) => o.estado === 'bloqueado'))
const terminadas = computed(() => ordenes.value.filter((o) => o.estado === 'terminado'))

// Momento en que el motor recalculó por última vez el orden de las activas.
const prioridadActualizada = computed(() => {
  const fechas = activas.value.map((o) => o.prioridad_actualizada).filter((f): f is string => !!f)
  if (!fechas.length) return ''
  const ultima = fechas.reduce((a, b) => (new Date(a) > new Date(b) ? a : b))
  return `recalculada ${hace(ultima)}`
})

// Una orden recién creada sin índice todavía está esperando al motor, no
// "sin estimación" (eso es un dato que el usuario no cargó).
function estaCalculando(o: OrdenListado) {
  return o.indice_prioridad == null && recienCreadas.value.includes(o.id)
}

// Con IA se marca con una estrella junto al puntaje; la regla de respaldo no
// lleva chip: su ausencia es la señal, y el detalle lo dice con palabras.

// La IA responde unos segundos después de cada cambio: se refresca el
// listado cada 30 segundos para que el nuevo orden aparezca solo.
watch(filtroEstado, (estado) => {
  router.replace({ query: estado ? { estado } : {} })
  cargarOrdenes()
})

// La IA responde unos segundos después de cada cambio: se consulta cada 30
// segundos, pero sin re-ordenar la pantalla por debajo del usuario.
let refresco: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  cargarOrdenes()
  refresco = setInterval(() => {
    if (mostrarForm.value || document.hidden) return
    cargarOrdenes(true)
  }, 30000)
})
onUnmounted(() => {
  clearInterval(refresco)
  clearTimeout(timerExito)
  timersPostAlta.forEach(clearTimeout)
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>Órdenes de trabajo</h2>
      <button v-if="auth.esJefe" class="btn-icono" :class="{ 'boton-secundario': mostrarForm }" @click="mostrarForm = !mostrarForm">
        <IconClose v-if="mostrarForm" aria-hidden="true" />
        <IconAdd v-else aria-hidden="true" />
        {{ mostrarForm ? 'Cancelar' : 'Nueva orden' }}
      </button>
    </div>

    <form v-if="mostrarForm && auth.esJefe" class="nueva-orden" @submit.prevent="crearOrden">
      <div class="cliente-picker">
        <BuscadorCombobox
          ref="buscadorCliente"
          v-model="clienteSeleccionado"
          class="combo-cliente"
          :cargar="cargarClientes"
          :etiqueta="etiquetaCliente"
          :clave="claveCliente"
          etiqueta-accesible="Buscar cliente por nombre o teléfono"
          placeholder="Buscar cliente por nombre o teléfono…"
          name="cliente"
          mensaje-error="No se pudo buscar clientes. Reintentá escribiendo de nuevo."
        />
        <button type="button" class="link-btn" @click="mostrarNuevoCliente = !mostrarNuevoCliente">
          {{ mostrarNuevoCliente ? 'Cancelar' : '+ Nuevo cliente' }}
        </button>
      </div>

      <div v-if="mostrarNuevoCliente" class="nuevo-cliente">
        <input v-model="nuevoCliente.razon_social" aria-label="Razón social o nombre del cliente" placeholder="Razón social / nombre" />
        <input v-model="nuevoCliente.telefono" aria-label="Teléfono del cliente" placeholder="Teléfono (para WhatsApp)" />
        <button type="button" :disabled="creandoCliente" @click="crearCliente">
          {{ creandoCliente ? 'Guardando…' : 'Guardar cliente' }}
        </button>
      </div>

      <label class="campo">
        <span>Tipo de equipo</span>
        <select v-model="tipoEquipoSeleccionado" required>
          <option value="" disabled>Elegí un tipo</option>
          <option v-for="t in TIPOS_EQUIPO" :key="t" :value="t">{{ t }}</option>
          <option :value="OTRO_VALOR">Otro (especificar)</option>
        </select>
      </label>
      <label v-if="tipoEquipoSeleccionado === OTRO_VALOR" class="campo">
        <span>¿Cuál?</span>
        <input v-model="tipoEquipoOtro" placeholder="Ej.: enfriador de aceite" required />
      </label>
      <label class="campo campo-ancho">
        <span>Descripción del problema</span>
        <input v-model="nuevaOrden.descripcion_falla" placeholder="Qué falla y qué se observó" required />
      </label>
      <label class="campo">
        <span>Costo estimado (opcional)</span>
        <input v-model.number="nuevaOrden.costo_estimado" type="number" min="0" placeholder="Ej.: 150000" />
      </label>
      <label class="campo">
        <span>Tiempo estimado en horas (opcional)</span>
        <input v-model.number="nuevaOrden.tiempo_estimado" type="number" min="0.1" step="0.1" placeholder="Ej.: 2.5" />
      </label>
      <p class="hint-estimacion campo-ancho">Sin costo y tiempo estimado, la orden no entra en el orden sugerido.</p>
      <label class="campo campo-ancho">
        <span>Criticidad del trabajo</span>
        <select v-model.number="nuevaOrden.criticidad">
          <option :value="1">Puede esperar</option>
          <option :value="2">Normal</option>
          <option :value="3">Normal-alta</option>
          <option :value="4">Urgente</option>
          <option :value="5">Muy urgente</option>
        </select>
      </label>

      <p v-if="errorForm" class="error" role="alert">{{ errorForm }}</p>
      <button type="submit" :disabled="guardando">{{ guardando ? 'Guardando…' : 'Registrar' }}</button>
    </form>

    <div class="filtros">
      <label>
        Estado:
        <select v-model="filtroEstado">
          <option value="">Todos</option>
          <option value="pendiente">Pendiente</option>
          <option value="en_curso">En curso</option>
          <option value="bloqueado">Bloqueado</option>
          <option value="terminado">Terminado</option>
        </select>
      </label>
      <span v-if="horaActualizacion" class="actualizado">
        Listado {{ horaActualizacion }}<template v-if="prioridadActualizada"> · prioridad {{ prioridadActualizada }}</template>
      </span>
    </div>

    <div v-if="mensajeExito" class="aviso aviso-exito" role="status">
      {{ mensajeExito }}
    </div>

    <div v-if="errorCarga" class="aviso aviso-error" role="alert">
      {{ errorCarga }}
      <button type="button" class="link-btn reintentar" @click="cargarOrdenes()">Reintentar</button>
    </div>

    <div v-if="cambiosPendientes" class="aviso aviso-cambio" role="status">
      El orden de prioridad cambió.
      <button type="button" class="link-btn" @click="aplicarCambios">Actualizar listado</button>
    </div>

    <p v-if="cargando && ordenes.length === 0 && !errorCarga" role="status" aria-live="polite">Cargando órdenes…</p>

    <template v-else-if="!filtroEstado && (!errorCarga || ordenes.length)">
      <h3 class="grupo">Activas, en orden de prioridad sugerida</h3>
      <table class="tabla-ordenes">
        <caption class="sr-only">
          Órdenes activas en el orden de prioridad sugerido
        </caption>
        <thead>
          <tr>
            <th scope="col" class="col-rango">#</th>
            <th scope="col" class="col-orden">Orden</th>
            <th scope="col">Cliente</th>
            <th scope="col" class="col-edad">Ingresó</th>
            <th scope="col" class="col-equipo">Equipo</th>
            <th scope="col" class="col-estado">Estado</th>
            <th scope="col" class="col-prioridad">Prioridad</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="(o, i) in activas" :key="o.id">
            <tr class="fila-orden">
              <td class="rango td-rango">{{ i + 1 }}</td>
              <td class="td-orden">
                <router-link class="orden-link" :to="{ name: 'orden-detalle', params: { id: o.id } }"> OT-{{ String(o.id).padStart(4, '0') }} </router-link>
              </td>
              <td class="td-cliente">
                <span class="cliente-nombre" :title="o.cliente_nombre">{{ o.cliente_nombre }}</span>
                <span class="fila-meta">
                  <span class="badge" :class="`badge-${o.estado}`">{{ etiquetaEstado(o.estado) }}</span>
                  <span class="edad">{{ hace(o.fecha_ingreso) }}</span>
                </span>
              </td>
              <td class="edad col-edad">{{ hace(o.fecha_ingreso) }}</td>
              <td class="col-equipo" :title="o.tipo_equipo ?? ''">{{ o.tipo_equipo ?? '-' }}</td>
              <td class="col-estado">
                <span class="badge" :class="`badge-${o.estado}`">{{ etiquetaEstado(o.estado) }}</span>
              </td>
              <td class="td-prioridad">
                <template v-if="o.indice_prioridad != null">
                  {{ Math.round(o.indice_prioridad) }}<span class="escala">/100</span>
                  <span v-if="o.prioridad_origen === 'ia'" class="origen-ia" title="Prioridad sugerida por IA">
                    <IconSparkle aria-hidden="true" />
                    <span class="sr-only">Prioridad sugerida por IA</span>
                  </span>
                </template>
                <span v-else-if="estaCalculando(o)" class="chip-calculando">Calculando prioridad…</span>
                <span v-else class="chip-sin-estimacion">Sin estimación</span>
              </td>
            </tr>
            <tr v-if="o.justificacion_prioridad" class="fila-justificacion">
              <td></td>
              <td colspan="6">
                <span class="sr-only">Justificación de la prioridad: </span>
                {{ o.justificacion_prioridad }}
              </td>
            </tr>
          </template>
          <tr v-if="activas.length === 0">
            <td colspan="7">
              No hay órdenes activas.
              <template v-if="auth.esJefe"> Registrá una con «Nueva orden».</template>
              <template v-else> Cuando el jefe registre una, va a aparecer acá.</template>
            </td>
          </tr>
        </tbody>
      </table>

      <template v-if="bloqueadas.length">
        <h3 class="grupo">Bloqueadas</h3>
        <table class="tabla-secundaria tabla-bloqueadas">
          <caption class="sr-only">
            Órdenes bloqueadas y su motivo
          </caption>
          <thead>
            <tr>
              <th scope="col">Orden</th>
              <th scope="col">Cliente</th>
              <th scope="col" class="col-edad">Ingresó</th>
              <th scope="col" class="col-equipo">Equipo</th>
              <th scope="col">Motivo</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="o in bloqueadas" :key="o.id" class="fila-orden">
              <td>
                <router-link class="orden-link" :to="{ name: 'orden-detalle', params: { id: o.id } }"> OT-{{ String(o.id).padStart(4, '0') }} </router-link>
              </td>
              <td>{{ o.cliente_nombre }}</td>
              <td class="edad col-edad">{{ hace(o.fecha_ingreso) }}</td>
              <td class="col-equipo" :title="o.tipo_equipo ?? ''">{{ o.tipo_equipo ?? '-' }}</td>
              <td class="motivo">{{ o.motivo_bloqueo }}</td>
            </tr>
          </tbody>
        </table>
      </template>

      <details v-if="terminadas.length" class="terminadas">
        <summary>Terminadas ({{ terminadas.length }})</summary>
        <table class="tabla-secundaria tabla-terminadas">
          <caption class="sr-only">
            Órdenes terminadas
          </caption>
          <thead>
            <tr>
              <th scope="col">Orden</th>
              <th scope="col">Cliente</th>
              <th scope="col">Equipo</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="o in terminadas" :key="o.id" class="fila-orden">
              <td>
                <router-link class="orden-link" :to="{ name: 'orden-detalle', params: { id: o.id } }"> OT-{{ String(o.id).padStart(4, '0') }} </router-link>
              </td>
              <td>{{ o.cliente_nombre }}</td>
              <td class="col-equipo" :title="o.tipo_equipo ?? ''">{{ o.tipo_equipo ?? '-' }}</td>
            </tr>
          </tbody>
        </table>
      </details>
    </template>

    <table v-else-if="!errorCarga || ordenes.length" class="tabla-ordenes">
      <caption class="sr-only">
        Órdenes filtradas por estado
      </caption>
      <thead>
        <tr>
          <th scope="col" class="col-rango">#</th>
          <th scope="col" class="col-orden">Orden</th>
          <th scope="col">Cliente</th>
          <th scope="col" class="col-edad">Ingresó</th>
          <th scope="col" class="col-equipo">Equipo</th>
          <th scope="col" class="col-estado">Estado</th>
          <th scope="col" class="col-prioridad">Prioridad</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="(o, i) in ordenes" :key="o.id">
          <tr class="fila-orden">
            <td class="rango td-rango">{{ i + 1 }}</td>
            <td class="td-orden">
              <router-link class="orden-link" :to="{ name: 'orden-detalle', params: { id: o.id } }"> OT-{{ String(o.id).padStart(4, '0') }} </router-link>
            </td>
            <td class="td-cliente">
              <span class="cliente-nombre" :title="o.cliente_nombre">{{ o.cliente_nombre }}</span>
              <span class="fila-meta">
                <span class="badge" :class="`badge-${o.estado}`">{{ etiquetaEstado(o.estado) }}</span>
                <span class="edad">{{ hace(o.fecha_ingreso) }}</span>
              </span>
            </td>
            <td class="edad col-edad">{{ hace(o.fecha_ingreso) }}</td>
            <td class="col-equipo" :title="o.tipo_equipo ?? ''">{{ o.tipo_equipo ?? '-' }}</td>
            <td class="col-estado">
              <span class="badge" :class="`badge-${o.estado}`">{{ etiquetaEstado(o.estado) }}</span>
              <span v-if="o.motivo_bloqueo" class="motivo"> · {{ o.motivo_bloqueo }}</span>
            </td>
            <td class="td-prioridad">
              <template v-if="o.indice_prioridad != null">
                {{ Math.round(o.indice_prioridad) }}<span class="escala">/100</span>
                <span v-if="o.prioridad_origen === 'ia'" class="origen-ia" title="Prioridad sugerida por IA">
                  <IconSparkle aria-hidden="true" />
                  <span class="sr-only">Prioridad sugerida por IA</span>
                </span>
              </template>
              <span v-else-if="estaCalculando(o)" class="chip-calculando">Calculando prioridad…</span>
              <span v-else class="chip-sin-estimacion">Sin estimación</span>
            </td>
          </tr>
          <tr v-if="o.justificacion_prioridad" class="fila-justificacion">
            <td></td>
            <td colspan="6">
              <span class="sr-only">Justificación de la prioridad: </span>
              {{ o.justificacion_prioridad }}
            </td>
          </tr>
        </template>
        <tr v-if="ordenes.length === 0">
          <td colspan="7">
            No hay órdenes con ese estado.
            <button type="button" class="link-btn" @click="filtroEstado = ''">Ver todas</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.page {
  max-width: 900px;
  margin: 2rem auto;
  padding: 0 1rem;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.nueva-orden {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
  background: white;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
}
.campo {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: #334155;
}
.campo-ancho {
  grid-column: 1 / -1;
}
.campo input,
.campo select {
  font-weight: 400;
  color: #0f172a;
}
.hint-estimacion {
  margin: -0.25rem 0 0;
  color: #b45309;
  font-size: 0.8rem;
}
.escala {
  color: #64748b;
  font-size: 0.8rem;
}
.chip-sin-estimacion {
  color: #b45309;
  border: 1px solid currentColor;
  border-radius: 4px;
  padding: 0 0.3rem;
  font-size: 0.7rem;
  white-space: nowrap;
}
/* Neutro a propósito: esperar al motor no es un dato faltante ni un error. */
.chip-calculando {
  color: #64748b;
  border: 1px solid currentColor;
  border-radius: 4px;
  padding: 0 0.3rem;
  font-size: 0.7rem;
  white-space: nowrap;
}
.cliente-picker {
  grid-column: 1 / -1;
  position: relative;
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.combo-cliente {
  flex: 1;
  min-width: 0;
}
.link-btn {
  background: none;
  color: #0f172a;
  text-decoration: underline;
  padding: 0.2rem 0.4rem;
  font-size: 0.8rem;
}
.reintentar {
  background: #0f172a;
  color: white;
  text-decoration: none;
  padding: 0.35rem 0.75rem;
}
.nuevo-cliente {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 0.5rem;
  background: #f1f5f9;
  padding: 0.75rem;
  border-radius: 6px;
}
.filtros {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
  font-size: 0.85rem;
}
.actualizado {
  color: #64748b;
  font-size: 0.8rem;
}
.aviso {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  font-size: 0.85rem;
  margin-bottom: 1rem;
}
.aviso-error {
  background: #fee2e2;
  color: #991b1b;
}
.aviso-cambio {
  background: #f1f5f9;
  color: #334155;
}
.aviso-exito {
  background: #dcfce7;
  color: #166534;
}
.motivo {
  color: #991b1b;
  font-size: 0.8rem;
}
.fila-orden {
  position: relative;
  & td {
    border: none;
  }
}
.fila-orden:hover,
.fila-orden:focus-within {
  background: #f1f5f9;
}
.rango {
  font-variant-numeric: tabular-nums;
  color: #475569;
}
.orden-link {
  color: inherit;
  font-weight: 600;
  text-decoration: none;
  /* Un código OT es un solo token: se dicta y se escribe a mano, así que no
     puede partirse en "OT-" / "0001". */
  white-space: nowrap;

  &::before {
    content: '';
    display: block;
    position: absolute;
    inset: 0;
  }
}
.orden-link:hover {
  text-decoration: underline;
}
.orden-link:focus-visible {
  outline: 2px solid #0f172a;
  outline-offset: 2px;
  border-radius: 4px;
}
.grupo {
  font-size: 0.95rem;
  margin: 1.25rem 0 0.5rem;
}
.edad {
  color: #475569;
  font-size: 0.8rem;
  white-space: nowrap;
}
.origen-ia {
  display: inline-flex;
  align-items: center;
  margin-left: 0.25rem;
  vertical-align: -0.15em;
  color: #3b82f6;
}
.origen-ia svg {
  width: 0.9em;
  height: 0.9em;
  display: block;
}
.fila-justificacion td {
  font-size: 0.8rem;
  color: #475569;
  padding-top: 0;
  border-top: none;
}
.terminadas {
  margin-top: 1.25rem;
  font-size: 0.9rem;
}

/* Anchos fijos: el código OT y el puntaje no cambian de lugar entre filas, y
   los textos largos (cliente, equipo, motivo) recortan con elipsis en vez de
   romper el ritmo de columnas. */
.tabla-ordenes,
.tabla-secundaria {
  table-layout: fixed;
}
.tabla-ordenes .col-rango {
  width: 2rem;
}
.tabla-ordenes .col-orden {
  width: 6rem;
}
.tabla-ordenes .col-edad {
  width: 5.5rem;
}
.tabla-ordenes .col-equipo {
  width: 8rem;
}
.tabla-ordenes .col-estado {
  width: 7rem;
}
.tabla-ordenes .col-prioridad {
  width: 7rem;
}
.tabla-ordenes .col-equipo,
.tabla-ordenes .td-cliente,
.tabla-bloqueadas td:nth-child(2),
.tabla-terminadas td:nth-child(2) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tabla-secundaria th:first-child,
.tabla-secundaria td:first-child {
  width: 6rem;
}
.tabla-bloqueadas .col-edad {
  width: 5.5rem;
}
.tabla-bloqueadas .col-equipo,
.tabla-terminadas .col-equipo {
  width: 8rem;
}
.cliente-nombre {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.error {
  grid-column: 1 / -1;
  color: #991b1b;
  font-size: 0.85rem;
  margin: 0;
}

/* En escritorio el estado y la antigüedad tienen su propia columna; en el
   celular viajan debajo del cliente para no perderlos al colapsar la tabla. */
.fila-meta {
  display: none;
}

.tabla-ordenes .td-prioridad {
  text-align: right;
}

@media (max-width: 640px) {
  .page {
    margin: 1rem auto;
  }
  .page-header {
    gap: 0.5rem;
  }
  .nueva-orden,
  .nuevo-cliente {
    grid-template-columns: 1fr;
  }
  .cliente-picker {
    flex-wrap: wrap;
  }
  .combo-cliente {
    flex-basis: 100%;
  }
  .terminadas summary {
    display: flex;
    align-items: center;
    min-height: 44px;
  }
  .filtros {
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  /* La tabla prioriza rank, orden, cliente y puntaje: lo demás se lee en el
     detalle o en la línea de metadatos. */
  .col-equipo,
  .col-estado,
  .col-edad {
    display: none;
  }
  table th,
  table td {
    padding: 0.6rem 0.4rem;
  }

  /* En el celular la tabla se lee como una lista: cada orden es una tarjeta
     de tres líneas —rango/OT/puntaje, cliente, estado/antigüedad/origen— en
     vez de siete columnas comprimidas. */
  .tabla-ordenes,
  .tabla-ordenes tbody {
    display: block;
  }
  .tabla-ordenes thead {
    display: none;
  }
  .tabla-ordenes tr.fila-orden {
    display: grid;
    grid-template-columns: 1.25rem 1fr auto;
    grid-template-areas:
      'rango orden prioridad'
      'cliente cliente cliente'
      'meta meta meta';
    align-items: center;
    column-gap: 0.5rem;
    row-gap: 0;
    padding: 0.4rem;
    line-height: 1.35;
    border-top: 1px solid #e2e8f0;
  }
  .tabla-ordenes tr.fila-orden:hover,
  .tabla-ordenes tr.fila-orden:focus-within {
    background: #f1f5f9;
  }
  .tabla-ordenes tr.fila-orden td {
    padding: 0;
    border: none;
  }
  .tabla-ordenes .td-rango {
    grid-area: rango;
  }
  .tabla-ordenes .td-orden {
    grid-area: orden;
  }
  .tabla-ordenes .td-prioridad {
    grid-area: prioridad;
    text-align: right;
  }
  .tabla-ordenes .td-cliente {
    display: contents;
  }
  .tabla-ordenes tr.fila-justificacion {
    display: block;
    padding: 0 0.4rem 0.6rem;
    border: none;
  }
  .tabla-ordenes tr.fila-justificacion td {
    display: block;
    padding: 0;
    border: none;
  }
  .tabla-ordenes tr.fila-justificacion td:first-child {
    display: none;
  }
  .tabla-ordenes tbody > tr:not(.fila-orden):not(.fila-justificacion) {
    display: block;
    padding: 0.75rem 0.4rem;
    border-top: 1px solid #e2e8f0;
  }
  .tabla-ordenes tbody > tr:not(.fila-orden):not(.fila-justificacion) td {
    display: block;
    padding: 0;
    border: none;
  }

  .fila-meta {
    display: flex;
    align-items: center;
    flex-wrap: nowrap;
    gap: 0.4rem;
    margin-top: 0;
    overflow: hidden;
    grid-area: meta;
  }
  .cliente-nombre {
    grid-area: cliente;
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .chip-sin-estimacion {
    display: inline-block;
    margin-top: 0.2rem;
  }
}
</style>
