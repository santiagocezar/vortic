<script setup lang="ts">
// HU-11 (ver stock actual) y HU-12 (alta/ajuste manual de repuestos).
import { ref, onMounted } from 'vue'
import api from '../api/client'
import { useAuthStore } from '../stores/auth'
import IconAdd from '~icons/material-symbols/add'
import IconClose from '~icons/material-symbols/close'

const auth = useAuthStore()

interface Repuesto {
  id: number
  codigo: string
  descripcion: string
  cantidad_actual: number
  cantidad_minima: number
  stock_bajo: boolean
  // Solo de referencia: el más barato entre proveedores +40%. La compra
  // real de cada orden se elige aparte (ver OrdenDetalleView) y puede no
  // coincidir con esto.
  precio_costo_sugerido: string | null
  proveedor_sugerido_nombre: string | null
  precio_venta_sugerido: string | null
}

const repuestos = ref<Repuesto[]>([])
const busqueda = ref('')
const soloStockBajo = ref(false)
const cargando = ref(false)
const error = ref('')

const mostrarForm = ref(false)
const nuevoRepuesto = ref({
  codigo: '', descripcion: '', cantidad_actual: 0, cantidad_minima: 0,
})

const editandoId = ref<number | null>(null)
const edicion = ref({ cantidad_actual: 0, cantidad_minima: 0 })

async function cargar() {
  cargando.value = true
  try {
    const params = busqueda.value ? { search: busqueda.value } : {}
    const { data } = await api.get('/repuestos/', { params })
    repuestos.value = soloStockBajo.value ? data.filter((r: Repuesto) => r.stock_bajo) : data
  } finally {
    cargando.value = false
  }
}

async function crearRepuesto() {
  error.value = ''
  if (!nuevoRepuesto.value.codigo || !nuevoRepuesto.value.descripcion) return
  try {
    await api.post('/repuestos/', nuevoRepuesto.value)
    nuevoRepuesto.value = { codigo: '', descripcion: '', cantidad_actual: 0, cantidad_minima: 0 }
    mostrarForm.value = false
    await cargar()
  } catch (e: any) {
    error.value = e?.response?.data?.codigo?.[0] ?? 'No se pudo crear el repuesto (¿código repetido?).'
  }
}

function empezarEdicion(r: Repuesto) {
  editandoId.value = r.id
  edicion.value = { cantidad_actual: r.cantidad_actual, cantidad_minima: r.cantidad_minima }
}

async function guardarEdicion(id: number) {
  error.value = ''
  try {
    await api.patch(`/repuestos/${id}/`, edicion.value)
    editandoId.value = null
    await cargar()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'No se pudo guardar el cambio de stock.'
  }
}

async function eliminarRepuesto(r: Repuesto) {
  error.value = ''
  try {
    await api.delete(`/repuestos/${r.id}/`)
    await cargar()
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? 'No se pudo eliminar el repuesto.'
  }
}

onMounted(cargar)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>Stock de repuestos</h2>
      <button
        v-if="auth.esJefe"
        class="btn-icono"
        :class="{ 'boton-secundario': mostrarForm }"
        @click="mostrarForm = !mostrarForm"
      >
        <IconClose v-if="mostrarForm" aria-hidden="true" />
        <IconAdd v-else aria-hidden="true" />
        {{ mostrarForm ? 'Cancelar' : 'Nuevo repuesto' }}
      </button>
    </div>

    <form v-if="mostrarForm && auth.esJefe" class="nuevo-repuesto" @submit.prevent="crearRepuesto">
      <input v-model="nuevoRepuesto.codigo" placeholder="Código" required />
      <input v-model="nuevoRepuesto.descripcion" placeholder="Descripción" required />
      <input v-model.number="nuevoRepuesto.cantidad_actual" type="number" placeholder="Cantidad actual" />
      <input v-model.number="nuevoRepuesto.cantidad_minima" type="number" placeholder="Cantidad mínima" />
      <button type="submit">Guardar</button>
    </form>
    <p v-if="error" class="error">{{ error }}</p>

    <div class="filtros">
      <input v-model="busqueda" placeholder="Buscar por código o descripción…" @input="cargar" />
      <label>
        <input type="checkbox" v-model="soloStockBajo" @change="cargar" />
        Solo stock bajo
      </label>
    </div>

    <table v-if="!cargando">
      <thead>
        <tr>
          <th>Código</th>
          <th>Descripción</th>
          <th>Cantidad actual</th>
          <th>Cantidad mínima</th>
          <th>Costo sugerido</th>
          <th>Precio de venta sugerido</th>
          <th v-if="auth.esJefe"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in repuestos" :key="r.id" :class="{ 'stock-bajo': r.stock_bajo }">
          <td>{{ r.codigo }}</td>
          <td>{{ r.descripcion }}</td>
          <template v-if="editandoId === r.id">
            <td><input v-model.number="edicion.cantidad_actual" type="number" /></td>
            <td><input v-model.number="edicion.cantidad_minima" type="number" /></td>
            <td colspan="2" class="hint">Costo y precio se cargan importando la planilla del proveedor.</td>
            <td class="acciones">
              <button @click="guardarEdicion(r.id)">Guardar</button>
              <button class="link-btn" @click="editandoId = null">Cancelar</button>
            </td>
          </template>
          <template v-else>
            <td>
              {{ r.cantidad_actual }}
              <span v-if="r.stock_bajo" class="badge badge-bloqueado">bajo</span>
            </td>
            <td>{{ r.cantidad_minima }}</td>
            <td>
              <span v-if="r.precio_costo_sugerido">
                ${{ r.precio_costo_sugerido }} <span class="hint">({{ r.proveedor_sugerido_nombre }}, más barato)</span>
              </span>
              <span v-else class="hint">Sin proveedor cargado</span>
            </td>
            <td>{{ r.precio_venta_sugerido ? `$${r.precio_venta_sugerido}` : '—' }}</td>
            <td v-if="auth.esJefe" class="acciones">
              <button class="link-btn" @click="empezarEdicion(r)">Editar</button>
              <button class="link-btn" @click="eliminarRepuesto(r)">Eliminar</button>
            </td>
          </template>
        </tr>
        <tr v-if="repuestos.length === 0">
          <td colspan="7">No hay repuestos para mostrar.</td>
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
.nuevo-repuesto {
  display: grid;
  grid-template-columns: 1fr 2fr 1fr 1fr auto;
  gap: 0.5rem;
  background: white;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
}
.filtros {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
  font-size: 0.85rem;
}
.filtros input[type='text'],
.filtros input:not([type]) {
  flex: 1;
}
.stock-bajo {
  background: #fef2f2;
}
.acciones {
  display: flex;
  gap: 0.5rem;
}
.acciones input {
  width: 70px;
}
.link-btn {
  background: none;
  color: #0f172a;
  text-decoration: underline;
  padding: 0.2rem 0.4rem;
  font-size: 0.8rem;
}
.error {
  color: #991b1b;
  font-size: 0.85rem;
}
</style>
