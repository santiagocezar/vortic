<script setup lang="ts">
// HU-10/CU-06: buscar un cliente y ver el listado completo de sus
// órdenes anteriores (todas, no solo las abiertas — a diferencia del
// listado principal de OrdenesView, acá interesa el historial completo).
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/client'

const router = useRouter()

interface Cliente {
  id: number
  razon_social: string
  telefono: string
}

interface OrdenListado {
  id: number
  tipo_equipo: string | null
  estado: string
  motivo_bloqueo: string | null
  fecha_ingreso: string
  criticidad: number
}

const busqueda = ref('')
const sugerencias = ref<Cliente[]>([])
const clienteElegido = ref<Cliente | null>(null)
const ordenes = ref<OrdenListado[]>([])
const cargando = ref(false)
let debounceHandle: ReturnType<typeof setTimeout> | undefined

// Una búsqueda vieja que tarda más no debe pisar el resultado de una
// más nueva si el usuario ya siguió tipeando (mismo patrón que en
// OrdenesView.vue y OrdenDetalleView.vue).
let secuenciaBusqueda = 0

function onBuscarInput() {
  clienteElegido.value = null
  ordenes.value = []
  clearTimeout(debounceHandle)
  const q = busqueda.value.trim()
  if (q.length < 2) {
    sugerencias.value = []
    return
  }
  const idBusqueda = ++secuenciaBusqueda
  debounceHandle = setTimeout(async () => {
    const { data } = await api.get('/clientes/', { params: { search: q } })
    if (idBusqueda === secuenciaBusqueda) {
      sugerencias.value = data
    }
  }, 250)
}

async function elegirCliente(c: Cliente) {
  clienteElegido.value = c
  busqueda.value = `${c.razon_social} (${c.telefono})`
  sugerencias.value = []
  cargando.value = true
  try {
    const { data } = await api.get('/ordenes/', { params: { cliente: c.id } })
    ordenes.value = data
  } finally {
    cargando.value = false
  }
}
</script>

<template>
  <div class="page">
    <h2>Historial de cliente</h2>

    <div class="buscador">
      <input
        v-model="busqueda"
        placeholder="Buscar cliente por nombre o teléfono…"
        @input="onBuscarInput"
      />
      <ul v-if="sugerencias.length" class="sugerencias">
        <li v-for="c in sugerencias" :key="c.id" @click="elegirCliente(c)">
          {{ c.razon_social }} — {{ c.telefono }}
        </li>
      </ul>
    </div>

    <div v-if="clienteElegido" class="resultado">
      <h3>{{ clienteElegido.razon_social }}</h3>
      <p class="hint">{{ clienteElegido.telefono }}</p>

      <table v-if="!cargando">
        <thead>
          <tr>
            <th>Orden</th>
            <th>Equipo</th>
            <th>Ingreso</th>
            <th>Estado</th>
            <th>Criticidad</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="o in ordenes"
            :key="o.id"
            class="fila-orden"
            @click="router.push({ name: 'orden-detalle', params: { id: o.id } })"
          >
            <td>OT-{{ String(o.id).padStart(4, '0') }}</td>
            <td>{{ o.tipo_equipo ?? '—' }}</td>
            <td>{{ new Date(o.fecha_ingreso).toLocaleDateString('es-AR') }}</td>
            <td>
              <span class="badge" :class="`badge-${o.estado}`">{{ o.estado }}</span>
              <span v-if="o.motivo_bloqueo" class="motivo"> · {{ o.motivo_bloqueo }}</span>
            </td>
            <td>{{ o.criticidad }}/5</td>
          </tr>
          <tr v-if="ordenes.length === 0">
            <td colspan="5">Este cliente todavía no tiene órdenes registradas.</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-else class="hint">Buscá un cliente para ver sus órdenes anteriores.</p>
  </div>
</template>

<style scoped>
.page {
  max-width: 900px;
  margin: 2rem auto;
  padding: 0 1rem;
}
.buscador {
  position: relative;
  margin-bottom: 1.5rem;
}
.buscador input {
  width: 100%;
  max-width: 400px;
}
.sugerencias {
  position: absolute;
  z-index: 10;
  top: 100%;
  left: 0;
  width: 100%;
  max-width: 400px;
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
.resultado h3 {
  margin-bottom: 0.1rem;
}
.hint {
  color: #64748b;
  font-size: 0.85rem;
}
.fila-orden {
  cursor: pointer;
}
.fila-orden:hover {
  background: #f1f5f9;
}
.motivo {
  color: #991b1b;
  font-size: 0.8rem;
}
</style>
