<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const username = ref('')
const password = ref('')
const error = ref('')
const cargando = ref(false)

async function submit() {
  error.value = ''
  cargando.value = true
  try {
    await auth.login(username.value, password.value)
    router.push({ name: 'ordenes' })
  } catch {
    error.value = 'Usuario o contraseña incorrectos.'
  } finally {
    cargando.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <form class="login-card" @submit.prevent="submit">
      <h1>Vortic</h1>
      <p class="subtitle">Sistema de gestión de taller oleohidráulico</p>
      <label>
        Usuario
        <input v-model="username" required autofocus />
      </label>
      <label>
        Contraseña
        <input v-model="password" type="password" required />
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" :disabled="cargando">
        {{ cargando ? 'Ingresando…' : 'Ingresar' }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.login-card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  width: 320px;
  padding: 2rem;
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}
h1 {
  margin: 0;
}
.subtitle {
  margin: 0 0 0.5rem;
  color: #64748b;
  font-size: 0.85rem;
}
label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.85rem;
  font-weight: 600;
}
.error {
  color: #991b1b;
  font-size: 0.85rem;
  margin: 0;
}
</style>
