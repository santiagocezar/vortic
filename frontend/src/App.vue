<script setup lang="ts">
import { useAuthStore } from './stores/auth'
import { useRouter } from 'vue-router'
import { FEATURE_STOCK_PROVEEDORES } from './config/features'

const auth = useAuthStore()
const router = useRouter()

function salir() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <header v-if="auth.estaAutenticado" class="topbar">
    <div class="left">
      <span class="brand">Vortic</span>
      <span v-if="!auth.esJefe" class="rol-badge">Técnico</span>
      <nav>
        <router-link to="/">Órdenes</router-link>
        <router-link to="/clientes">Clientes</router-link>
        <template v-if="FEATURE_STOCK_PROVEEDORES">
          <router-link to="/stock">Stock</router-link>
          <router-link to="/proveedores">Proveedores</router-link>
        </template>
        <router-link v-if="auth.esJefe" to="/usuarios">Usuarios</router-link>
      </nav>
    </div>
    <button @click="salir">Salir</button>
  </header>
  <main>
    <router-view />
  </main>
</template>

<style scoped>
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.5rem;
  background: #0f172a;
  color: white;
}
.left {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}
.brand {
  font-weight: 700;
  letter-spacing: 0.05em;
}
.rol-badge {
  font-size: 0.7rem;
  color: #94a3b8;
  border: 1px solid #334155;
  border-radius: 999px;
  padding: 0.1rem 0.5rem;
}
nav {
  display: flex;
  gap: 1rem;
}
nav a {
  color: #cbd5e1;
  text-decoration: none;
  font-size: 0.9rem;
}
nav a.router-link-exact-active {
  color: white;
  font-weight: 600;
}
</style>
