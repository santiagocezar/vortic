// Etiquetas legibles de los estados de una orden. El backend devuelve los
// valores crudos (`en_curso`); la interfaz muestra el mismo concepto en
// español, sin guiones bajos, sin cambiar el valor que viaja a la API.
export const ETIQUETA_ESTADO: Record<string, string> = {
  pendiente: 'Pendiente',
  en_curso: 'En curso',
  bloqueado: 'Bloqueado',
  terminado: 'Terminado',
}

export function etiquetaEstado(estado: string): string {
  return ETIQUETA_ESTADO[estado] ?? estado
}
