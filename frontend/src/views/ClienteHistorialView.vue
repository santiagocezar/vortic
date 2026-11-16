<script setup lang="ts">
// HU-10/CU-06: buscar un cliente y ver el listado completo de sus
// órdenes anteriores (todas, no solo las abiertas — a diferencia del
// listado principal de OrdenesView, acá interesa el historial completo).
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/client'
import BuscadorCombobox from '../components/BuscadorCombobox.vue'
import { etiquetaEstado } from '../utils/estados'

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

const clienteElegido = ref<Cliente | null>(null)
const ordenes = ref<OrdenListado[]>([])
const cargando = ref(false)

async function cargarClientes(q: string): Promise<Cliente[]> {
  const { data } = await api.get('/clientes/', { params: { search: q } })
  return data
}

const etiquetaCliente = (c: Cliente) => `${c.razon_social} (${c.telefono})`
const claveCliente = (c: Cliente) => c.id

// Elegir un cliente trae su historial; escribir de nuevo (el buscador emite
// null) limpia el resultado anterior.
watch(clienteElegido, async (c) => {
  ordenes.value = []
  if (!c) return
  cargando.value = true
  try {
    const { data } = await api.get('/ordenes/', { params: { cliente: c.id } })
    ordenes.value = data
  } finally {
    cargando.value = false
  }
})
</script>

<template>
  <div class="page">
    <h2>Historial de cliente</h2>

    <div class="buscador">
      <BuscadorCombobox
        v-model="clienteElegido"
        :cargar="cargarClientes"
        :etiqueta="etiquetaCliente"
        :clave="claveCliente"
        etiqueta-accesible="Buscar cliente por nombre o teléfono"
        placeholder="Buscar cliente por nombre o teléfono…"
        name="cliente"
        mensaje-error="No se pudo buscar clientes. Reintentá escribiendo de nuevo."
      />
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
          <tr v-for="o in ordenes" :key="o.id" class="fila-orden" @click="router.push({ name: 'orden-detalle', params: { id: o.id } })">
            <td>OT-{{ String(o.id).padStart(4, '0') }}</td>
            <td>{{ o.tipo_equipo ?? '—' }}</td>
            <td>{{ new Date(o.fecha_ingreso).toLocaleDateString('es-AR') }}</td>
            <td>
              <span class="badge" :class="`badge-${o.estado}`">{{ etiquetaEstado(o.estado) }}</span>
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
  margin-bottom: 1.5rem;
  max-width: 400px;
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
