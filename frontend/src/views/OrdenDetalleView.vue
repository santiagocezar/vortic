<script setup lang="ts">
// Detalle de una orden: cambiar estado (CU-02/HU-03/HU-04), registrar
// repuestos y horas (CU-04/HU-07/HU-08), avisar al cliente (CU-05/HU-09).
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api/client'
import { useAuthStore } from '../stores/auth'
import { FEATURE_STOCK_PROVEEDORES } from '../config/features'

const auth = useAuthStore()

interface PrecioProveedor {
  id: number
  proveedor: number
  proveedor_nombre: string
  precio_costo: string
}

interface Repuesto {
  id: number
  codigo: string
  descripcion: string
  cantidad_actual: number
  cantidad_minima: number
  stock_bajo: boolean
  precios_proveedor: PrecioProveedor[]
}

interface OrdenRepuesto {
  id: number
  repuesto: number | null
  repuesto_detalle: Repuesto | null
  descripcion_encargo: string | null
  cantidad: number
  proveedor_nombre: string | null
  precio_costo: string | null
  precio_venta: string | null
}

// Una fila del buscador: "este repuesto, comprado a este proveedor a este
// precio" (o sin proveedor, si el repuesto todavía no tiene ninguna lista
// cargada). Elegir una fila fija cuál precio_proveedor_id se manda —
// nunca se autoselecciona el más barato, eso lo decide quien carga la orden.
interface SugerenciaRepuesto {
  key: string
  label: string
  repuestoId: number
  precioProveedorId: number | null
  stockActual: number
}

interface SesionHoras {
  id: number
  horas: number
  fecha_registro: string
  usuario_username: string
}

interface HistorialItem {
  id: number
  estado_anterior: string
  estado_nuevo: string
  fecha_cambio: string
  usuario_username: string
}

interface OrdenDetalle {
  id: number
  cliente_detalle: { razon_social: string; telefono: string }
  equipo_detalle: { tipo_equipo: string; marca_modelo: string | null } | null
  descripcion_falla: string
  estado: string
  motivo_bloqueo: string | null
  fecha_ingreso: string
  costo_estimado: number | null
  tiempo_estimado: number | null
  criticidad: number
  indice_prioridad: number | null
  justificacion_prioridad: string
  prioridad_origen: '' | 'ia' | 'respaldo'
  fecha_aviso_cliente: string | null
  repuestos_usados: OrdenRepuesto[]
  sesiones_horas: SesionHoras[]
  historial: HistorialItem[]
  total_horas: number
}

const route = useRoute()
const router = useRouter()
const ordenId = route.params.id as string

const orden = ref<OrdenDetalle | null>(null)
const cargando = ref(true)
const error = ref('')
const accionando = ref(false)

const nuevoEstado = ref('')
const motivoBloqueo = ref('')

// Hallazgo B (revisión de diseño): antes esta vista solo MOSTRABA costo/
// tiempo estimado como texto — si la orden se cargó sin esos datos (caso
// típico: se anota rápido en el mostrador y se sabe el costo/tiempo recién
// después del diagnóstico), no había forma de completarlos nunca, y la
// orden quedaba sin indice_prioridad para siempre. El backend ya aceptaba
// el PATCH (no son read_only en el serializer); faltaba el formulario acá.
const costoEstimadoEdit = ref<number | null>(null)
const tiempoEstimadoEdit = ref<number | null>(null)
const guardandoEstimacion = ref(false)
const errorEstimacion = ref('')

// Buscador de repuestos: recorre TODAS las listas de proveedores cargadas
// (vía /api/repuestos/?search=, que ya trae precios_proveedor anidado) y
// va mostrando coincidencias a medida que se escribe. El usuario elige
// de cuál lista comprar; no hay auto-selección del más barato.
const busquedaRepuesto = ref('')
const sugerenciasRepuesto = ref<SugerenciaRepuesto[]>([])
const repuestoSeleccionado = ref<SugerenciaRepuesto | null>(null)
let debounceHandle: ReturnType<typeof setTimeout> | undefined

const porEncargo = ref(false)
const descripcionEncargo = ref('')
const cantidadRepuesto = ref<number | null>(null)
const advertenciaRepuesto = ref('')

const nuevasHoras = ref<number | null>(null)
const errorHoras = ref('')

const ESTADOS = [
  { value: 'pendiente', label: 'Pendiente' },
  { value: 'en_curso', label: 'En curso' },
  { value: 'bloqueado', label: 'Bloqueado' },
  { value: 'terminado', label: 'Terminado' },
]

// HU-06: avisar al cliente es una decisión del Jefe de Taller, no del
// Técnico (el backend ya lo bloquea con 403; acá se oculta el botón para
// que el Técnico no se encuentre con un error al tocarlo).
const puedeAvisar = computed(
  () => auth.esJefe && orden.value?.estado === 'terminado' && !!orden.value?.cliente_detalle?.telefono,
)

async function cargar() {
  cargando.value = true
  try {
    const { data } = await api.get(`/ordenes/${ordenId}/`)
    orden.value = data
    nuevoEstado.value = data.estado
    motivoBloqueo.value = data.motivo_bloqueo ?? ''
    costoEstimadoEdit.value = data.costo_estimado
    tiempoEstimadoEdit.value = data.tiempo_estimado
  } catch {
    // Si la sesión venció y el refresh falla, el interceptor ya manda al
    // login; esto solo evita quedarse en "Cargando…" para siempre por
    // cualquier otro error de red.
  } finally {
    cargando.value = false
  }
}

// Igual que en OrdenesView.vue: una búsqueda vieja no debe pisar el
// resultado de una más nueva si tarda más en responder.
let secuenciaBusquedaRepuesto = 0

function onBuscarRepuestoInput() {
  // Escribir de nuevo invalida lo elegido antes — hay que confirmar la
  // elección de nuevo si se sigue tipeando.
  repuestoSeleccionado.value = null
  clearTimeout(debounceHandle)
  const q = busquedaRepuesto.value.trim()
  if (q.length < 2) {
    sugerenciasRepuesto.value = []
    return
  }
  const idBusqueda = ++secuenciaBusquedaRepuesto
  debounceHandle = setTimeout(async () => {
    const { data } = await api.get('/repuestos/', { params: { search: q } })
    if (idBusqueda !== secuenciaBusquedaRepuesto) return
    const sugerencias: SugerenciaRepuesto[] = []
    for (const r of data as Repuesto[]) {
      if (r.precios_proveedor.length === 0) {
        sugerencias.push({
          key: `r${r.id}`,
          label: `${r.codigo} — ${r.descripcion} · sin proveedor cargado (stock: ${r.cantidad_actual})`,
          repuestoId: r.id,
          precioProveedorId: null,
          stockActual: r.cantidad_actual,
        })
      }
      for (const pp of r.precios_proveedor) {
        sugerencias.push({
          key: `pp${pp.id}`,
          label: `${r.codigo} — ${r.descripcion} · ${pp.proveedor_nombre}: $${pp.precio_costo} (stock: ${r.cantidad_actual})`,
          repuestoId: r.id,
          precioProveedorId: pp.id,
          stockActual: r.cantidad_actual,
        })
      }
    }
    sugerenciasRepuesto.value = sugerencias
  }, 250)
}

function elegirSugerencia(s: SugerenciaRepuesto) {
  repuestoSeleccionado.value = s
  busquedaRepuesto.value = s.label
  sugerenciasRepuesto.value = []
}

async function cambiarEstado() {
  error.value = ''
  accionando.value = true
  try {
    const { data } = await api.post(`/ordenes/${ordenId}/cambiar_estado/`, {
      estado: nuevoEstado.value,
      motivo_bloqueo: motivoBloqueo.value,
    })
    orden.value = data
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'No se pudo cambiar el estado.'
  } finally {
    accionando.value = false
  }
}

async function agregarRepuesto() {
  advertenciaRepuesto.value = ''
  if (!cantidadRepuesto.value) return
  if (!porEncargo.value && !repuestoSeleccionado.value) {
    advertenciaRepuesto.value = 'Elegí un resultado del buscador (o marcá "es por encargo").'
    return
  }
  if (porEncargo.value && !descripcionEncargo.value.trim()) {
    advertenciaRepuesto.value = 'Describí el repuesto por encargo.'
    return
  }

  accionando.value = true
  try {
    const payload = porEncargo.value
      ? { descripcion_encargo: descripcionEncargo.value, cantidad: cantidadRepuesto.value }
      : {
          precio_proveedor_id: repuestoSeleccionado.value!.precioProveedorId,
          repuesto: repuestoSeleccionado.value!.precioProveedorId ? undefined : repuestoSeleccionado.value!.repuestoId,
          cantidad: cantidadRepuesto.value,
        }
    const { data } = await api.post(`/ordenes/${ordenId}/registrar_repuesto/`, payload)
    if (data.warning) advertenciaRepuesto.value = data.warning
    busquedaRepuesto.value = ''
    repuestoSeleccionado.value = null
    descripcionEncargo.value = ''
    porEncargo.value = false
    cantidadRepuesto.value = null
    await cargar() // refresca stock, repuestos_usados y precios
  } catch (e: any) {
    advertenciaRepuesto.value = e?.response?.data?.detail ?? 'No se pudo registrar el repuesto.'
  } finally {
    accionando.value = false
  }
}

async function agregarHoras() {
  if (!nuevasHoras.value) return
  errorHoras.value = ''
  accionando.value = true
  try {
    await api.post(`/ordenes/${ordenId}/registrar_horas/`, { horas: nuevasHoras.value })
    nuevasHoras.value = null
    await cargar()
  } catch (e: any) {
    errorHoras.value = e?.response?.data?.detail ?? 'No se pudieron registrar las horas.'
  } finally {
    accionando.value = false
  }
}

async function guardarEstimacion() {
  errorEstimacion.value = ''
  guardandoEstimacion.value = true
  try {
    const { data } = await api.patch(`/ordenes/${ordenId}/`, {
      costo_estimado: costoEstimadoEdit.value,
      tiempo_estimado: tiempoEstimadoEdit.value,
    })
    orden.value = data
  } catch (e: any) {
    errorEstimacion.value = e?.response?.data
      ? JSON.stringify(e.response.data)
      : 'No se pudo guardar la estimación.'
  } finally {
    guardandoEstimacion.value = false
  }
}

async function avisarCliente() {
  accionando.value = true
  try {
    const { data } = await api.post(`/ordenes/${ordenId}/avisar_cliente/`, {})
    window.open(data.whatsapp_url, '_blank')
    await cargar()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'No se pudo avisar al cliente.'
  } finally {
    accionando.value = false
  }
}

onMounted(cargar)
</script>

<template>
  <div class="page" v-if="orden">
    <button class="volver" @click="router.push({ name: 'ordenes' })">← Volver al listado</button>

    <h2>OT-{{ String(orden.id).padStart(4, '0') }} — {{ orden.cliente_detalle.razon_social }}</h2>
    <p class="subinfo">
      {{ orden.equipo_detalle?.tipo_equipo ?? 'Sin equipo' }}
      <span v-if="orden.equipo_detalle?.marca_modelo"> · {{ orden.equipo_detalle.marca_modelo }}</span>
      · Ingresó {{ new Date(orden.fecha_ingreso).toLocaleString('es-AR') }}
    </p>
    <p class="falla">{{ orden.descripcion_falla }}</p>

    <div class="grid">
      <section class="card">
        <h3>Estado</h3>
        <p><span class="badge" :class="`badge-${orden.estado}`">{{ orden.estado }}</span></p>
        <p v-if="orden.motivo_bloqueo" class="motivo">Motivo de bloqueo: {{ orden.motivo_bloqueo }}</p>

        <select v-model="nuevoEstado">
          <option v-for="e in ESTADOS" :key="e.value" :value="e.value">{{ e.label }}</option>
        </select>
        <input
          v-if="nuevoEstado === 'bloqueado'"
          v-model="motivoBloqueo"
          placeholder="Motivo de bloqueo (obligatorio)"
        />
        <button :disabled="accionando" @click="cambiarEstado">Guardar estado</button>
        <p v-if="error" class="error">{{ error }}</p>

        <button v-if="puedeAvisar" class="whatsapp" :disabled="accionando" @click="avisarCliente">
          Avisar al cliente por WhatsApp
        </button>
        <p v-if="orden.fecha_aviso_cliente" class="hint">
          Avisado el {{ new Date(orden.fecha_aviso_cliente).toLocaleString('es-AR') }}
        </p>
      </section>

      <section class="card">
        <h3>Datos de la orden</h3>
        <template v-if="auth.esJefe">
          <label class="campo-inline">
            Costo estimado
            <input v-model.number="costoEstimadoEdit" type="number" min="0" />
          </label>
          <label class="campo-inline">
            Tiempo estimado (hs)
            <input v-model.number="tiempoEstimadoEdit" type="number" min="0.1" step="0.5" />
          </label>
          <button :disabled="guardandoEstimacion" @click="guardarEstimacion">
            {{ guardandoEstimacion ? 'Guardando…' : 'Guardar estimación' }}
          </button>
          <p v-if="errorEstimacion" class="error">{{ errorEstimacion }}</p>
          <p v-if="orden.costo_estimado == null || orden.tiempo_estimado == null" class="hint aviso-sin-estimacion">
            Sin costo y/o tiempo estimado, esta orden no tiene prioridad calculada y queda al final del listado.
          </p>
        </template>
        <template v-else>
          <p>Costo estimado: {{ orden.costo_estimado ?? '—' }}</p>
          <p>Tiempo estimado: {{ orden.tiempo_estimado ?? '—' }} hs</p>
        </template>
        <p>Criticidad del trabajo: {{ orden.criticidad }}/5</p>
        <p>
          Prioridad sugerida: {{ orden.indice_prioridad != null ? Math.round(orden.indice_prioridad) + ' / 100' : '-' }}
          <span v-if="orden.prioridad_origen">({{ orden.prioridad_origen === 'ia' ? 'decidida por IA' : 'regla de respaldo' }})</span>
        </p>
        <p v-if="orden.justificacion_prioridad" class="justificacion">{{ orden.justificacion_prioridad }}</p>
        <p>Horas registradas: {{ orden.total_horas }}</p>
      </section>

      <section v-if="FEATURE_STOCK_PROVEEDORES" class="card">
        <h3>Repuestos usados</h3>
        <ul>
          <li v-for="r in orden.repuestos_usados" :key="r.id">
            {{ r.repuesto_detalle ? `${r.repuesto_detalle.codigo} — ${r.repuesto_detalle.descripcion}` : r.descripcion_encargo }}
            × {{ r.cantidad }}
            <span v-if="r.proveedor_nombre" class="hint"> · {{ r.proveedor_nombre }} (${{ r.precio_costo }} c/u)</span>
          </li>
          <li v-if="orden.repuestos_usados.length === 0" class="hint">Sin repuestos cargados.</li>
        </ul>

        <div v-if="!porEncargo" class="buscador-repuesto">
          <input
            v-model="busquedaRepuesto"
            placeholder="Buscar repuesto en todas las listas de proveedores…"
            @input="onBuscarRepuestoInput"
          />
          <ul v-if="sugerenciasRepuesto.length" class="sugerencias">
            <li v-for="s in sugerenciasRepuesto" :key="s.key" @click="elegirSugerencia(s)">
              {{ s.label }}
            </li>
          </ul>
        </div>
        <input v-else v-model="descripcionEncargo" placeholder="Descripción del repuesto por encargo" />

        <div class="inline-form">
          <label class="checkbox-inline">
            <input type="checkbox" v-model="porEncargo" @change="busquedaRepuesto = ''; repuestoSeleccionado = null" />
            Es por encargo (no está en el catálogo)
          </label>
        </div>
        <div class="inline-form">
          <input v-model.number="cantidadRepuesto" type="number" placeholder="Cantidad" min="1" />
          <button :disabled="accionando" @click="agregarRepuesto">Agregar</button>
        </div>
        <p v-if="advertenciaRepuesto" class="error">{{ advertenciaRepuesto }}</p>
      </section>

      <section class="card">
        <h3>Horas trabajadas</h3>
        <ul>
          <li v-for="s in orden.sesiones_horas" :key="s.id">
            {{ s.horas }} hs — {{ s.usuario_username }} ({{ new Date(s.fecha_registro).toLocaleString('es-AR') }})
          </li>
          <li v-if="orden.sesiones_horas.length === 0" class="hint">Sin horas cargadas.</li>
        </ul>
        <div class="inline-form">
          <input v-model.number="nuevasHoras" type="number" step="0.25" placeholder="Horas" min="0" />
          <button :disabled="accionando" @click="agregarHoras">Registrar</button>
        </div>
        <p v-if="errorHoras" class="error">{{ errorHoras }}</p>
      </section>

      <section class="card">
        <h3>Historial de estados</h3>
        <ul>
          <li v-for="h in orden.historial" :key="h.id">
            {{ h.estado_anterior }} → {{ h.estado_nuevo }} — {{ h.usuario_username }}
            ({{ new Date(h.fecha_cambio).toLocaleString('es-AR') }})
          </li>
          <li v-if="orden.historial.length === 0" class="hint">Sin cambios registrados.</li>
        </ul>
      </section>
    </div>
  </div>
  <p v-else-if="cargando" class="page">Cargando…</p>
</template>

<style scoped>
.justificacion {
  font-size: 0.85rem;
  color: #475569;
}
.page {
  max-width: 900px;
  margin: 2rem auto;
  padding: 0 1rem;
}
.volver {
  background: none;
  color: #0f172a;
  padding: 0;
  margin-bottom: 1rem;
  font-size: 0.85rem;
}
h2 {
  margin-bottom: 0.25rem;
}
.subinfo {
  color: #64748b;
  font-size: 0.85rem;
  margin: 0 0 0.75rem;
}
.falla {
  background: white;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-bottom: 1.5rem;
}
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}
.card {
  background: white;
  border-radius: 8px;
  padding: 1rem;
}
.card h3 {
  margin-top: 0;
  font-size: 0.95rem;
}
.card select,
.card input {
  width: 100%;
  margin-bottom: 0.5rem;
}
.card > button {
  width: 100%;
  margin-bottom: 0.5rem;
}
.whatsapp {
  background: #16a34a;
}
ul {
  list-style: none;
  padding: 0;
  margin: 0 0 0.75rem;
  font-size: 0.85rem;
}
ul li {
  padding: 0.35rem 0;
  border-bottom: 1px solid #f1f5f9;
}
.buscador-repuesto {
  position: relative;
  margin-bottom: 0.5rem;
}
.buscador-repuesto input {
  margin-bottom: 0;
}
.sugerencias {
  position: absolute;
  z-index: 10;
  top: 100%;
  left: 0;
  right: 0;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  max-height: 220px;
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
.checkbox-inline {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
  font-weight: normal;
  color: #64748b;
}
.checkbox-inline input {
  width: auto;
  margin: 0;
}
.inline-form {
  display: flex;
  gap: 0.4rem;
}
.inline-form select {
  flex: 2;
}
.inline-form input {
  flex: 1;
}
.inline-form button {
  flex: 0 0 auto;
}
.hint {
  color: #94a3b8;
  font-size: 0.8rem;
}
.campo-inline {
  display: block;
  font-size: 0.8rem;
  color: #64748b;
  margin-bottom: 0.5rem;
}
.aviso-sin-estimacion {
  color: #b45309;
}
.motivo {
  color: #991b1b;
  font-size: 0.85rem;
}
.error {
  color: #991b1b;
  font-size: 0.85rem;
}
</style>
