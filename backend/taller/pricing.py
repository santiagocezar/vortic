"""
Cálculo de precio de venta a partir del precio de costo de proveedor.
Aislado del resto de la lógica (mismo criterio que priorizacion.py) para
que cambiar el margen o el criterio de "mejor precio" sea un cambio en
un solo lugar.

Regla vigente: 40% de ganancia sobre el precio de costo, para todos los
repuestos por igual. Cuando un repuesto tiene precio cargado de más de
un proveedor, se toma el más barato como precio de costo de referencia
(minimiza el costo del taller); ver `mejor_precio_proveedor`.
"""
from decimal import Decimal, ROUND_HALF_UP

MARGEN_GANANCIA = Decimal('0.40')  # 40%


def calcular_precio_venta(precio_costo: Decimal) -> Decimal:
    if precio_costo is None:
        return None
    precio = precio_costo * (Decimal('1') + MARGEN_GANANCIA)
    return precio.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def mejor_precio_proveedor(repuesto):
    """
    Devuelve la instancia de PrecioProveedor más barata para un repuesto,
    o None si no tiene ningún precio cargado. `precios_proveedor` ya
    viene ordenado por precio_costo ascendente (Meta.ordering del
    modelo), así que el primero es el más barato.
    """
    return repuesto.precios_proveedor.select_related('proveedor').first()
