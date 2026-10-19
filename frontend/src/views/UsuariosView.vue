<script setup lang="ts">
// Hallazgo F (revisión de testing práctico): antes de esto, dar de alta a
// un técnico o cambiarle la contraseña dependía de entrar a /admin/ de
// Django — una barrera real para un taller sin nadie técnico a mano en el
// día a día. Vista mínima, solo Jefe (guardado también en el router y en
// el backend: usuarios/permissions.py EsJefe).
import { ref, onMounted } from 'vue'
import api from '../api/client'

interface Usuario {
  id: number
  username: string
  rol: 'jefe' | 'tecnico'
  is_active: boolean
}

const usuarios = ref<Usuario[]>([])
const cargando = ref(false)
const mostrarForm = ref(false)
const guardando = ref(false)
const errorForm = ref('')

const nuevoUsuario = ref({ username: '', password: '', rol: 'tecnico' as 'jefe' | 'tecnico' })

async function cargar() {
  cargando.value = true
  try {
    const { data } = await api.get('/usuarios/')
    usuarios.value = data
  } finally {
    cargando.value = false
  }
}

async function crearUsuario() {
  errorForm.value = ''
  guardando.value = true
  try {
    await api.post('/usuarios/', nuevoUsuario.value)
    nuevoUsuario.value = { username: '', password: '', rol: 'tecnico' }
    mostrarForm.value = false
    await cargar()
  } catch (e: any) {
    const data = e?.response?.data
    errorForm.value = data ? Object.values(data).flat().join(' ') : 'No se pudo crear el usuario.'
  } finally {
    guardando.value = false
  }
}

async function alternarActivo(u: Usuario) {
  await api.patch(`/usuarios/${u.id}/`, { is_active: !u.is_active })
  await cargar()
}

onMounted(cargar)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>Usuarios</h2>
      <button @click="mostrarForm = !mostrarForm">
        {{ mostrarForm ? 'Cancelar' : '+ Nuevo usuario' }}
      </button>
    </div>

    <form v-if="mostrarForm" class="nuevo-usuario" @submit.prevent="crearUsuario">
      <input v-model="nuevoUsuario.username" placeholder="Usuario" required />
      <input v-model="nuevoUsuario.password" type="password" placeholder="Contraseña (mínimo 8 caracteres)" required />
      <select v-model="nuevoUsuario.rol">
        <option value="tecnico">Técnico</option>
        <option value="jefe">Jefe de Taller</option>
      </select>
      <p v-if="errorForm" class="error">{{ errorForm }}</p>
      <button type="submit" :disabled="guardando">{{ guardando ? 'Guardando…' : 'Crear' }}</button>
    </form>

    <table v-if="!cargando">
      <thead>
        <tr>
          <th>Usuario</th>
          <th>Rol</th>
          <th>Estado</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in usuarios" :key="u.id">
          <td>{{ u.username }}</td>
          <td>{{ u.rol === 'jefe' ? 'Jefe de Taller' : 'Técnico' }}</td>
          <td>{{ u.is_active ? 'Activo' : 'Inactivo' }}</td>
          <td>
            <button class="link-btn" @click="alternarActivo(u)">
              {{ u.is_active ? 'Desactivar' : 'Reactivar' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.page {
  max-width: 700px;
  margin: 2rem auto;
  padding: 0 1rem;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.nuevo-usuario {
  display: grid;
  gap: 0.5rem;
  background: white;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  max-width: 320px;
}
.link-btn {
  background: none;
  color: #0f172a;
  text-decoration: underline;
  padding: 0;
  font-size: 0.8rem;
}
.error {
  color: #991b1b;
  font-size: 0.85rem;
  margin: 0;
}
</style>
