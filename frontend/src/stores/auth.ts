import { defineStore } from 'pinia'
import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'

// El token de acceso (el que viaja en cada pedido) vive solo en memoria.
// El token de refresco, el usuario y el rol se guardan en sessionStorage:
// así recargar la página no cierra la sesión, pero cerrar la pestaña sí.
const CLAVE = 'vortic-sesion'

interface SesionGuardada {
  refreshToken: string
  username: string
  rol: 'jefe' | 'tecnico'
}

function leerSesion(): SesionGuardada | null {
  try {
    const raw = sessionStorage.getItem(CLAVE)
    return raw ? (JSON.parse(raw) as SesionGuardada) : null
  } catch {
    return null
  }
}

function guardarSesion(s: SesionGuardada | null) {
  try {
    if (s) sessionStorage.setItem(CLAVE, JSON.stringify(s))
    else sessionStorage.removeItem(CLAVE)
  } catch {
    // Navegador sin sessionStorage (modo privado estricto): la sesión dura
    // hasta recargar, como antes.
  }
}

const previa = leerSesion()

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: null as string | null,
    refreshToken: (previa?.refreshToken ?? null) as string | null,
    username: (previa?.username ?? null) as string | null,
    // HU-06: el rol decide si se muestran los formularios de alta/edición
    // (Jefe de Taller) o solo lectura y tareas operativas (Técnico).
    rol: (previa?.rol ?? null) as 'jefe' | 'tecnico' | null,
  }),
  getters: {
    estaAutenticado: (state) => !!state.accessToken,
    puedeRestaurar: (state) => !state.accessToken && !!state.refreshToken,
    esJefe: (state) => state.rol === 'jefe',
  },
  actions: {
    async login(username: string, password: string) {
      const { data } = await axios.post(`${API_URL}/token/`, { username, password })
      this.accessToken = data.access
      this.refreshToken = data.refresh
      this.username = data.username
      this.rol = data.rol
      guardarSesion({ refreshToken: data.refresh, username: data.username, rol: data.rol })
    },
    async refrescarToken() {
      if (!this.refreshToken) throw new Error('Sin refresh token')
      const { data } = await axios.post(`${API_URL}/token/refresh/`, { refresh: this.refreshToken })
      this.accessToken = data.access
    },
    // Al recargar la página: pide un token de acceso nuevo con el de
    // refresco guardado. Si venció, se limpia todo y va al login.
    async restaurar(): Promise<boolean> {
      try {
        await this.refrescarToken()
        return true
      } catch {
        this.logout()
        return false
      }
    },
    logout() {
      this.accessToken = null
      this.refreshToken = null
      this.username = null
      this.rol = null
      guardarSesion(null)
    },
  },
})
