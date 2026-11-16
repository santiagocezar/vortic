<script setup lang="ts">
// Buscador con autocompletado accesible para cualquier entidad: el ARIA del
// combobox, las flechas, Enter/Escape y el anuncio de resultados viven acá
// una sola vez (Headless UI), y cada vista aporta solo cómo buscar, cómo
// etiquetar y cómo comparar sus ítems.
//
// El debounce y la guarda de secuencia también son parte del patrón: si el
// usuario sigue tipeando, una búsqueda vieja que tarda más no puede pisar el
// resultado de una más nueva (misma regla que DESIGN.md pide repetir).
import { computed, onUnmounted, ref, watch } from 'vue'
import { Combobox, ComboboxInput, ComboboxOption, ComboboxOptions } from '@headlessui/vue'
import IconSearch from '~icons/material-symbols/search'

// El ítem es opaco para el buscador: cada vista decide su forma y aporta
// `etiqueta` y `clave`. Se usa `any` en el borde porque `vue-tsc` no infiere
// genéricos a través de props con callbacks en plantillas; la seguridad de
// tipos vive en cada vista, donde el ítem sí está tipado.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Item = any

const props = defineProps<{
  modelValue: Item | null
  cargar: (q: string) => Promise<Item[]>
  etiqueta: (item: Item) => string
  clave: (item: Item) => string | number
  etiquetaAccesible: string
  placeholder?: string
  name?: string
  mensajeError?: string
  /** Caracteres mínimos antes de consultar la API. */
  minimo?: number
}>()

const MENSAJE_ERROR_POR_DEFECTO = 'No se pudo buscar. Reintentá escribiendo de nuevo.'

const emit = defineEmits<{
  'update:modelValue': [valor: Item | null]
}>()

defineSlots<{
  /** Contenido de cada opción; por defecto se usa `etiqueta(item)`. */
  opcion?: (props: { item: Item; active: boolean }) => unknown
}>()

const consulta = ref('')
const sugerencias = ref<Item[]>([])
const error = ref('')
let secuencia = 0
let debounce: ReturnType<typeof setTimeout> | undefined

function alEscribir(event: Event) {
  const valor = (event.target as HTMLInputElement).value
  consulta.value = valor
  error.value = ''
  // Escribir invalida la elección anterior: si no, se enviaría la entidad
  // vieja mientras el input muestra otro texto.
  emit('update:modelValue', null)
  clearTimeout(debounce)
  // Las sugerencias de la búsqueda anterior no deben quedar visibles
  // mientras se espera la nueva: mostrarían resultados de otro texto.
  sugerencias.value = []
  const q = valor.trim()
  if (q.length < (props.minimo ?? 2)) {
    secuencia += 1
    return
  }
  const idBusqueda = ++secuencia
  debounce = setTimeout(async () => {
    try {
      const items = await props.cargar(q)
      if (idBusqueda === secuencia) sugerencias.value = items
    } catch {
      if (idBusqueda === secuencia) {
        sugerencias.value = []
        error.value = props.mensajeError ?? MENSAJE_ERROR_POR_DEFECTO
      }
    }
  }, 250)
}

function alSeleccionar(item: Item | null) {
  emit('update:modelValue', item)
  if (item) {
    consulta.value = props.etiqueta(item)
    sugerencias.value = []
    error.value = ''
  }
}

// Una selección puesta desde afuera (ej.: se creó un cliente nuevo y se
// elige automáticamente) también tiene que reflejarse en el input.
watch(
  () => props.modelValue,
  (item) => {
    if (!item) return
    consulta.value = props.etiqueta(item)
    sugerencias.value = []
  },
)

// Headless UI muestra el valor elegido con esta función y, cuando no hay
// selección, deja el texto que el usuario está tipeando.
function textoMostrado(item: unknown): string {
  const valor = item as Item | null
  return valor ? props.etiqueta(valor) : consulta.value
}

function mismaClave(a: Item | null, b: Item | null): boolean {
  if (a == null || b == null) return a === b
  return props.clave(a) === props.clave(b)
}

const anuncio = computed(() => {
  const n = sugerencias.value.length
  if (!n) return ''
  return n === 1 ? '1 resultado encontrado' : `${n} resultados encontrados`
})

// Permite vaciar el buscador después de un alta sin remontar el componente.
function limpiar() {
  consulta.value = ''
  sugerencias.value = []
  error.value = ''
  secuencia += 1
  clearTimeout(debounce)
}

defineExpose({ limpiar })

onUnmounted(() => clearTimeout(debounce))
</script>

<template>
  <div class="buscador-combobox">
    <Combobox :model-value="modelValue" :by="mismaClave" nullable @update:model-value="alSeleccionar">
      <div class="campo-busqueda">
        <IconSearch aria-hidden="true" />
        <ComboboxInput :name="name" :aria-label="etiquetaAccesible" :placeholder="placeholder" :display-value="textoMostrado" @change="alEscribir" />
      </div>
      <ComboboxOptions v-if="sugerencias.length" class="sugerencias">
        <ComboboxOption v-for="item in sugerencias" :key="clave(item)" :value="item" as="template" v-slot="{ active }">
          <li :class="{ 'opcion-activa': active }">
            <slot name="opcion" :item="item" :active="active">{{ etiqueta(item) }}</slot>
          </li>
        </ComboboxOption>
      </ComboboxOptions>
    </Combobox>
    <p class="sr-only" role="status" aria-live="polite">{{ anuncio }}</p>
    <p v-if="error" class="error-busqueda" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
.buscador-combobox {
  position: relative;
  flex: 1 1 auto;
  min-width: 0;
}
.campo-busqueda {
  position: relative;
  display: flex;
  align-items: center;
}
.campo-busqueda svg {
  position: absolute;
  left: 0.6rem;
  width: 1rem;
  height: 1rem;
  color: #64748b;
  pointer-events: none;
}
.campo-busqueda input {
  width: 100%;
  padding-left: 2rem;
}
.sugerencias {
  position: absolute;
  z-index: 10;
  top: 100%;
  left: 0;
  right: 0;
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
.sugerencias li:hover,
.sugerencias li.opcion-activa {
  background: #f1f5f9;
}
.error-busqueda {
  color: #991b1b;
  font-size: 0.85rem;
  margin: 0.25rem 0 0;
}
</style>
