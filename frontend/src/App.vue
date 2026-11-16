<script setup lang="ts">
import { useAuthStore } from './stores/auth'
import { useRouter } from 'vue-router'
import { FEATURE_STOCK_PROVEEDORES } from './config/features'
import IconLogout from '~icons/material-symbols/logout'

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
    <button class="salir" aria-label="Salir" title="Salir" @click="salir">
      <IconLogout aria-hidden="true" />
    </button>
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
.salir {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 44px;
  min-height: 44px;
  padding: 0.35rem;
  background: transparent;
  border: 1px solid #334155;
  color: #cbd5e1;
}
.salir:hover {
  background: #1e293b;
  color: white;
}
.salir svg {
  width: 1.15rem;
  height: 1.15rem;
  display: block;
}

@media (max-width: 640px) {
  .topbar {
    flex-wrap: nowrap;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    align-items: center;
  }
  .left {
    flex: 1 1 auto;
    min-width: 0;
    flex-wrap: nowrap;
    gap: 0.6rem;
  }
  .brand {
    font-size: 0.95rem;
  }
  .rol-badge {
    display: none;
  }
  nav {
    flex: 1 1 auto;
    flex-wrap: nowrap;
    gap: 0.85rem;
    overflow-x: auto;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
    /* Pista de que hay más destinos: sin esto, "Usuarios" y "Proveedores"
       desaparecen en silencio detrás del borde en un teléfono de 320px. */
    mask-image: linear-gradient(to right, #000 calc(100% - 20px), transparent);
    -webkit-mask-image: linear-gradient(to right, #000 calc(100% - 20px), transparent);
  }
  nav::-webkit-scrollbar {
    display: none;
  }
  nav a {
    white-space: nowrap;
    display: inline-flex;
    align-items: center;
    min-height: 44px;
  }
}
</style>
