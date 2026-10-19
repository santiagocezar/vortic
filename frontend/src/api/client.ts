import axios from 'axios'
import { useAuthStore } from '../stores/auth'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api',
})

// El token se guarda en memoria (Pinia), no en localStorage, y se manda
// en cada request por header Authorization (informe, sección 8.4).
api.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.accessToken) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`
  }
  return config
})

// Si varios requests reciben 401 al mismo tiempo (ej. una pantalla que
// dispara varios GET juntos con el access token ya vencido), todos
// esperan el MISMO refresh en vez de llamar a /token/refresh/ cada uno
// por su cuenta — evita llamadas duplicadas y, si en el futuro el
// refresh token rota (se invalida al usarlo), evita que un refresh pise
// el resultado de otro.
let refrescoEnCurso: Promise<void> | null = null

function refrescarUnaVez(auth: ReturnType<typeof useAuthStore>) {
  if (!refrescoEnCurso) {
    refrescoEnCurso = auth.refrescarToken().finally(() => {
      refrescoEnCurso = null
    })
  }
  return refrescoEnCurso
}

// Si el access token expiró, intenta refrescar una vez con el refresh token.
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const auth = useAuthStore()
    const original = error.config
    if (error.response?.status === 401 && auth.refreshToken && !original._retry) {
      original._retry = true
      try {
        await refrescarUnaVez(auth)
        original.headers.Authorization = `Bearer ${auth.accessToken}`
        return api(original)
      } catch {
        auth.logout()
        // Import dinámico (no estático) para evitar el ciclo
        // router → vistas → este archivo → router: así se resuelve recién
        // al ejecutarse, no al cargar el módulo. Sin este redirect, una
        // sesión vencida dejaba la pantalla actual pidiendo datos que
        // nunca llegan (spinner de "Cargando…" para siempre) en vez de
        // mandar al login.
        const { default: router } = await import('../router')
        router.push({ name: 'login' })
      }
    }
    return Promise.reject(error)
  },
)

export default api
