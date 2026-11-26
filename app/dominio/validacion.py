"""Validador del entorno: qué está mal, dónde y cómo arreglarlo.

``validar`` no modifica nada ni lanza excepciones por datos raros: recorre
el entorno y devuelve una lista de ``Aviso``. Los de gravedad «error»
impiden recorrer el entorno con garantías (un inicio dentro de un muro, una
escalera que lleva a una planta que no existe); los de gravedad «aviso»
conviene revisarlos pero pueden ser intencionados (una habitación sin
puerta, un paso estrecho).

Cada aviso lleva el id del elemento y de la planta, para que el editor
pueda llevar el cursor hasta el problema, y una sugerencia en lenguaje llano.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable

from app.core.i18n import _, _n, separador_decimal
from app.dominio import geometria as geo
from app.dominio.catalogo import TIPO_CAJA, Catalogo
from app.dominio.colocacion import PASO_MINIMO, comprobar, lote_de_comprobaciones
from app.dominio.geometria import Punto
from app.dominio.modelo import (
	ACUSTICAS,
	ESTADOS_ABERTURA,
	HOJAS,
	SUELOS,
	TIPOS_ABERTURA,
	TIPOS_CONECTOR,
	TIPOS_ESPACIO,
	TOLERANCIA_PARED,
	Abertura,
	Aviso,
	Conector,
	Entorno,
	Espacio,
	Planta,
	Posicion,
	hay_errores,
	segmentos_solidos,
)

__all__ = ["Aviso", "hay_errores", "resumen", "validar"]

log = logging.getLogger(__name__)

# Distancia mínima del punto de inicio a una pared para no empezar «dentro del muro».
MARGEN_INICIO = 0.2
# Una puerta más estrecha que esto no deja pasar con comodidad.
ANCHO_MINIMO_ABERTURA = 0.6


def _aviso(gravedad: str, codigo: str, mensaje: str, elemento: str = "", planta: str = "", sugerencia: str = "") -> Aviso:
	return Aviso(gravedad=gravedad, codigo=codigo, mensaje=mensaje, elemento_id=elemento, planta_id=planta, sugerencia=sugerencia)


def _contorno_valido(contorno: list[Punto]) -> str:
	"""Cadena vacía si el contorno vale; si no, el motivo."""
	if len(contorno) < 3:
		return _("tiene menos de tres vértices")
	if not geo.es_simple(contorno):
		return _("se corta a sí mismo o repite un vértice")
	if geo.area(contorno) < 0.01:
		return _("no encierra superficie")
	return ""


def _sobre_pared(planta: Planta, abertura: Abertura) -> bool:
	"""True si la abertura está sobre el lado de un espacio con paredes, de un macizo o sobre una pared suelta.

	Solo se miran los espacios cuya caja toca la de la abertura (índice
	espacial de la planta): antes cada puerta se cruzaba con todos los lados
	del barrio y comprobar un entorno importado tardaba minutos.
	"""
	x0, y0, x1, y1 = geo.caja((abertura.a, abertura.b))
	for espacio in planta.indice_espacios().en_caja(x0, y0, x1, y1, TOLERANCIA_PARED + 1e-6):
		if len(espacio.contorno) < 3 or not (espacio.cerrado or espacio.macizo):
			continue
		for indice, (a, b) in enumerate(espacio.lados()):
			if indice in espacio.lados_abiertos and not espacio.macizo:
				continue
			if geo.intervalo_sobre_segmento(a, b, abertura.a, abertura.b, TOLERANCIA_PARED) is not None:
				return True
	return any(geo.intervalo_sobre_segmento(p.a, p.b, abertura.a, abertura.b, TOLERANCIA_PARED) is not None for p in planta.paredes)


def _tiene_acceso(entorno: Entorno, planta: Planta, espacio: Espacio) -> bool:
	"""True si se puede entrar de algún modo: lado abierto, puerta, hueco, portal o conector."""
	lados = espacio.lados()
	if any(0 <= indice < len(lados) for indice in espacio.lados_abiertos):
		return True
	# Una abertura lejos de la caja del espacio no puede estar sobre ninguno de sus lados.
	margen = TOLERANCIA_PARED + 1e-6
	ex0, ey0, ex1, ey1 = espacio.caja()
	for abertura in planta.aberturas:
		if abertura.tipo == "ventana":
			continue
		(ax, ay), (bx, by) = abertura.a, abertura.b
		if min(ax, bx) > ex1 + margen or max(ax, bx) < ex0 - margen or min(ay, by) > ey1 + margen or max(ay, by) < ey0 - margen:
			continue
		for a, b in lados:
			if geo.intervalo_sobre_segmento(a, b, abertura.a, abertura.b, TOLERANCIA_PARED) is not None:
				return True
	for conector in entorno.conectores:
		for posicion in conector.posiciones():
			if posicion.planta == planta.id and espacio.contiene(posicion.x, posicion.y):
				return True
	return False


def _validar_ids(entorno: Entorno, avisos: list[Aviso]) -> None:
	cuenta = Counter(entorno.ids())
	if cuenta.get("", 0):
		avisos.append(
			_aviso(
				"error",
				"id_vacio",
				_("Hay {n} elementos sin identificador.").format(n=cuenta[""]),
				sugerencia=_("Guarde el entorno desde el editor para que se les asigne uno."),
			)
		)
	for identificador, veces in sorted(cuenta.items()):
		if identificador and veces > 1:
			avisos.append(
				_aviso(
					"error",
					"id_duplicado",
					_("El identificador «{id}» está repetido en {n} elementos.").format(id=identificador, n=veces),
					identificador,
					sugerencia=_("Duplique el elemento desde el editor en lugar de copiarlo a mano."),
				)
			)


def _validar_espacios(entorno: Entorno, planta: Planta, avisos: list[Aviso]) -> None:
	validos: list[Espacio] = []
	for espacio in planta.espacios:
		motivo = _contorno_valido(espacio.contorno)
		if motivo:
			avisos.append(
				_aviso(
					"error",
					"contorno_no_valido",
					_("El contorno de «{nombre}» {motivo}.").format(nombre=espacio.nombre or espacio.id, motivo=motivo),
					espacio.id,
					planta.id,
					_("Vuelva a trazar el espacio o bórrelo."),
				)
			)
			continue
		validos.append(espacio)
		for valor, tabla, clave in (
			(espacio.tipo, TIPOS_ESPACIO, "tipo"),
			(espacio.suelo, SUELOS, "suelo"),
			(espacio.acustica, ACUSTICAS, "acustica"),
		):
			if valor not in tabla:
				avisos.append(
					_aviso(
						"aviso",
						"valor_desconocido",
						_("«{nombre}» tiene un valor desconocido en «{clave}»: «{valor}».").format(
							nombre=espacio.nombre, clave=clave, valor=valor
						),
						espacio.id,
						planta.id,
						_("Elija uno de la lista en sus propiedades."),
					)
				)
		if any(not 0 <= indice < len(espacio.contorno) for indice in espacio.lados_abiertos):
			avisos.append(
				_aviso(
					"aviso",
					"lado_abierto_inexistente",
					_("«{nombre}» marca como abierto un lado que no existe.").format(nombre=espacio.nombre),
					espacio.id,
					planta.id,
					_("Revise sus lados abiertos."),
				)
			)
		if espacio.cerrado and not espacio.macizo and not _tiene_acceso(entorno, planta, espacio):
			avisos.append(
				_aviso(
					"aviso",
					"espacio_sin_acceso",
					_("«{nombre}» está cerrado y no tiene ninguna puerta ni hueco: no se puede entrar.").format(nombre=espacio.nombre),
					espacio.id,
					planta.id,
					_("Añádale una puerta o márquelo como macizo si no se va a entrar."),
				)
			)
	con_paredes = [e for e in validos if e.cerrado or e.macizo]
	# Parejas que se pisan: solo se miran las de cajas que se tocan, que da el índice espacial
	# (antes, todas con todas: con 3.000 espacios, cuatro millones y medio de parejas).
	posicion = {id(espacio): numero for numero, espacio in enumerate(con_paredes)}
	indice = planta.indice_espacios()
	for i, uno in enumerate(con_paredes):
		x0, y0, x1, y1 = uno.caja()
		cercanos = sorted(posicion[id(otro)] for otro in indice.en_caja(x0, y0, x1, y1) if posicion.get(id(otro), -1) > i)
		for otro in (con_paredes[j] for j in cercanos):
			if geo.cajas_se_tocan(uno.caja(), otro.caja()) and geo.area_interseccion(uno.contorno, otro.contorno) > 0.01:
				avisos.append(
					_aviso(
						"aviso",
						"espacios_solapados",
						_("«{a}» y «{b}» se pisan.").format(a=uno.nombre, b=otro.nombre),
						uno.id,
						planta.id,
						_("Mueva o cambie de medida uno de los dos para que solo compartan pared."),
					)
				)


def _validar_aberturas_y_paredes(planta: Planta, avisos: list[Aviso]) -> None:
	for abertura in planta.aberturas:
		nombre = abertura.nombre or abertura.id
		if abertura.ancho < 0.05:
			avisos.append(
				_aviso(
					"error",
					"abertura_no_valida",
					_("«{nombre}» no tiene anchura.").format(nombre=nombre),
					abertura.id,
					planta.id,
					_("Bórrela y vuelva a crearla."),
				)
			)
			continue
		if not _sobre_pared(planta, abertura):
			avisos.append(
				_aviso(
					"error",
					"abertura_sin_pared",
					_("«{nombre}» no está sobre ninguna pared.").format(nombre=nombre),
					abertura.id,
					planta.id,
					_("Muévala sobre el lado de una habitación o bórrela."),
				)
			)
		elif abertura.tipo != "ventana" and abertura.ancho < ANCHO_MINIMO_ABERTURA:
			avisos.append(
				_aviso(
					"aviso",
					"abertura_estrecha",
					_("«{nombre}» mide solo {ancho} metros de ancho.").format(
						nombre=nombre, ancho=f"{abertura.ancho:.2f}".replace(".", separador_decimal())
					),
					abertura.id,
					planta.id,
					_("Una puerta normal mide entre 0,70 y 0,90 metros."),
				)
			)
		for valor, tabla, clave in (
			(abertura.tipo, TIPOS_ABERTURA, "tipo"),
			(abertura.estado, ESTADOS_ABERTURA, "estado"),
			(abertura.hoja, HOJAS, "hoja"),
		):
			if valor not in tabla:
				avisos.append(
					_aviso(
						"aviso",
						"valor_desconocido",
						_("«{nombre}» tiene un valor desconocido en «{clave}»: «{valor}».").format(nombre=nombre, clave=clave, valor=valor),
						abertura.id,
						planta.id,
						_("Elija uno de la lista en sus propiedades."),
					)
				)
	for pared in planta.paredes:
		if geo.distancia(pared.a, pared.b) < 0.01:
			avisos.append(
				_aviso(
					"error",
					"pared_no_valida",
					_("La pared «{nombre}» no tiene longitud.").format(nombre=pared.nombre or pared.id),
					pared.id,
					planta.id,
					_("Bórrela."),
				)
			)


def _validar_objetos(
	entorno: Entorno,
	planta: Planta,
	catalogo: Catalogo,
	con_catalogo: bool,
	paso_minimo: float,
	avisos: list[Aviso],
	avance: Callable[[int], None] | None = None,
) -> None:
	for numero, objeto in enumerate(planta.objetos):
		if avance is not None and numero and numero % 25 == 0:
			avance(numero)
		if con_catalogo and objeto.tipo != TIPO_CAJA and catalogo.objeto(objeto.tipo) is None:
			avisos.append(
				_aviso(
					"aviso",
					"tipo_no_instalado",
					_("«{nombre}» es de un tipo que no está instalado («{tipo}»); se trata como una caja con sus medidas.").format(
						nombre=objeto.nombre or objeto.id, tipo=objeto.tipo
					),
					objeto.id,
					planta.id,
					_("Instale el complemento que falta."),
				)
			)
		avisos.extend(comprobar(entorno, planta, objeto, catalogo, paso_minimo))
	for fuente in planta.fuentes:
		if not fuente.sonido.strip():
			avisos.append(
				_aviso(
					"error",
					"sonido_vacio",
					_("La fuente de sonido «{nombre}» no dice qué sonido emite.").format(nombre=fuente.nombre or fuente.id),
					fuente.id,
					planta.id,
					_("Elija un sonido en sus propiedades."),
				)
			)
		if fuente.radio <= 0:
			avisos.append(
				_aviso(
					"aviso",
					"radio_no_valido",
					_("La fuente de sonido «{nombre}» tiene radio cero: no se oirá.").format(nombre=fuente.nombre or fuente.id),
					fuente.id,
					planta.id,
					_("Póngale un radio en metros."),
				)
			)
		if planta.espacios and planta.espacio_en(fuente.x, fuente.y) is None:
			avisos.append(
				_aviso(
					"aviso",
					"fuente_fuera",
					_("La fuente de sonido «{nombre}» está fuera de todos los espacios.").format(nombre=fuente.nombre or fuente.id),
					fuente.id,
					planta.id,
					_("Compruebe su posición."),
				)
			)
	for zona in planta.zonas:
		motivo = _contorno_valido(zona.contorno)
		if motivo:
			avisos.append(
				_aviso(
					"error",
					"contorno_no_valido",
					_("El contorno de «{nombre}» {motivo}.").format(nombre=zona.nombre or zona.id, motivo=motivo),
					zona.id,
					planta.id,
					_("Vuelva a trazar la zona o bórrela."),
				)
			)
		elif zona.suelo not in SUELOS:
			avisos.append(
				_aviso(
					"aviso",
					"valor_desconocido",
					_("«{nombre}» tiene un valor desconocido en «{clave}»: «{valor}».").format(
						nombre=zona.nombre, clave="suelo", valor=zona.suelo
					),
					zona.id,
					planta.id,
					_("Elija uno de la lista en sus propiedades."),
				)
			)
	for via in planta.vias:
		if len(via.eje) < 2 or geo.longitud_linea(via.eje) < 0.5 or via.ancho <= 0:
			avisos.append(
				_aviso(
					"error",
					"via_no_valida",
					_("La vía «{nombre}» no tiene un eje con longitud o no tiene anchura.").format(nombre=via.nombre or via.id),
					via.id,
					planta.id,
					_("Vuelva a crear la calle."),
				)
			)


def _validar_extremo(entorno: Entorno, conector: Conector, posicion: Posicion, que: str, avisos: list[Aviso]) -> None:
	planta = entorno.planta(posicion.planta)
	if planta is None:
		avisos.append(
			_aviso(
				"error",
				"conector_planta_inexistente",
				_("{que} de «{nombre}» lleva a una planta que no existe («{planta}»).").format(
					que=que, nombre=conector.nombre, planta=posicion.planta
				),
				conector.id,
				"",
				_("Elija una planta que exista o borre el conector."),
			)
		)
		return
	espacio = planta.espacio_en(posicion.x, posicion.y, incluir_macizos=False)
	if espacio is None:
		avisos.append(
			_aviso(
				"error",
				"conector_fuera_de_espacio",
				_("{que} de «{nombre}» queda fuera de todo espacio en la planta «{planta}».").format(
					que=que, nombre=conector.nombre, planta=planta.nombre
				),
				conector.id,
				planta.id,
				_("Muévalo dentro de un pasillo o un vestíbulo, o cree allí un espacio."),
			)
		)


def _validar_conectores(entorno: Entorno, avisos: list[Aviso]) -> None:
	for conector in entorno.conectores:
		if conector.tipo not in TIPOS_CONECTOR:
			avisos.append(
				_aviso(
					"aviso",
					"valor_desconocido",
					_("«{nombre}» tiene un valor desconocido en «{clave}»: «{valor}».").format(
						nombre=conector.nombre, clave="tipo", valor=conector.tipo
					),
					conector.id,
					"",
					_("Elija uno de la lista en sus propiedades."),
				)
			)
		if conector.tipo == "ascensor":
			if len({parada.planta for parada in conector.paradas}) < 2:
				avisos.append(
					_aviso(
						"error",
						"conector_incompleto",
						_("El ascensor «{nombre}» para en menos de dos plantas.").format(nombre=conector.nombre),
						conector.id,
						"",
						_("Añada paradas o bórrelo."),
					)
				)
			for parada in conector.paradas:
				_validar_extremo(entorno, conector, parada.puerta, _("Una parada"), avisos)
			continue
		if not conector.tramos:
			avisos.append(
				_aviso(
					"error",
					"conector_incompleto",
					_("«{nombre}» no tiene ningún tramo: no une nada.").format(nombre=conector.nombre),
					conector.id,
					"",
					_("Bórrelo y vuelva a crearlo."),
				)
			)
		for tramo in conector.tramos:
			_validar_extremo(entorno, conector, tramo.desde, _("La boca de abajo"), avisos)
			_validar_extremo(entorno, conector, tramo.hasta, _("La boca de arriba"), avisos)
			if tramo.desde.planta == tramo.hasta.planta:
				avisos.append(
					_aviso(
						"aviso",
						"conector_misma_planta",
						_("Un tramo de «{nombre}» empieza y acaba en la misma planta.").format(nombre=conector.nombre),
						conector.id,
						tramo.desde.planta,
						_("Compruebe a qué planta sube."),
					)
				)
			if tramo.longitud_m <= 0:
				avisos.append(
					_aviso(
						"error",
						"conector_incompleto",
						_("Un tramo de «{nombre}» no tiene longitud.").format(nombre=conector.nombre),
						conector.id,
						tramo.desde.planta,
						_("Indique su longitud en metros."),
					)
				)
			if conector.tipo == "escalera" and tramo.peldanos < 1:
				avisos.append(
					_aviso(
						"aviso",
						"escalera_sin_peldanos",
						_("La escalera «{nombre}» no dice cuántos peldaños tiene.").format(nombre=conector.nombre),
						conector.id,
						tramo.desde.planta,
						_("Indique el número de peldaños: el alumno los cuenta al subir."),
					)
				)


def _validar_inicio(entorno: Entorno, catalogo: Catalogo, avisos: list[Aviso]) -> None:
	inicio = entorno.inicio
	planta = entorno.planta(inicio.planta)
	if planta is None:
		avisos.append(
			_aviso(
				"error",
				"inicio_no_valido",
				_("El punto de inicio no está en ninguna planta del entorno."),
				sugerencia=_("Fije el inicio en un punto de una habitación."),
			)
		)
		return
	punto = (inicio.x, inicio.y)
	espacios = planta.espacios_en(inicio.x, inicio.y)
	if any(espacio.macizo for espacio in espacios):
		avisos.append(
			_aviso(
				"error",
				"inicio_en_muro",
				_("El punto de inicio está dentro de «{nombre}», que es macizo.").format(
					nombre=next(e.nombre for e in espacios if e.macizo)
				),
				planta=planta.id,
				sugerencia=_("Lleve el inicio a una zona por la que se pueda andar."),
			)
		)
		return
	if not espacios:
		avisos.append(
			_aviso(
				"error",
				"inicio_fuera",
				_("El punto de inicio está fuera de todos los espacios de la planta «{planta}».").format(planta=planta.nombre),
				planta=planta.id,
				sugerencia=_("Lleve el inicio dentro de una habitación o de una zona."),
			)
		)
		return
	for segmento in segmentos_solidos(planta):
		if geo.distancia_punto_segmento(punto, segmento.a, segmento.b) < MARGEN_INICIO:
			avisos.append(
				_aviso(
					"error",
					"inicio_en_muro",
					_("El punto de inicio está dentro de un muro o pegado a él, en «{espacio}».").format(espacio=espacios[0].nombre),
					segmento.elemento_id,
					planta.id,
					_("Sepárelo al menos {metros} metros de la pared.").format(metros=str(MARGEN_INICIO).replace(".", separador_decimal())),
				)
			)
			break
	for objeto in planta.objetos:
		if catalogo.bloquea(objeto) and geo.punto_en_poligono(punto, catalogo.huella(objeto)):
			avisos.append(
				_aviso(
					"error",
					"inicio_en_objeto",
					_("El punto de inicio está dentro de «{nombre}».").format(nombre=objeto.nombre or objeto.id),
					objeto.id,
					planta.id,
					_("Mueva el inicio o el objeto."),
				)
			)
			break


def validar(
	entorno: Entorno,
	catalogo: Catalogo | None = None,
	paso_minimo: float = PASO_MINIMO,
	progreso: Callable[[str, int | None, int | None], None] | None = None,
) -> list[Aviso]:
	"""Revisa todo el entorno y devuelve los problemas, con los errores primero.

	Sin ``catalogo`` los objetos se tratan como cajas con sus medidas y no se
	avisa de complementos que falten. Una lista vacía significa que el
	entorno está listo para recorrerse.

	``progreso(fase, hecho, total)`` se llama al empezar cada fase y, en la de
	los objetos, cada pocos objetos: con un barrio importado comprobar tarda
	segundos y el diálogo de progreso dice qué se está mirando. Puede lanzar
	una excepción para cancelar (``TareaCancelada``): se deja salir.
	"""

	def avisar(fase: str, hecho: int | None = None, total: int | None = None) -> None:
		if progreso is not None:
			progreso(fase, hecho, total)

	con_catalogo = catalogo is not None
	catalogo = catalogo if catalogo is not None else Catalogo()
	avisos: list[Aviso] = []
	if not entorno.plantas:
		avisos.append(
			_aviso(
				"error",
				"entorno_vacio",
				_("El entorno no tiene ninguna planta."),
				sugerencia=_("Cree una planta y una habitación para empezar."),
			)
		)
		return avisos
	_validar_ids(entorno, avisos)
	niveles = Counter(planta.nivel for planta in entorno.plantas)
	for planta in entorno.plantas:
		if niveles[planta.nivel] > 1:
			avisos.append(
				_aviso(
					"aviso",
					"nivel_repetido",
					_("La planta «{nombre}» comparte el nivel {nivel} con otra.").format(nombre=planta.nombre, nivel=planta.nivel),
					planta.id,
					planta.id,
					_("Dé a cada planta un nivel distinto."),
				)
			)
		if not planta.espacios:
			avisos.append(
				_aviso(
					"aviso",
					"planta_sin_espacios",
					_("La planta «{nombre}» no tiene ningún espacio.").format(nombre=planta.nombre),
					planta.id,
					planta.id,
					_("Cree en ella una habitación o bórrela."),
				)
			)
		nombre_planta = planta.nombre or planta.id
		avisar(_("Comprobando los espacios de {planta}").format(planta=nombre_planta), 0, len(planta.espacios))
		_validar_espacios(entorno, planta, avisos)
		avisar(_("Comprobando las puertas y paredes de {planta}").format(planta=nombre_planta), 0, len(planta.aberturas))
		_validar_aberturas_y_paredes(planta, avisos)
		fase_objetos = _("Comprobando los objetos de {planta}").format(planta=nombre_planta)
		total_objetos = len(planta.objetos)
		avisar(fase_objetos, 0, total_objetos)
		# En lote: las paredes y puertas de la planta se calculan una vez para todos sus objetos.
		with lote_de_comprobaciones():
			_validar_objetos(
				entorno,
				planta,
				catalogo,
				con_catalogo,
				paso_minimo,
				avisos,
				lambda hecho, fase=fase_objetos, total=total_objetos: avisar(fase, hecho, total),
			)
	_validar_conectores(entorno, avisos)
	_validar_inicio(entorno, catalogo, avisos)
	avisos.sort(key=lambda aviso: 0 if aviso.es_error else 1)
	log.info(
		"Validación de «%s»: %s errores y %s avisos", entorno.nombre, sum(a.es_error for a in avisos), sum(not a.es_error for a in avisos)
	)
	return avisos


def resumen(avisos: list[Aviso]) -> str:
	"""Frase corta con el resultado: «Sin problemas», «2 errores y 1 aviso»."""
	errores = sum(aviso.es_error for aviso in avisos)
	leves = len(avisos) - errores
	if not avisos:
		return _("Sin problemas.")
	return _("{errores} y {avisos}.").format(
		errores=_n("{n} error", "{n} errores", errores).format(n=errores), avisos=_n("{n} aviso", "{n} avisos", leves).format(n=leves)
	)
