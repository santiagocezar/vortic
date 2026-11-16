<script setup lang="ts">
// Alta de proveedores e importación de listas de precios (.csv / .xlsx).
// Cada proveedor manda su planilla con sus propias columnas (no hay un
// formato estándar entre proveedores), así que la importación es en dos
// pasos: 1) se sube el archivo y el backend devuelve los encabezados
// reales + una sugerencia de qué columna es cada cosa; 2) el usuario
// confirma o corrige esa asociación y recién ahí se importa. Una vez
// confirmado, el proveedor guarda ese mapeo y la próxima planilla del
// mismo proveedor lo pre-completa solo.
import { ref, onMounted } from 'vue'
import api from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

interface Proveedor {
  id: number
  nombre: string
  activo: boolean
}

interface ResultadoImport {
  precios_creados: number
  precios_actualizados: number
  filas_con_error: string[]
}

interface PrevisualizacionState {
  archivo: File
  headers: string[]
  muestra: Record<string, unknown>[]
  totalFilas: number
  colCodigo: string
  colDescripcion: string
  colPrecio: string
  mapeoReutilizado: boolean
}

const proveedores = ref<Proveedor[]>([])
const nombreNuevo = ref('')
const error = ref('')

const archivoPorProveedor = ref<Record<number, File | null>>({})
const cargandoPreview = ref<number | null>(null)
const previsualizacionPorProveedor = ref<Record<number, PrevisualizacionState | null>>({})
const importando = ref<number | null>(null)
const resultadoPorProveedor = ref<Record<number, ResultadoImport>>({})
const errorPorProveedor = ref<Record<number, string>>({})

async function cargar() {
  const { data } = await api.get('/proveedores/')
  proveedores.value = data
}

async function crearProveedor() {
  error.value = ''
  if (!nombreNuevo.value.trim()) return
  try {
    await api.post('/proveedores/', { nombre: nombreNuevo.value })
    nombreNuevo.value = ''
    await cargar()
  } catch {
    error.value = 'No se pudo crear el proveedor (¿nombre repetido?).'
  }
}

function onArchivoSeleccionado(proveedorId: number, event: Event) {
  const input = event.target as HTMLInputElement
  archivoPorProveedor.value[proveedorId] = input.files?.[0] ?? null
  previsualizacionPorProveedor.value[proveedorId] = null
  resultadoPorProveedor.value[proveedorId] = undefined as any
  delete resultadoPorProveedor.value[proveedorId]
  errorPorProveedor.value[proveedorId] = ''
}

async function previsualizar(proveedorId: number) {
  const archivo = archivoPorProveedor.value[proveedorId]
  if (!archivo) return
  errorPorProveedor.value[proveedorId] = ''
  cargandoPreview.value = proveedorId
  try {
    const formData = new FormData()
    formData.append('archivo', archivo)
    const { data } = await api.post(`/proveedores/${proveedorId}/previsualizar_planilla/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    previsualizacionPorProveedor.value[proveedorId] = {
      archivo,
      headers: data.headers,
      muestra: data.muestra,
      totalFilas: data.total_filas,
      colCodigo: data.sugerencia.codigo ?? '',
      colDescripcion: data.sugerencia.descripcion ?? '',
      colPrecio: data.sugerencia.precio ?? '',
      mapeoReutilizado: data.mapeo_reutilizado,
    }
  } catch (e: any) {
    errorPorProveedor.value[proveedorId] = e?.response?.data?.detail ?? 'No se pudo leer la planilla.'
  } finally {
    cargandoPreview.value = null
  }
}

async function confirmarImportacion(proveedorId: number) {
  const prev = previsualizacionPorProveedor.value[proveedorId]
  if (!prev) return
  if (!prev.colCodigo || !prev.colPrecio) {
    errorPorProveedor.value[proveedorId] = 'Elegí qué columna es el código y cuál es el precio.'
    return
  }
  errorPorProveedor.value[proveedorId] = ''
  importando.value = proveedorId
  try {
    const formData = new FormData()
    formData.append('archivo', prev.archivo)
    formData.append('col_codigo', prev.colCodigo)
    if (prev.colDescripcion) formData.append('col_descripcion', prev.colDescripcion)
    formData.append('col_precio', prev.colPrecio)
    const { data } = await api.post(`/proveedores/${proveedorId}/importar_precios/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    resultadoPorProveedor.value[proveedorId] = data
    previsualizacionPorProveedor.value[proveedorId] = null
    archivoPorProveedor.value[proveedorId] = null
  } catch (e: any) {
    errorPorProveedor.value[proveedorId] = e?.response?.data?.detail ?? 'No se pudo importar la planilla.'
  } finally {
    importando.value = null
  }
}

function cancelarPreview(proveedorId: number) {
  previsualizacionPorProveedor.value[proveedorId] = null
  archivoPorProveedor.value[proveedorId] = null
}

onMounted(cargar)
</script>

<template>
  <div class="page">
    <h2>Proveedores</h2>

    <form v-if="auth.esJefe" class="nuevo-proveedor" @submit.prevent="crearProveedor">
      <input v-model="nombreNuevo" placeholder="Nombre del proveedor" required />
      <button type="submit">Agregar proveedor</button>
    </form>
    <p v-if="error" class="error">{{ error }}</p>

    <div v-for="p in proveedores" :key="p.id" class="proveedor-card">
      <h3>{{ p.nombre }}</h3>

      <p v-if="!auth.esJefe" class="hint">Solo el Jefe de Taller puede importar listas de precios.</p>
      <template v-else-if="!previsualizacionPorProveedor[p.id]">
        <p class="hint">
          Subí la lista de precios (.csv o .xlsx) con las columnas que use este proveedor — no hace falta que coincidan con las de otro proveedor, en el
          siguiente paso decís cuál es cuál.
        </p>
        <div class="importar">
          <input type="file" accept=".csv,.xlsx" @change="onArchivoSeleccionado(p.id, $event)" />
          <button :disabled="cargandoPreview === p.id || !archivoPorProveedor[p.id]" @click="previsualizar(p.id)">
            {{ cargandoPreview === p.id ? 'Leyendo…' : 'Continuar' }}
          </button>
        </div>
      </template>

      <template v-else>
        <div class="mapeo">
          <p class="hint">
            {{ previsualizacionPorProveedor[p.id]!.totalFilas }} filas encontradas.
            <span v-if="previsualizacionPorProveedor[p.id]!.mapeoReutilizado"> Usamos el mismo mapeo de la última vez — revisalo y confirmá. </span>
            <span v-else>Elegí qué columna de la planilla es cada dato.</span>
          </p>

          <div class="campos-mapeo">
            <label>
              Código (obligatorio)
              <select v-model="previsualizacionPorProveedor[p.id]!.colCodigo">
                <option value="">— elegir columna —</option>
                <option v-for="h in previsualizacionPorProveedor[p.id]!.headers" :key="h" :value="h">
                  {{ h }}
                </option>
              </select>
            </label>
            <label>
              Descripción (opcional)
              <select v-model="previsualizacionPorProveedor[p.id]!.colDescripcion">
                <option value="">— sin descripción —</option>
                <option v-for="h in previsualizacionPorProveedor[p.id]!.headers" :key="h" :value="h">
                  {{ h }}
                </option>
              </select>
            </label>
            <label>
              Precio (obligatorio)
              <select v-model="previsualizacionPorProveedor[p.id]!.colPrecio">
                <option value="">— elegir columna —</option>
                <option v-for="h in previsualizacionPorProveedor[p.id]!.headers" :key="h" :value="h">
                  {{ h }}
                </option>
              </select>
            </label>
          </div>

          <div class="muestra" v-if="previsualizacionPorProveedor[p.id]!.muestra.length">
            <p class="hint">Vista previa (primeras filas):</p>
            <table class="tabla-muestra">
              <thead>
                <tr>
                  <th v-for="h in previsualizacionPorProveedor[p.id]!.headers" :key="h">{{ h }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(fila, i) in previsualizacionPorProveedor[p.id]!.muestra" :key="i">
                  <td v-for="h in previsualizacionPorProveedor[p.id]!.headers" :key="h">
                    {{ fila[h] }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="acciones-mapeo">
            <button :disabled="importando === p.id" @click="confirmarImportacion(p.id)">
              {{ importando === p.id ? 'Importando…' : 'Confirmar e importar' }}
            </button>
            <button class="link-btn" @click="cancelarPreview(p.id)">Cancelar</button>
          </div>
        </div>
      </template>

      <p v-if="errorPorProveedor[p.id]" class="error">{{ errorPorProveedor[p.id] }}</p>

      <div v-if="resultadoPorProveedor[p.id]" class="resultado">
        <p>{{ resultadoPorProveedor[p.id].precios_creados }} precios nuevos, {{ resultadoPorProveedor[p.id].precios_actualizados }} actualizados.</p>
        <ul v-if="resultadoPorProveedor[p.id].filas_con_error.length">
          <li v-for="(e, i) in resultadoPorProveedor[p.id].filas_con_error" :key="i" class="error">
            {{ e }}
          </li>
        </ul>
      </div>
    </div>
    <p v-if="proveedores.length === 0" class="hint">Todavía no cargaste ningún proveedor.</p>
  </div>
</template>

<style scoped>
.page {
  max-width: 900px;
  margin: 2rem auto;
  padding: 0 1rem;
}
.nuevo-proveedor {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}
.nuevo-proveedor input {
  flex: 1;
}
.proveedor-card {
  background: white;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1rem;
}
.proveedor-card h3 {
  margin: 0 0 0.5rem;
}
.hint {
  color: #64748b;
  font-size: 0.8rem;
}
.importar {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  margin-top: 0.5rem;
}
.mapeo {
  margin-top: 0.5rem;
}
.campos-mapeo {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
  margin: 0.5rem 0;
}
.campos-mapeo label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.8rem;
  color: #334155;
}
.muestra {
  margin: 0.75rem 0;
  overflow-x: auto;
}
.tabla-muestra {
  font-size: 0.78rem;
  border-collapse: collapse;
  width: 100%;
}
.tabla-muestra th,
.tabla-muestra td {
  border: 1px solid #e2e8f0;
  padding: 0.25rem 0.5rem;
  text-align: left;
  white-space: nowrap;
}
.acciones-mapeo {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-top: 0.5rem;
}
.resultado {
  margin-top: 0.75rem;
  font-size: 0.85rem;
}
.resultado ul {
  margin: 0.25rem 0 0;
  padding-left: 1.2rem;
}
.error {
  color: #991b1b;
  font-size: 0.85rem;
}
</style>
