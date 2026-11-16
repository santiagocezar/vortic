<script setup lang="ts">
// Detalle de una orden: cambiar estado (CU-02/HU-03/HU-04), registrar
// repuestos y horas (CU-04/HU-07/HU-08), avisar al cliente (CU-05/HU-09).
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api/client'
import BuscadorCombobox from '../components/BuscadorCombobox.vue'
import { useAuthStore } from '../stores/auth'
import { FEATURE_STOCK_PROVEEDORES } from '../config/features'
import { etiquetaEstado } from '../utils/estados'
import IconBack from '~icons/material-symbols/arrow-back'
import IconChat from '~icons/material-symbols/chat'

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
const repuestoSeleccionado = ref<SugerenciaRepuesto | null>(null)
const buscadorRepuesto = ref<{ limpiar: () => void } | null>(null)

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
const puedeAvisar = computed(() => auth.esJefe && orden.value?.estado === 'terminado' && !!orden.value?.cliente_detalle?.telefono)

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

// El buscador compartido se encarga del debounce, la guarda de secuencia y
// el ARIA; acá solo se mapea cada repuesto+proveedor a una fila elegible.
async function cargarRepuestos(q: string): Promise<SugerenciaRepuesto[]> {
  const { data } = await api.get('/repuestos/', { params: { search: q } })
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
  return sugerencias
}

const etiquetaRepuesto = (s: SugerenciaRepuesto) => s.label
const claveRepuesto = (s: SugerenciaRepuesto) => s.key

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
    repuestoSeleccionado.value = null
    buscadorRepuesto.value?.limpiar()
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
    errorEstimacion.value = e?.response?.data ? JSON.stringify(e.response.data) : 'No se pudo guardar la estimación.'
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

// Volver al listado conservando el filtro (?estado=) con el que se llegó:
// si hay historial, el back restaura la URL exacta; si se entró por enlace
// directo, se cae al listado completo.
function volver() {
  if (router.options.history.state.back) router.back()
  else router.push({ name: 'ordenes' })
}

onMounted(cargar)
</script>

<template>
  <div class="page" v-if="orden">
    <button class="volver" @click="volver">
      <IconBack aria-hidden="true" />
      Volver al listado
    </button>

    <h2>OT-{{ String(orden.id).padStart(4, '0') }} — {{ orden.cliente_detalle.razon_social }}</h2>
    <p class="subinfo">
      {{ orden.equipo_detalle?.tipo_equipo ?? 'Sin equipo' }}
      <span v-if="orden.equipo_detalle?.marca_modelo"> · {{ orden.equipo_detalle.marca_modelo }}</span>
      · Ingresó {{ new Date(orden.fecha_ingreso).toLocaleString('es-AR') }}
    </p>
    <p class="falla">{{ orden.descripcion_falla }}</p>
    <p class="meta">
      <span class="badge" :class="`badge-${orden.estado}`">{{ etiquetaEstado(orden.estado) }}</span>
      <span
        >Criticidad <strong>{{ orden.criticidad }}/5</strong></span
      >
    </p>

    <section class="card accion-estado">
      <h3>Cambiar estado</h3>
      <div class="estado-form">
        <label class="campo-inline estado-select">
          <span>Nuevo estado</span>
          <select v-model="nuevoEstado">
            <option v-for="e in ESTADOS" :key="e.value" :value="e.value">{{ e.label }}</option>
          </select>
        </label>
        <input v-if="nuevoEstado === 'bloqueado'" v-model="motivoBloqueo" aria-label="Motivo de bloqueo" placeholder="Motivo de bloqueo (obligatorio)" />
        <button :disabled="accionando" @click="cambiarEstado">Guardar estado</button>
      </div>
      <p v-if="orden.motivo_bloqueo" class="motivo">Motivo de bloqueo: {{ orden.motivo_bloqueo }}</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>

      <div v-if="puedeAvisar" class="aviso-cliente">
        <button class="whatsapp btn-icono" :disabled="accionando" @click="avisarCliente">
          <IconChat aria-hidden="true" />
          Avisar al cliente por WhatsApp
        </button>
        <p v-if="orden.fecha_aviso_cliente" class="hint">Avisado el {{ new Date(orden.fecha_aviso_cliente).toLocaleString('es-AR') }}</p>
      </div>
    </section>

    <div class="grid">
      <section class="card">
        <h3>Prioridad</h3>
        <p v-if="orden.indice_prioridad != null" class="puntaje">
          <strong>{{ Math.round(orden.indice_prioridad) }}</strong
          ><span class="escala">/100</span>
          <span v-if="orden.prioridad_origen" class="origen">
            {{ orden.prioridad_origen === 'ia' ? 'decidida por IA' : 'regla de respaldo' }}
          </span>
        </p>
        <p v-else class="sin-prioridad">Sin calcular</p>
        <p v-if="orden.justificacion_prioridad" class="justificacion">{{ orden.justificacion_prioridad }}</p>
      </section>

      <section class="card">
        <h3>Estimación</h3>
        <template v-if="auth.esJefe">
          <div class="campos">
            <label class="campo-inline">
              Costo estimado
              <input v-model.number="costoEstimadoEdit" type="number" min="0" />
            </label>
            <label class="campo-inline">
              Tiempo estimado (hs)
              <input v-model.number="tiempoEstimadoEdit" type="number" min="0.1" step="0.1" />
            </label>
          </div>
          <button :disabled="guardandoEstimacion" @click="guardarEstimacion">
            {{ guardandoEstimacion ? 'Guardando…' : 'Guardar estimación' }}
          </button>
          <p v-if="errorEstimacion" class="error" role="alert">{{ errorEstimacion }}</p>
          <p v-if="orden.costo_estimado == null || orden.tiempo_estimado == null" class="hint aviso-sin-estimacion">
            Falta costo o tiempo: la orden queda sin prioridad calculada.
          </p>
        </template>
        <template v-else>
          <p class="dato">Costo estimado: {{ orden.costo_estimado ?? '—' }}</p>
          <p class="dato">Tiempo estimado: {{ orden.tiempo_estimado ?? '—' }} hs</p>
        </template>
      </section>

      <section v-if="FEATURE_STOCK_PROVEEDORES" class="card">
        <h3>
          Repuestos usados
          <span v-if="orden.repuestos_usados.length" class="conteo">{{ orden.repuestos_usados.length }}</span>
        </h3>
        <ul v-if="orden.repuestos_usados.length" class="lista">
          <li v-for="r in orden.repuestos_usados" :key="r.id">
            {{ r.repuesto_detalle ? `${r.repuesto_detalle.codigo} — ${r.repuesto_detalle.descripcion}` : r.descripcion_encargo }}
            × {{ r.cantidad }}
            <span v-if="r.proveedor_nombre" class="hint"> · {{ r.proveedor_nombre }} (${{ r.precio_costo }} c/u)</span>
          </li>
        </ul>
        <p v-else class="hint vacio">Sin repuestos cargados.</p>

        <details class="agregar">
          <summary>Registrar repuesto</summary>
          <div class="form-repuesto">
            <label class="checkbox-inline">
              <input
                type="checkbox"
                v-model="porEncargo"
                @change="
                  repuestoSeleccionado = null
                  buscadorRepuesto?.limpiar()
                "
              />
              Es por encargo (no está en el catálogo)
            </label>

            <div v-if="!porEncargo" class="buscador-repuesto">
              <BuscadorCombobox
                ref="buscadorRepuesto"
                v-model="repuestoSeleccionado"
                :cargar="cargarRepuestos"
                :etiqueta="etiquetaRepuesto"
                :clave="claveRepuesto"
                etiqueta-accesible="Buscar repuesto en todas las listas de proveedores"
                placeholder="Buscar repuesto…"
                name="repuesto"
                mensaje-error="No se pudo buscar repuestos. Reintentá escribiendo de nuevo."
              />
            </div>
            <input v-else v-model="descripcionEncargo" aria-label="Descripción del repuesto por encargo" placeholder="Descripción del repuesto por encargo" />

            <div class="inline-form">
              <input v-model.number="cantidadRepuesto" type="number" aria-label="Cantidad de repuestos" placeholder="Cantidad" min="1" />
              <button :disabled="accionando" @click="agregarRepuesto">Agregar</button>
            </div>
            <p v-if="advertenciaRepuesto" class="error" role="alert">{{ advertenciaRepuesto }}</p>
          </div>
        </details>
      </section>

      <section class="card">
        <h3>
          Horas trabajadas
          <span class="conteo">{{ orden.total_horas }} h</span>
        </h3>
        <ul v-if="orden.sesiones_horas.length" class="lista">
          <li v-for="s in orden.sesiones_horas" :key="s.id">
            {{ s.horas }} hs — {{ s.usuario_username }} ({{ new Date(s.fecha_registro).toLocaleString('es-AR') }})
          </li>
        </ul>
        <p v-else class="hint vacio">Sin horas cargadas.</p>
        <div class="inline-form">
          <input v-model.number="nuevasHoras" type="number" step="0.25" aria-label="Horas a registrar" placeholder="Horas" min="0" />
          <button :disabled="accionando" @click="agregarHoras">Registrar</button>
        </div>
        <p v-if="errorHoras" class="error" role="alert">{{ errorHoras }}</p>
      </section>
    </div>

    <details v-if="orden.historial.length" class="historial">
      <summary>Historial de estados ({{ orden.historial.length }})</summary>
      <ul class="lista">
        <li v-for="h in orden.historial" :key="h.id">
          {{ etiquetaEstado(h.estado_anterior) }} → {{ etiquetaEstado(h.estado_nuevo) }} — {{ h.usuario_username }} ({{
            new Date(h.fecha_cambio).toLocaleString('es-AR')
          }})
        </li>
      </ul>
    </details>
    <p v-else class="hint sin-historial">Sin cambios de estado registrados.</p>
  </div>
  <p v-else-if="cargando" class="page">Cargando…</p>
</template>

<style scoped>
.page {
  max-width: 900px;
  margin: 2rem auto;
  padding: 0 1rem;
}
.volver {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background: none;
  color: #0f172a;
  padding: 0;
  margin-bottom: 1rem;
  font-size: 0.85rem;
}
.volver svg {
  width: 1.05em;
  height: 1.05em;
}
h2 {
  margin: 0 0 0.25rem;
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
  margin: 0 0 0.75rem;
}
.meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem 0.9rem;
  margin: 0 0 1rem;
  font-size: 0.8rem;
  color: #64748b;
}
.meta strong {
  color: #0f172a;
  font-weight: 600;
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
  margin: 0 0 0.75rem;
  font-size: 0.95rem;
}
.accion-estado {
  margin-bottom: 1rem;
}
.estado-form {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0.5rem;
}
.estado-select {
  flex: 0 1 220px;
  margin: 0;
}
.estado-form > input {
  flex: 1 1 220px;
}
.estado-form button {
  flex: 0 0 auto;
}
.campo-inline {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: #334155;
}
.campo-inline input,
.campo-inline select {
  width: 100%;
  font-weight: 400;
  color: #0f172a;
}
.campos {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}
.puntaje {
  display: flex;
  align-items: baseline;
  gap: 0.2rem;
  margin: 0 0 0.5rem;
}
.puntaje strong {
  font-size: 1.5rem;
  line-height: 1.2;
}
.escala {
  color: #64748b;
  font-size: 0.8rem;
}
.origen {
  margin-left: 0.35rem;
  color: #475569;
  font-size: 0.8rem;
}
.sin-prioridad {
  margin: 0 0 0.5rem;
  color: #b45309;
  font-size: 0.9rem;
}
.justificacion {
  margin: 0;
  color: #475569;
  font-size: 0.8rem;
  line-height: 1.45;
}
.dato {
  margin: 0 0 0.25rem;
  font-size: 0.9rem;
}
.dato:last-child {
  margin-bottom: 0;
}
.lista {
  list-style: none;
  padding: 0;
  margin: 0 0 0.75rem;
  font-size: 0.85rem;
}
.lista li {
  padding: 0.35rem 0;
  border-bottom: 1px solid #f1f5f9;
}
.lista li:last-child {
  border-bottom: 0;
}
.conteo {
  margin-left: 0.25rem;
  color: #64748b;
  font-size: 0.8rem;
  font-weight: 400;
}
.vacio {
  margin: 0 0 0.75rem;
}
.hint {
  color: #64748b;
  font-size: 0.8rem;
}
.aviso-sin-estimacion {
  margin: 0.5rem 0 0;
  color: #b45309;
}
.motivo {
  margin: 0.5rem 0 0;
  color: #991b1b;
  font-size: 0.8rem;
}
.error {
  margin: 0.5rem 0 0;
  color: #991b1b;
  font-size: 0.85rem;
}
.aviso-cliente {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid #f1f5f9;
}
.aviso-cliente .hint {
  margin: 0.5rem 0 0;
}
.whatsapp {
  background: #16a34a;
}
.agregar {
  margin-top: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid #f1f5f9;
}
.agregar summary {
  cursor: pointer;
  padding: 0.35rem 0;
  color: #0f172a;
  font-size: 0.8rem;
  font-weight: 600;
}
.agregar summary::marker {
  color: #64748b;
}
.form-repuesto {
  display: grid;
  gap: 0.5rem;
  margin-top: 0.5rem;
  padding: 0.75rem;
  background: #f1f5f9;
  border-radius: 6px;
}
.form-repuesto > input {
  width: 100%;
}
.buscador-repuesto {
  position: relative;
}
.checkbox-inline {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
  font-weight: 400;
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
.inline-form input {
  flex: 1;
  min-width: 0;
}
.inline-form button {
  flex: 0 0 auto;
}
.historial {
  margin-top: 1rem;
  padding: 0 1rem;
  background: white;
  border-radius: 8px;
}
.historial summary {
  padding: 0.85rem 0;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 600;
}
.historial summary::marker {
  color: #64748b;
}
.historial .lista {
  margin: 0 0 0.75rem;
}
.sin-historial {
  margin: 1rem 0 0;
}

@media (max-width: 640px) {
  .page {
    margin: 1rem auto;
  }
  .grid {
    grid-template-columns: 1fr;
  }
  .estado-form {
    flex-direction: column;
    align-items: stretch;
  }
  .estado-select {
    flex: 1 1 auto;
  }
  .estado-form > input {
    flex: 1 1 auto;
  }
  .estado-form button {
    width: 100%;
  }
  .campos {
    grid-template-columns: 1fr;
  }
  .inline-form {
    flex-wrap: wrap;
  }
  .agregar summary,
  .historial summary {
    min-height: 44px;
    padding-top: 0.8rem;
    padding-bottom: 0.8rem;
  }
  .aviso-cliente .whatsapp {
    width: 100%;
  }
}
</style>
