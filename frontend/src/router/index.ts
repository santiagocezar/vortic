import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { FEATURE_STOCK_PROVEEDORES } from '../config/features'
import LoginView from '../views/LoginView.vue'
import OrdenesView from '../views/OrdenesView.vue'
import OrdenDetalleView from '../views/OrdenDetalleView.vue'
import StockView from '../views/StockView.vue'
import ProveedoresView from '../views/ProveedoresView.vue'
import ClienteHistorialView from '../views/ClienteHistorialView.vue'
import UsuariosView from '../views/UsuariosView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView },
    { path: '/', name: 'ordenes', component: OrdenesView, meta: { requiresAuth: true } },
    {
      path: '/ordenes/:id',
      name: 'orden-detalle',
      component: OrdenDetalleView,
      meta: { requiresAuth: true },
    },
    { path: '/stock', name: 'stock', component: StockView, meta: { requiresAuth: true } },
    {
      path: '/proveedores',
      name: 'proveedores',
      component: ProveedoresView,
      meta: { requiresAuth: true },
    },
    {
      path: '/clientes',
      name: 'clientes-historial',
      component: ClienteHistorialView,
      meta: { requiresAuth: true },
    },
    // Hallazgo F: gestión de usuarios (alta de técnicos, contraseñas, baja
    // lógica) sin depender de /admin/ de Django — solo Jefe (ver también
    // usuarios/permissions.py EsJefe, que rechaza esto igual del lado del
    // backend aunque alguien navegue directo a la URL).
    {
      path: '/usuarios',
      name: 'usuarios',
      component: UsuariosView,
      meta: { requiresAuth: true, soloJefe: true },
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (auth.puedeRestaurar) {
    await auth.restaurar()
  }
  if (to.meta.requiresAuth && !auth.estaAutenticado) {
    return { name: 'login' }
  }
  if (to.meta.soloJefe && !auth.esJefe) {
    return { name: 'ordenes' }
  }
  // Stock y proveedores se pueden apagar desde src/config/features.ts.
  if (!FEATURE_STOCK_PROVEEDORES && (to.name === 'stock' || to.name === 'proveedores')) {
    return { name: 'ordenes' }
  }
})

export default router
