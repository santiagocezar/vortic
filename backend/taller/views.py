import csv
import io
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from urllib.parse import quote

from clientes.models import numero_whatsapp
from .models import (
    Equipo, Repuesto, OrdenTrabajo, OrdenRepuesto, SesionHoras, HistorialEstado,
    Proveedor, PrecioProveedor,
)
from .serializers import (
    EquipoSerializer, RepuestoSerializer, OrdenRepuestoSerializer,
    SesionHorasSerializer, OrdenTrabajoListSerializer, OrdenTrabajoDetailSerializer,
    ProveedorSerializer, PrecioProveedorSerializer,
)
from .permissions import PuedeOperarOrden
from .priorizacion import solicitar_repriorizacion
from usuarios.permissions import EsJefeOSoloLectura


# No existe un formato estándar de planilla de precios entre proveedores
# (cada uno manda la suya con sus propios nombres de columna), así que en
# vez de adivinar con una lista fija de sinónimos, el flujo es: se leen
# los encabezados reales de la planilla (_leer_headers_y_filas), se
# sugiere una asociación por similitud de nombre (_sugerir_mapeo) y el
# usuario la confirma o la corrige (previsualizar_planilla). Una vez
# confirmada queda guardada en Proveedor.mapeo_columnas para la próxima
# importación de ese mismo proveedor.
_SINONIMOS_COLUMNA = {
    'codigo': ['codigo', 'code', 'cod', 'sku', 'id', 'item', 'articulo', 'nro', 'numero', 'referencia'],
    'descripcion': ['descripcion', 'description', 'desc', 'detalle', 'producto', 'product', 'nombre', 'name'],
    'precio': [
        'precio', 'preciocosto', 'costo', 'cost', 'price', 'valor', 'importe', 'pvp',
        'preciounitario', 'preciounit', 'preciolista', 'unitprice', 'unitcost',
    ],
}


def _normalizar_header(h) -> str:
    if h is None:
        return ''
    texto = str(h).strip().lower()
    for a, b in (('á', 'a'), ('é', 'e'), ('í', 'i'), ('ó', 'o'), ('ú', 'u')):
        texto = texto.replace(a, b)
    for c in (' ', '_', '-', '.', '/', '\\', '#', '$', '%'):
        texto = texto.replace(c, '')
    return texto


def _sugerir_mapeo(headers: list[str]) -> dict:
    """Heurística de auto-sugerencia: no adivina el archivo, solo propone
    a qué columna real corresponde cada campo — el usuario la confirma."""
    normalizados = [(h, _normalizar_header(h)) for h in headers if h]
    sugerencia = {}
    for campo, sinonimos in _SINONIMOS_COLUMNA.items():
        encontrado = next((h for h, norm in normalizados if norm in sinonimos), None)
        if not encontrado:
            encontrado = next((h for h, norm in normalizados if any(s in norm for s in sinonimos)), None)
        if not encontrado:
            # Abreviaturas cortas (p. ej. "Ref." para "referencia"): alcanza
            # con que el encabezado sea el principio de algún sinónimo.
            encontrado = next(
                (h for h, norm in normalizados if len(norm) >= 3 and any(s.startswith(norm) for s in sinonimos)),
                None,
            )
        sugerencia[campo] = encontrado
    return sugerencia


def _leer_headers_y_filas(archivo) -> tuple[list[str], list[dict]]:
    """Lee un .csv o .xlsx subido tal cual viene (sin normalizar ni
    adivinar columnas) y devuelve (encabezados, filas) con las filas
    como dict {encabezado_real: valor}."""
    nombre = archivo.name.lower()
    if nombre.endswith('.csv'):
        contenido = archivo.read().decode('utf-8-sig')
        lector = csv.DictReader(io.StringIO(contenido))
        headers = [h for h in (lector.fieldnames or []) if h]
        return headers, list(lector)
    if nombre.endswith('.xlsx'):
        import openpyxl
        try:
            wb = openpyxl.load_workbook(archivo, data_only=True)
        except Exception:
            # Archivo corrupto, con contraseña, o con extensión .xlsx pero
            # contenido que en realidad no es un .xlsx válido: openpyxl
            # tira excepciones internas (BadZipFile, KeyError, etc.) que no
            # son ValueError — sin este catch, esto tiraba un 500 en vez
            # del 400 prolijo que se devuelve para el resto de los casos.
            raise ValueError('No se pudo leer el archivo .xlsx (¿está dañado o no es realmente un Excel?).')
        filas_iter = wb.active.iter_rows(values_only=True)
        try:
            headers_crudos = [str(h).strip() if h else '' for h in next(filas_iter)]
        except StopIteration:
            return [], []
        # zip primero contra los encabezados crudos (misma posición que las
        # columnas reales) y recién después se descartan las columnas sin
        # nombre, para no desalinear código/precio con la fila.
        filas = [
            {h: v for h, v in zip(headers_crudos, fila) if h}
            for fila in filas_iter
        ]
        headers = [h for h in headers_crudos if h]
        return headers, filas
    raise ValueError('Formato no soportado: subí un archivo .csv o .xlsx.')


class EquipoViewSet(viewsets.ModelViewSet):
    """HU-06: alta/edición es solo del Jefe; el Técnico puede consultar."""
    queryset = Equipo.objects.select_related('cliente').all()
    serializer_class = EquipoSerializer
    permission_classes = [IsAuthenticated, EsJefeOSoloLectura]


class ProveedorViewSet(viewsets.ModelViewSet):
    """HU-06: alta de proveedores e importación de precios son solo del
    Jefe; el Técnico puede ver proveedores y precios cargados."""
    queryset = Proveedor.objects.all()
    serializer_class = ProveedorSerializer
    permission_classes = [IsAuthenticated, EsJefeOSoloLectura]

    def destroy(self, request, *args, **kwargs):
        # PrecioProveedor.proveedor es PROTECT: un proveedor que ya tuvo
        # aunque sea una planilla de precios importada no se puede borrar
        # (dejaría precios históricos huérfanos) — sin este catch, Django
        # tira ProtectedError sin manejar y DRF lo devuelve como 500.
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {'detail': 'No se puede eliminar: el proveedor tiene precios cargados. Marcalo como inactivo en su lugar.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser])
    def previsualizar_planilla(self, request, pk=None):
        """
        Paso 1 de la importación (no guarda nada): lee la planilla subida
        (campo `archivo`) y devuelve sus encabezados reales tal cual
        vienen, unas filas de muestra y una sugerencia de a qué columna
        corresponde código/descripción/precio. Si este proveedor ya tiene
        un mapeo guardado de una importación anterior y esos encabezados
        siguen estando en la planilla, se reusa ese en vez de re-adivinar.
        El frontend muestra esto para que el usuario confirme o corrija
        antes de importar de verdad (importar_precios).
        """
        proveedor = self.get_object()
        archivo = request.FILES.get('archivo')
        if not archivo:
            return Response({'detail': 'Falta el archivo (campo "archivo").'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            headers, filas = _leer_headers_y_filas(archivo)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        if not headers:
            return Response({'detail': 'No se encontraron encabezados en la planilla.'}, status=status.HTTP_400_BAD_REQUEST)

        mapeo_guardado = proveedor.mapeo_columnas or {}
        mapeo_sigue_valido = mapeo_guardado.get('codigo') in headers and mapeo_guardado.get('precio') in headers
        sugerencia = mapeo_guardado if mapeo_sigue_valido else _sugerir_mapeo(headers)

        return Response({
            'headers': headers,
            'muestra': filas[:5],
            'sugerencia': sugerencia,
            'total_filas': len(filas),
            'mapeo_reutilizado': mapeo_sigue_valido,
        })

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser])
    def importar_precios(self, request, pk=None):
        """
        Paso 2: importa de verdad. Además del archivo (`archivo`), recibe
        qué columna real de la planilla es cada campo — `col_codigo`
        (obligatoria), `col_descripcion` (opcional, solo se usa si el
        repuesto todavía no existe en el catálogo) y `col_precio`
        (obligatoria) — confirmadas por el usuario en previsualizar_planilla.
        Si el repuesto no existe se crea con cantidad 0 (se ajusta después
        desde Stock); si el precio ya existía para este proveedor, se
        actualiza (no se duplica). El mapeo confirmado queda guardado en
        el proveedor para pre-completar la próxima importación.
        """
        proveedor = self.get_object()
        archivo = request.FILES.get('archivo')
        col_codigo = request.data.get('col_codigo')
        col_descripcion = request.data.get('col_descripcion') or None
        col_precio = request.data.get('col_precio')

        if not archivo:
            return Response({'detail': 'Falta el archivo (campo "archivo").'}, status=status.HTTP_400_BAD_REQUEST)
        if not col_codigo or not col_precio:
            return Response(
                {'detail': 'Falta indicar qué columna de la planilla es el código y cuál es el precio.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            headers, filas = _leer_headers_y_filas(archivo)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        columnas_invalidas = [
            c for c in (col_codigo, col_precio, col_descripcion) if c and c not in headers
        ]
        if columnas_invalidas:
            return Response(
                {'detail': f'Estas columnas no están en la planilla: {", ".join(columnas_invalidas)}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        creados, actualizados, errores = 0, 0, []
        with transaction.atomic():
            for i, fila in enumerate(filas, start=2):  # fila 1 es el encabezado
                codigo_raw = fila.get(col_codigo)
                codigo = str(codigo_raw).strip() if codigo_raw not in (None, '') else None
                precio_raw = fila.get(col_precio)
                if not codigo or precio_raw in (None, ''):
                    errores.append(f'Fila {i}: falta código o precio, se omitió.')
                    continue
                try:
                    precio = Decimal(str(precio_raw).replace(',', '.'))
                except InvalidOperation:
                    errores.append(f'Fila {i}: precio inválido ({precio_raw!r}), se omitió.')
                    continue
                if precio <= 0:
                    errores.append(f'Fila {i}: precio debe ser mayor a cero, se omitió.')
                    continue

                descripcion_raw = fila.get(col_descripcion) if col_descripcion else None
                descripcion = str(descripcion_raw).strip() if descripcion_raw not in (None, '') else codigo
                repuesto, _ = Repuesto.objects.get_or_create(
                    codigo=codigo, defaults={'descripcion': descripcion},
                )
                _, creado_precio = PrecioProveedor.objects.update_or_create(
                    repuesto=repuesto, proveedor=proveedor,
                    defaults={'precio_costo': precio},
                )
                if creado_precio:
                    creados += 1
                else:
                    actualizados += 1

        proveedor.mapeo_columnas = {'codigo': col_codigo, 'descripcion': col_descripcion, 'precio': col_precio}
        proveedor.save(update_fields=['mapeo_columnas'])

        return Response({
            'precios_creados': creados,
            'precios_actualizados': actualizados,
            'filas_con_error': errores,
        })


class PrecioProveedorViewSet(viewsets.ModelViewSet):
    """CRUD manual de precios, por si hace falta corregir uno sin reimportar la planilla entera.
    HU-06: solo el Jefe corrige precios; el Técnico puede consultarlos."""
    queryset = PrecioProveedor.objects.select_related('proveedor', 'repuesto').all()
    serializer_class = PrecioProveedorSerializer
    permission_classes = [IsAuthenticated, EsJefeOSoloLectura]


class RepuestoViewSet(viewsets.ModelViewSet):
    """HU-11 (ver stock) / HU-12 (actualizar stock). HU-06: alta/edición/
    baja del catálogo y ajuste manual de stock son solo del Jefe; el
    Técnico puede consultar el stock."""
    queryset = Repuesto.objects.prefetch_related('precios_proveedor__proveedor').all()
    serializer_class = RepuestoSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['codigo', 'descripcion']
    permission_classes = [IsAuthenticated, EsJefeOSoloLectura]

    def destroy(self, request, *args, **kwargs):
        # HU-12, criterio 04: no se puede eliminar un repuesto asociado a una orden abierta.
        repuesto = self.get_object()
        abiertas = OrdenRepuesto.objects.filter(
            repuesto=repuesto,
            orden__estado__in=[OrdenTrabajo.PENDIENTE, OrdenTrabajo.EN_CURSO, OrdenTrabajo.BLOQUEADO],
        ).exists()
        if abiertas:
            return Response(
                {'detail': 'No se puede eliminar: el repuesto está asociado a una orden abierta.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            # OrdenRepuesto.repuesto es PROTECT: aunque no haya órdenes
            # ABIERTAS con este repuesto, alguna orden TERMINADA puede
            # seguir referenciándolo (es el historial de qué se usó) — sin
            # este catch, borrar ese repuesto tiraba un 500 en vez de un
            # error claro.
            return Response(
                {'detail': 'No se puede eliminar: el repuesto está usado en el historial de alguna orden.'},
                status=status.HTTP_400_BAD_REQUEST,
            )


class OrdenTrabajoViewSet(viewsets.ModelViewSet):
    """
    CU-01 a CU-08. El listado (HU-05/HU-06/HU-13) usa un serializer
    liviano y soporta ?estado= y ?ordering=-indice_prioridad; el detalle
    trae repuestos, horas e historial completos.
    """
    queryset = OrdenTrabajo.objects.select_related('cliente', 'equipo').all()
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['indice_prioridad', 'fecha_ingreso']
    permission_classes = [IsAuthenticated, PuedeOperarOrden]
    # OJO: sin `ordering` de clase a propósito. SQLite y PostgreSQL tratan
    # distinto los NULL al ordenar DESC (SQLite los deja al final, Postgres
    # los pone primero por defecto) — el orden por defecto se arma abajo
    # con nulls_last explícito para que HU-13/criterio 03 ("sin costo
    # estimado, al final") valga en los dos motores.

    def get_serializer_class(self):
        return OrdenTrabajoDetailSerializer if self.action in (
            'retrieve', 'create', 'update', 'partial_update'
        ) else OrdenTrabajoListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        estado = self.request.query_params.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        cliente = self.request.query_params.get('cliente')
        if cliente:
            # HU-10/CU-06: historial de un cliente puntual — acá sí interesa
            # ver TODAS sus órdenes (incluidas las Terminadas), así que no
            # se aplica el order_by de prioridad; se ordena por fecha.
            # ?cliente= no numérico (típicamente escrito a mano) rompía con
            # un 500 en vez de devolver vacío: se valida antes de filtrar.
            if not str(cliente).isdigit():
                return qs.none()
            qs = qs.filter(cliente_id=cliente)
            if not self.request.query_params.get('ordering'):
                qs = qs.order_by('-fecha_ingreso')
            return qs
        if not self.request.query_params.get('ordering'):
            qs = qs.order_by(F('indice_prioridad').desc(nulls_last=True))
        return qs

    def perform_create(self, serializer):
        # HU-01, criterio 03: la orden nueva entra con estado Pendiente por defecto (default del modelo).
        serializer.save()

    @action(detail=True, methods=['post'])
    def cambiar_estado(self, request, pk=None):
        """CU-02: cambia el estado y deja registro en HistorialEstado."""
        orden = self.get_object()
        nuevo_estado = request.data.get('estado')
        motivo = request.data.get('motivo_bloqueo', '')

        if nuevo_estado not in dict(OrdenTrabajo.ESTADOS):
            return Response({'detail': 'Estado inválido.'}, status=status.HTTP_400_BAD_REQUEST)
        if nuevo_estado == OrdenTrabajo.BLOQUEADO and not motivo:
            return Response(
                {'detail': 'El motivo de bloqueo es obligatorio (HU-04).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        estado_anterior = orden.estado
        orden.estado = nuevo_estado
        # Si sale de Bloqueado, el motivo viejo ya no aplica — dejarlo
        # pisaba el badge de estado con un motivo de un bloqueo anterior
        # ya resuelto (ej. "En curso" mostrando el motivo de un bloqueo
        # pasado).
        orden.motivo_bloqueo = motivo if nuevo_estado == OrdenTrabajo.BLOQUEADO else ''
        # Hallazgo G (revisión de testing práctico): reabrir una orden
        # Terminada (ej. el cliente la trajo de vuelta) no limpiaba
        # fecha_aviso_cliente — el detalle seguía mostrando "Avisado el..."
        # de la notificación vieja aunque el trabajo ya no estuviera listo,
        # mensaje confuso en el mostrador si alguien vuelve a mirar la orden.
        if estado_anterior == OrdenTrabajo.TERMINADO and nuevo_estado != OrdenTrabajo.TERMINADO:
            orden.fecha_aviso_cliente = None
        orden.save()

        HistorialEstado.objects.create(
            orden=orden,
            estado_anterior=estado_anterior,
            estado_nuevo=nuevo_estado,
            usuario=request.user,
        )

        return Response(OrdenTrabajoDetailSerializer(orden).data)

    @action(detail=True, methods=['post'])
    def registrar_repuesto(self, request, pk=None):
        """
        Wrapper que deja la lógica real intacta en `_registrar_repuesto`
        (ver su docstring) y solo agrega el guard de
        FEATURE_STOCK_PROVEEDORES — así se reactiva borrando 3 líneas acá
        en vez de deshacer todo un método.
        """
        if not settings.FEATURE_STOCK_PROVEEDORES:
            return Response(
                {'detail': 'La función de repuestos/stock está desactivada temporalmente.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return self._registrar_repuesto(request, pk)

    def _registrar_repuesto(self, request, pk=None):
        """
        HU-07/CU-04: agrega un repuesto y descuenta stock (advierte si no
        alcanza, pero permite). El proveedor de esta compra puntual se
        elige explícitamente — no se asume el más barato: el frontend
        manda `precio_proveedor_id` (el resultado elegido en el buscador
        que recorre todas las listas cargadas) y acá se resuelve repuesto
        + proveedor + precio de costo a partir de esa fila puntual, no de
        una heurística. `repuesto` (sin proveedor) sigue existiendo como
        alternativa para repuestos que todavía no tienen ninguna lista
        cargada.
        """
        orden = self.get_object()
        precio_proveedor_id = request.data.get('precio_proveedor_id')
        repuesto_id = request.data.get('repuesto')
        descripcion_encargo = request.data.get('descripcion_encargo')

        try:
            cantidad = int(request.data.get('cantidad', 0))
        except (TypeError, ValueError):
            return Response({'detail': 'Cantidad inválida.'}, status=status.HTTP_400_BAD_REQUEST)
        if cantidad <= 0:
            return Response({'detail': 'La cantidad debe ser mayor a cero.'}, status=status.HTTP_400_BAD_REQUEST)
        if not precio_proveedor_id and not repuesto_id and not descripcion_encargo:
            return Response(
                {'detail': 'Elegí un repuesto (con o sin proveedor) o describí el repuesto por encargo (HU-07).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        warning = None
        repuesto = None
        proveedor = None
        precio_costo = None

        if precio_proveedor_id:
            try:
                precio = PrecioProveedor.objects.select_related('repuesto', 'proveedor').get(pk=precio_proveedor_id)
            except PrecioProveedor.DoesNotExist:
                return Response({'detail': 'Ese precio de proveedor ya no existe.'}, status=status.HTTP_400_BAD_REQUEST)
            repuesto = precio.repuesto
            proveedor = precio.proveedor
            precio_costo = precio.precio_costo
        elif repuesto_id:
            try:
                repuesto = Repuesto.objects.get(pk=repuesto_id)
            except Repuesto.DoesNotExist:
                return Response({'detail': 'El repuesto no existe.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            if repuesto is not None:
                # select_for_update + F() en vez de leer/restar/guardar en
                # Python: dos registrar_repuesto simultáneos sobre el mismo
                # repuesto (dos técnicos, dos órdenes distintas) ya no
                # pisan el descuento de stock del otro (lost update).
                repuesto = Repuesto.objects.select_for_update().get(pk=repuesto.pk)
                if repuesto.cantidad_actual < cantidad:
                    warning = 'La cantidad supera el stock disponible; se registra igual.'
                Repuesto.objects.filter(pk=repuesto.pk).update(cantidad_actual=F('cantidad_actual') - cantidad)
                repuesto.refresh_from_db(fields=['cantidad_actual'])

            item = OrdenRepuesto.objects.create(
                orden=orden, repuesto=repuesto, proveedor=proveedor, precio_costo=precio_costo,
                cantidad=cantidad, descripcion_encargo=descripcion_encargo,
            )
            # El descuento de stock se hizo con .update() (no dispara la
            # señal de Repuesto), así que la repriorización se pide acá.
            transaction.on_commit(lambda: solicitar_repriorizacion('repuesto_registrado'))

        data = OrdenRepuestoSerializer(item).data
        if warning:
            data['warning'] = warning
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def registrar_horas(self, request, pk=None):
        """HU-08/CU-04."""
        orden = self.get_object()
        try:
            horas = float(request.data.get('horas', 0))
        except (TypeError, ValueError):
            return Response({'detail': 'Horas inválidas.'}, status=status.HTTP_400_BAD_REQUEST)
        if horas <= 0:
            return Response({'detail': 'Las horas deben ser mayores a cero.'}, status=status.HTTP_400_BAD_REQUEST)
        sesion = SesionHoras.objects.create(orden=orden, horas=horas, usuario=request.user)
        return Response(SesionHorasSerializer(sesion).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def avisar_cliente(self, request, pk=None):
        """HU-09/CU-05: solo disponible si la orden está Terminada y el cliente tiene teléfono."""
        orden = self.get_object()
        if orden.estado != OrdenTrabajo.TERMINADO:
            return Response(
                {'detail': 'Solo se puede avisar cuando la orden está Terminada.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # WhatsApp necesita el número en formato internacional (549 + área +
        # número, sin 0 ni 15). Clientes cargados antes de la validación de
        # teléfono pueden no tener un número usable: se avisa en vez de abrir
        # WhatsApp sin destinatario.
        telefono = numero_whatsapp(orden.cliente.telefono)
        if not telefono:
            return Response(
                {'detail': 'El cliente no tiene un teléfono válido registrado (revisalo en la ficha del cliente).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mensaje = (
            f'Hola {orden.cliente.razon_social}, tu equipo '
            f'({orden.equipo.tipo_equipo if orden.equipo else "orden"}) '
            f'está listo para retirar. Orden OT-{orden.id:04d}.'
        )
        orden.fecha_aviso_cliente = timezone.now()
        orden.save(update_fields=['fecha_aviso_cliente'])

        whatsapp_url = f'https://wa.me/{telefono}?text={quote(mensaje)}'
        return Response({'whatsapp_url': whatsapp_url, 'mensaje': mensaje})
