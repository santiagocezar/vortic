<script setup lang="ts">
// HU-01 (registrar ingreso), HU-02 (autocompletar cliente existente al
// escribir), HU-05 (consultar trabajos del día) y HU-13 (ver prioridad
// sugerida) en una sola vista: el listado viene ordenado por
// indice_prioridad (default del ViewSet) y desde acá se da de alta
// cliente + orden.
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/client'
import { useAuthStore } from '../stores/auth'

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
}

const ordenes = ref<OrdenListado[]>([])
const filtroEstado = ref('')
const cargando = ref(false)
const mostrarForm = ref(false)
const guardando = ref(false)
const errorForm = ref('')

// HU-02: buscador de cliente existente (en vez de un <select> con todos
// los clientes) — a medida que se escribe, sugiere coincidencias por
// razón social o teléfono; si no existe, se puede cargar uno nuevo.
const busquedaCliente = ref('')
const sugerenciasCliente = ref<Cliente[]>([])
const clienteSeleccionado = ref<Cliente | null>(null)
let debounceCliente: ReturnType<typeof setTimeout> | undefined

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

async function cargarOrdenes() {
  cargando.value = true
  try {
    const params = filtroEstado.value ? { estado: filtroEstado.value } : {}
    const { data } = await api.get('/ordenes/', { params })
    ordenes.value = data
  } catch {
    // Si el token venció y el refresh también falla, el interceptor de
    // api/client.ts ya redirige al login — acá solo evitamos que la
    // pantalla se quede en "Cargando…" para siempre por un error de red.
  } finally {
    cargando.value = false
  }
}

// Guarda de "respuesta obsoleta": si el usuario sigue tipeando, una
// búsqueda vieja que tarda más puede resolver DESPUÉS de una más nueva y
// pisarle el resultado con sugerencias de un texto que ya no está en el
// input. Cada búsqueda lleva un número de secuencia y solo se aplica si
// sigue siendo la más reciente cuando responde.
let secuenciaBusquedaCliente = 0

function onBuscarClienteInput() {
  clienteSeleccionado.value = null
  clearTimeout(debounceCliente)
  const q = busquedaCliente.value.trim()
  if (q.length < 2) {
    sugerenciasCliente.value = []
    return
  }
  const idBusqueda = ++secuenciaBusquedaCliente
  debounceCliente = setTimeout(async () => {
    const { data } = await api.get('/clientes/', { params: { search: q } })
    if (idBusqueda === secuenciaBusquedaCliente) {
      sugerenciasCliente.value = data
    }
  }, 250)
}

function elegirCliente(c: Cliente) {
  clienteSeleccionado.value = c
  busquedaCliente.value = `${c.razon_social} (${c.telefono})`
  sugerenciasCliente.value = []
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
    const detalle = e?.response?.data?.telefono?.[0] ?? e?.response?.data?.razon_social?.[0]
    errorForm.value = detalle ?? (e?.response?.data ? JSON.stringify(e.response.data) : 'No se pudo crear el cliente.')
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
  const tipoEquipoFinal = tipoEquipoSeleccionado.value === OTRO_VALOR
    ? tipoEquipoOtro.value.trim()
    : tipoEquipoSeleccionado.value
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
    await api.post('/ordenes/', {
      cliente: clienteSeleccionado.value.id,
      nuevo_tipo_equipo: tipoEquipoFinal,
      descripcion_falla: nuevaOrden.value.descripcion_falla,
      costo_estimado: nuevaOrden.value.costo_estimado,
      tiempo_estimado: nuevaOrden.value.tiempo_estimado,
      criticidad: nuevaOrden.value.criticidad,
    })

    nuevaOrden.value = {
      descripcion_falla: '',
      costo_estimado: null, tiempo_estimado: null, criticidad: 2,
    }
    tipoEquipoSeleccionado.value = ''
    tipoEquipoOtro.value = ''
    busquedaCliente.value = ''
    clienteSeleccionado.value = null
    mostrarForm.value = false
    await cargarOrdenes()
  } catch (e: any) {
    errorForm.value = e?.response?.data
      ? JSON.stringify(e.response.data)
      : 'No se pudo registrar la orden.'
  } finally {
    guardando.value = false
  }
}

// CU-08: sin filtro, el listado se separa en tres grupos. Las activas
// vienen ordenadas por prioridad desde el backend; las bloqueadas no
// compiten en el orden y se muestran aparte con su motivo.
const activas = computed(() => ordenes.value.filter(o => o.estado === 'pendiente' || o.estado === 'en_curso'))
const bloqueadas = computed(() => ordenes.value.filter(o => o.estado === 'bloqueado'))
const terminadas = computed(() => ordenes.value.filter(o => o.estado === 'terminado'))

function etiquetaOrigen(o: OrdenListado) {
  return o.prioridad_origen === 'ia' ? 'IA' : o.prioridad_origen === 'respaldo' ? 'Regla' : ''
}

// La IA responde unos segundos después de cada cambio: se refresca el
// listado cada 30 segundos para que el nuevo orden aparezca solo.
let refresco: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  cargarOrdenes()
  refresco = setInterval(() => { if (!mostrarForm.value) cargarOrdenes() }, 30000)
})
onUnmounted(() => clearInterval(refresco))
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>Órdenes de trabajo</h2>
      <button v-if="auth.esJefe" @click="mostrarForm = !mostrarForm">
        {{ mostrarForm ? 'Cancelar' : '+ Nueva orden' }}
      </button>
    </div>

    <form v-if="mostrarForm && auth.esJefe" class="nueva-orden" @submit.prevent="crearOrden">
      <div class="cliente-picker">
        <input
          v-model="busquedaCliente"
          placeholder="Buscar cliente por nombre o teléfono…"
          @input="onBuscarClienteInput"
        />
        <ul v-if="sugerenciasCliente.length" class="sugerencias">
          <li v-for="c in sugerenciasCliente" :key="c.id" @click="elegirCliente(c)">
            {{ c.razon_social }} — {{ c.telefono }}
          </li>
        </ul>
        <button type="button" class="link-btn" @click="mostrarNuevoCliente = !mostrarNuevoCliente">
          {{ mostrarNuevoCliente ? 'cancelar' : '+ nuevo cliente' }}
        </button>
      </div>

      <div v-if="mostrarNuevoCliente" class="nuevo-cliente">
        <input v-model="nuevoCliente.razon_social" placeholder="Razón social / nombre" />
        <input v-model="nuevoCliente.telefono" placeholder="Teléfono (para WhatsApp)" />
        <button type="button" :disabled="creandoCliente" @click="crearCliente">
          {{ creandoCliente ? 'Guardando…' : 'Guardar cliente' }}
        </button>
      </div>

      <select v-model="tipoEquipoSeleccionado" required>
        <option value="" disabled>Tipo de equipo…</option>
        <option v-for="t in TIPOS_EQUIPO" :key="t" :value="t">{{ t }}</option>
        <option :value="OTRO_VALOR">Otro (especificar)</option>
      </select>
      <input
        v-if="tipoEquipoSeleccionado === OTRO_VALOR"
        v-model="tipoEquipoOtro"
        placeholder="¿Cuál tipo de equipo?"
        required
      />
      <input v-model="nuevaOrden.descripcion_falla" placeholder="Descripción del problema" required />
      <input v-model.number="nuevaOrden.costo_estimado" type="number" min="0" placeholder="Costo estimado" />
      <input
        v-model.number="nuevaOrden.tiempo_estimado"
        type="number"
        min="0.1"
        step="0.5"
        placeholder="Tiempo estimado (hs, mínimo 0,1)"
      />
      <select v-model.number="nuevaOrden.criticidad">
        <option :value="1">Criticidad del trabajo: puede esperar</option>
        <option :value="2">Criticidad del trabajo: normal</option>
        <option :value="3">Criticidad del trabajo: normal-alta</option>
        <option :value="4">Criticidad del trabajo: urgente</option>
        <option :value="5">Criticidad del trabajo: muy urgente</option>
      </select>

      <p v-if="errorForm" class="error">{{ errorForm }}</p>
      <button type="submit" :disabled="guardando">{{ guardando ? 'Guardando…' : 'Registrar' }}</button>
    </form>

    <div class="filtros">
      <label>
        Estado:
        <select v-model="filtroEstado" @change="cargarOrdenes">
          <option value="">Todos</option>
          <option value="pendiente">Pendiente</option>
          <option value="en_curso">En curso</option>
          <option value="bloqueado">Bloqueado</option>
          <option value="terminado">Terminado</option>
        </select>
      </label>
    </div>

    <p v-if="cargando && ordenes.length === 0">Cargando…</p>

    <template v-else-if="!filtroEstado">
      <h3 class="grupo">Activas, en orden de prioridad sugerida</h3>
      <table>
        <thead>
          <tr><th>#</th><th>Orden</th><th>Cliente</th><th>Equipo</th><th>Estado</th><th>Prioridad</th></tr>
        </thead>
        <tbody>
          <template v-for="(o, i) in activas" :key="o.id">
            <tr class="fila-orden" @click="router.push({ name: 'orden-detalle', params: { id: o.id } })">
              <td>{{ i + 1 }}</td>
              <td>OT-{{ String(o.id).padStart(4, '0') }}</td>
              <td>{{ o.cliente_nombre }}</td>
              <td>{{ o.tipo_equipo ?? '-' }}</td>
              <td><span class="badge" :class="`badge-${o.estado}`">{{ o.estado }}</span></td>
              <td>
                {{ o.indice_prioridad != null ? Math.round(o.indice_prioridad) : '-' }}
                <span v-if="etiquetaOrigen(o)" class="origen">{{ etiquetaOrigen(o) }}</span>
              </td>
            </tr>
            <tr v-if="o.justificacion_prioridad" class="fila-justificacion">
              <td></td>
              <td colspan="5">{{ o.justificacion_prioridad }}</td>
            </tr>
          </template>
          <tr v-if="activas.length === 0"><td colspan="6">No hay órdenes activas.</td></tr>
        </tbody>
      </table>

      <template v-if="bloqueadas.length">
        <h3 class="grupo">Bloqueadas</h3>
        <table>
          <thead><tr><th>Orden</th><th>Cliente</th><th>Equipo</th><th>Motivo</th></tr></thead>
          <tbody>
            <tr v-for="o in bloqueadas" :key="o.id" class="fila-orden" @click="router.push({ name: 'orden-detalle', params: { id: o.id } })">
              <td>OT-{{ String(o.id).padStart(4, '0') }}</td>
              <td>{{ o.cliente_nombre }}</td>
              <td>{{ o.tipo_equipo ?? '-' }}</td>
              <td class="motivo">{{ o.motivo_bloqueo }}</td>
            </tr>
          </tbody>
        </table>
      </template>

      <details v-if="terminadas.length" class="terminadas">
        <summary>Terminadas ({{ terminadas.length }})</summary>
        <table>
          <tbody>
            <tr v-for="o in terminadas" :key="o.id" class="fila-orden" @click="router.push({ name: 'orden-detalle', params: { id: o.id } })">
              <td>OT-{{ String(o.id).padStart(4, '0') }}</td>
              <td>{{ o.cliente_nombre }}</td>
              <td>{{ o.tipo_equipo ?? '-' }}</td>
            </tr>
          </tbody>
        </table>
      </details>
    </template>

    <table v-else>
      <thead>
        <tr><th>Orden</th><th>Cliente</th><th>Equipo</th><th>Estado</th><th>Prioridad</th></tr>
      </thead>
      <tbody>
        <tr v-for="o in ordenes" :key="o.id" class="fila-orden" @click="router.push({ name: 'orden-detalle', params: { id: o.id } })">
          <td>OT-{{ String(o.id).padStart(4, '0') }}</td>
          <td>{{ o.cliente_nombre }}</td>
          <td>{{ o.tipo_equipo ?? '-' }}</td>
          <td>
            <span class="badge" :class="`badge-${o.estado}`">{{ o.estado }}</span>
            <span v-if="o.motivo_bloqueo" class="motivo"> · {{ o.motivo_bloqueo }}</span>
          </td>
          <td>{{ o.indice_prioridad != null ? Math.round(o.indice_prioridad) : '-' }}</td>
        </tr>
        <tr v-if="ordenes.length === 0"><td colspan="5">No hay órdenes con ese estado.</td></tr>
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
.cliente-picker {
  grid-column: 1 / -1;
  position: relative;
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.cliente-picker input {
  flex: 1;
}
.sugerencias {
  position: absolute;
  z-index: 10;
  top: 100%;
  left: 0;
  right: 6.5rem;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  max-height: 200px;
  overflow-y: auto;
  list-style: none;
  margin: 0.25rem 0 0;
  padding: 0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}
.sugerencias li {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid #f1f5f9;
  cursor: pointer;
  font-size: 0.85rem;
}
.sugerencias li:hover {
  background: #f1f5f9;
}
.link-btn {
  background: none;
  color: #0f172a;
  text-decoration: underline;
  padding: 0.2rem 0.4rem;
  font-size: 0.8rem;
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
  margin-bottom: 1rem;
  font-size: 0.85rem;
}
.motivo {
  color: #991b1b;
  font-size: 0.8rem;
}
.fila-orden {
  cursor: pointer;
}
.fila-orden:hover {
  background: #f1f5f9;
}
.grupo {
  font-size: 0.95rem;
  margin: 1.25rem 0 0.5rem;
}
.origen {
  font-size: 0.7rem;
  border: 1px solid #94a3b8;
  border-radius: 4px;
  padding: 0 0.3rem;
  margin-left: 0.3rem;
  color: #475569;
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
.error {
  grid-column: 1 / -1;
  color: #991b1b;
  font-size: 0.85rem;
  margin: 0;
}
</style>
