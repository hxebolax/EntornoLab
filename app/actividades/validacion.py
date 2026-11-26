"""Validación de una actividad contra su entorno, antes de dársela a un alumno.

Devuelve ``Aviso`` como la validación del entorno, con códigos estables. Lo
que impide jugar es un **error** (un premio dentro de un muro, un id que ya
no existe, un examen sin pruebas posibles); lo que conviene revisar es un
**aviso**.

Se distingue lo imposible de lo bloqueado a propósito: un premio al que no
se puede llegar de ninguna manera es un error, pero uno al que solo se llega
abriendo una puerta que está con llave puede ser justo lo que el profesional
quiere (una zona que hoy no se usa), y se deja como aviso.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Iterable
from typing import Any

from app.actividades.base import RADIO_RECOGER
from app.actividades.fabrica import CLASES, crear_actividad
from app.actividades.formato import normalizar
from app.actividades.lugares import Lugar, punto_de_acceso, resolver_lugar
from app.actividades.tipos import ESTILO_DEL_ALUMNO, ESTILOS, TIPOS
from app.core.i18n import _
from app.dominio.catalogo import Catalogo
from app.dominio.formato import CARPETA_IMAGENES, CARPETA_SONIDOS
from app.dominio.modelo import Abertura, Aviso, Conector, Entorno, Espacio, Objeto
from app.motor.mundo import Mundo
from app.motor.navegacion import Navegador
from app.motor.percepcion import AYUDAS

log = logging.getLogger(__name__)

TIPOS_CON_PREMIOS = ("busqueda", "pistas", "sacar_tesoros")
TIPOS_CON_SALIDAS = ("sacar_tesoros", "examen_salida")
TIPOS_CON_DESTINO = ("sigue_guia", "ruta", "ruta_inversa", "ruta_alternativa", "localizar")


class _Contexto:
	"""Lo que hace falta para comprobar lugares: el mundo, dos navegadores (sin y con llaves) y el punto de partida."""

	def __init__(self, datos: dict[str, Any], entorno: Entorno, catalogo: Catalogo | None) -> None:
		self.datos = datos
		self.entorno = entorno
		self.catalogo = catalogo
		self.mundo = Mundo(entorno, catalogo)
		self.nav = Navegador(self.mundo)
		self.nav_con_llave = Navegador(self.mundo, con_llave=True)
		self.avisos: list[Aviso] = []
		inicio = datos.get("inicio") or {}
		planta = str(inicio.get("planta") or entorno.inicio.planta)
		self.inicio: tuple[str, float, float] = (planta, float(inicio.get("x", entorno.inicio.x)), float(inicio.get("y", entorno.inicio.y)))

	def error(self, codigo: str, mensaje: str, elemento: str = "", planta: str = "", sugerencia: str = "") -> None:
		self.avisos.append(Aviso("error", codigo, mensaje, elemento, planta, sugerencia))

	def aviso(self, codigo: str, mensaje: str, elemento: str = "", planta: str = "", sugerencia: str = "") -> None:
		self.avisos.append(Aviso("aviso", codigo, mensaje, elemento, planta, sugerencia))

	def comprobar_punto(self, que: str, ident: str, planta_id: str, x: float, y: float, dentro_de_objeto: bool = False) -> bool:
		"""Comprueba que un punto está en un sitio donde se puede estar y al que se puede llegar. Devuelve si vale."""
		if self.mundo.planta(planta_id) is None:
			self.error(
				"planta_no_existe",
				_("{que} está en una planta que no existe.").format(que=que),
				ident,
				planta_id,
				_("Vuelve a colocarlo en el plano."),
			)
			return False
		if not dentro_de_objeto:
			espacio = self.mundo.espacio_en(planta_id, x, y, macizos=True)
			if espacio is None:
				self.error(
					"fuera_de_espacio",
					_("{que} está fuera de todos los espacios: dentro de un muro o fuera del entorno.").format(que=que),
					ident,
					planta_id,
					_("Muévelo dentro de una habitación."),
				)
				return False
			if espacio.macizo:
				self.error(
					"dentro_de_macizo",
					_("{que} está dentro de {espacio}, donde no se puede entrar.").format(que=que, espacio=espacio.nombre or espacio.id),
					ident,
					planta_id,
					_("Muévelo a un sitio transitable."),
				)
				return False
			tapado = self.mundo.dentro_de_objeto(planta_id, x, y)
			if tapado is not None:
				self.aviso(
					"dentro_de_mueble",
					_("{que} cae dentro de {objeto}.").format(que=que, objeto=tapado.objeto.nombre or tapado.objeto.id),
					ident,
					planta_id,
					_("Si quieres esconderlo dentro, indícalo en «dentro de»; si no, muévelo a un sitio libre."),
				)
		return self.comprobar_alcance(que, ident, planta_id, x, y)

	def comprobar_alcance(self, que: str, ident: str, planta_id: str, x: float, y: float) -> bool:
		"""Distingue lo inalcanzable (error) de lo que solo está tras una puerta con llave (aviso)."""
		destino = (planta_id, x, y)
		if self.nav.ruta(self.inicio, destino) is not None:
			return True
		if self.nav_con_llave.ruta(self.inicio, destino) is not None:
			self.aviso(
				"bloqueado",
				_("A {que} solo se llega pasando por una puerta que está cerrada con llave.").format(que=que),
				ident,
				planta_id,
				_("Si es a propósito, no hagas nada; si no, quita la llave de esa puerta."),
			)
			return True
		self.error(
			"inalcanzable",
			_("No se puede llegar andando a {que} desde el punto de inicio.").format(que=que),
			ident,
			planta_id,
			_("Muévelo o abre un paso hasta él."),
		)
		return False

	def comprobar_lugar(self, que: str, valor: Any, ident: str = "") -> Lugar | None:
		"""Resuelve y comprueba un lugar de los datos (un id o una posición)."""
		lugar = resolver_lugar(self.entorno, valor)
		if lugar is None:
			self.error(
				"no_existe",
				_("{que} apunta a algo que no existe en el entorno ({valor}).").format(que=que, valor=valor),
				ident,
				"",
				_("Elige otro elemento."),
			)
			return None
		if lugar.clase == "punto":
			self.comprobar_punto(que, ident, lugar.planta, lugar.x, lugar.y)
		elif lugar.clase == "objeto":
			acceso = punto_de_acceso(self.mundo, lugar.elemento_id)
			if acceso is None:
				self.error(
					"objeto_sin_acceso",
					_("{que} es un objeto junto al que no queda sitio libre.").format(que=que),
					ident or lugar.elemento_id,
					lugar.planta,
					_("Mueve el objeto o elige otro lugar."),
				)
				return lugar
			lugar.x, lugar.y = acceso
			self.comprobar_alcance(que, ident or lugar.elemento_id, lugar.planta, lugar.x, lugar.y)
		else:
			self.comprobar_alcance(que, ident or lugar.elemento_id, lugar.planta, lugar.x, lugar.y)
		return lugar


def _validar_premios(ctx: _Contexto) -> None:
	datos = ctx.datos
	for premio in datos["premios"]:
		que = _("El premio «{nombre}»").format(nombre=premio["nombre"])
		contenedor = premio.get("dentro_de")
		if contenedor:
			objeto = ctx.entorno.elemento(contenedor)
			if not isinstance(objeto, Objeto):
				ctx.error(
					"contenedor_no_existe",
					_("{que} está dentro de un objeto que ya no existe.").format(que=que),
					premio["id"],
					"",
					_("Elige otro objeto o déjalo suelto."),
				)
				continue
			definicion = ctx.catalogo.definicion_de(objeto) if ctx.catalogo is not None else None
			if definicion is not None and not definicion.contenedor:
				ctx.aviso(
					"no_es_contenedor",
					_("{que} está dentro de {objeto}, que no está pensado para guardar cosas.").format(
						que=que, objeto=objeto.nombre or objeto.id
					),
					premio["id"],
					"",
					_("Funciona igual (se encuentra al usar el objeto), pero puede extrañar al alumno."),
				)
			planta = ctx.entorno.planta_de(objeto)
			acceso = punto_de_acceso(ctx.mundo, objeto.id)
			if planta is None or acceso is None:
				ctx.error(
					"contenedor_sin_acceso",
					_("{que} está dentro de {objeto}, pero no queda sitio libre junto a él para usarlo.").format(
						que=que, objeto=objeto.nombre or objeto.id
					),
					premio["id"],
					planta.id if planta is not None else "",
					_("Mueve el objeto o elige otro."),
				)
				continue
			ctx.comprobar_punto(que, premio["id"], planta.id, acceso[0], acceso[1], dentro_de_objeto=True)
			continue
		if premio.get("x") is None or premio.get("y") is None or not premio.get("planta"):
			ctx.error(
				"premio_sin_lugar",
				_("{que} no tiene lugar.").format(que=que),
				premio["id"],
				"",
				_("Colócalo en el plano o dentro de un objeto."),
			)
			continue
		ctx.comprobar_punto(que, premio["id"], premio["planta"], float(premio["x"]), float(premio["y"]))
		if (
			premio["planta"] == ctx.inicio[0]
			and math.hypot(float(premio["x"]) - ctx.inicio[1], float(premio["y"]) - ctx.inicio[2]) <= RADIO_RECOGER
		):
			ctx.aviso(
				"premio_en_el_inicio",
				_("{que} está en el punto de inicio: se recogerá nada más empezar.").format(que=que),
				premio["id"],
				premio["planta"],
				_("Aléjalo un par de metros o mételo dentro de un objeto."),
			)
	if datos["tipo"] in TIPOS_CON_PREMIOS and not datos["premios"]:
		ctx.error(
			"sin_premios", _("Esta actividad necesita al menos un premio."), "", "", _("Añade premios a mano o con el reparto asistido.")
		)


def _validar_salidas(ctx: _Contexto) -> None:
	salidas = ctx.nav.salidas(ctx.inicio)
	if not salidas:
		ctx.error(
			"sin_salidas",
			_("El entorno no tiene ninguna salida a la que se pueda llegar."),
			"",
			"",
			_("Marca como salida al menos una puerta exterior."),
		)
	elif len(salidas) == 1:
		ctx.aviso(
			"una_sola_salida",
			_("Solo hay una salida: elegir la más cercana no mide nada, todas las pruebas valdrán 3 puntos."),
			salidas[0].abertura.id,
			salidas[0].planta_id,
			_("Marca más salidas o usa otro tipo de actividad."),
		)


def _validar_objetivos(ctx: _Contexto) -> None:
	datos = ctx.datos
	tipo = datos["tipo"]
	for numero, objetivo in enumerate(datos["objetivos"], start=1):
		que = _("El objetivo {n}").format(n=numero)
		claves = [c for c in ("recoger", "entregar") if objetivo.get(c) is not None] or ["destino"]
		for clave in claves:
			if objetivo.get(clave) is None:
				ctx.error(
					"objetivo_sin_destino", _("{que} no dice adónde hay que ir.").format(que=que), objetivo["id"], "", _("Elige un lugar.")
				)
				continue
			ctx.comprobar_lugar(que, objetivo.get(clave), objetivo["id"])
	if tipo in TIPOS_CON_DESTINO:
		if datos.get("destino") is None:
			ctx.error("sin_destino", _("La actividad no tiene destino."), "", "", _("Elige el lugar al que hay que llegar."))
		else:
			lugar = ctx.comprobar_lugar(_("El destino"), datos["destino"])
			if tipo == "localizar" and lugar is not None and lugar.clase != "espacio":
				ctx.aviso(
					"destino_no_es_espacio",
					_("En «localizar» el destino debería ser un espacio con nombre."),
					lugar.elemento_id,
					lugar.planta,
					_("Elige una habitación o un lugar."),
				)
	elif datos.get("destino") is not None and tipo == "cruce":
		ctx.comprobar_lugar(_("El lugar al que llegar"), datos["destino"])
	if tipo in ("recadero", "volver_origen") and not datos["objetivos"]:
		ctx.error("sin_objetivos", _("Esta actividad necesita al menos un objetivo."), "", "", _("Añade un lugar al que ir."))
	if tipo in ("perimetro", "linea_guia") and datos.get("espacio"):
		if not isinstance(ctx.entorno.elemento(str(datos["espacio"])), Espacio):
			ctx.error("espacio_no_existe", _("El espacio elegido ya no existe."), str(datos["espacio"]), "", _("Elige otro espacio."))


def _validar_cortes(ctx: _Contexto) -> None:
	datos = ctx.datos
	if datos["tipo"] != "ruta_alternativa":
		return
	cortes = datos["cortes"]
	if not cortes:
		ctx.aviso(
			"sin_corte",
			_("No hay ningún paso cortado: es una ruta normal."),
			"",
			"",
			_("Elige la puerta o la escalera que hoy no se puede usar."),
		)
		return
	validos: list[str] = []
	for ident in cortes:
		elemento = ctx.entorno.elemento(ident)
		if not isinstance(elemento, (Abertura, Conector)):
			ctx.error("corte_no_existe", _("El paso cortado ya no existe."), ident, "", _("Elige otro paso."))
		else:
			validos.append(ident)
	destino = resolver_lugar(ctx.entorno, datos.get("destino"))
	if destino is None or not validos:
		return
	if ctx.nav.ruta(ctx.inicio, destino.terna, evitar=validos) is None:
		ctx.error(
			"corte_sin_alternativa",
			_("Con ese paso cortado no queda ningún camino hasta el destino."),
			validos[0],
			"",
			_("Corta otro paso o cambia el destino."),
		)
	elif all(not _en_el_camino(ctx, destino, ident) for ident in validos):
		ctx.aviso(
			"corte_fuera_del_camino",
			_("El paso cortado no está en el camino más corto: cortarlo no cambia nada."),
			validos[0],
			"",
			_("Corta un paso por el que se pasaría."),
		)


def _en_el_camino(ctx: _Contexto, destino: Lugar, ident: str) -> bool:
	"""Si cortar ese paso alarga el camino al destino (o lo cambia de conector)."""
	directa = ctx.nav.ruta(ctx.inicio, destino.terna)
	cortada = ctx.nav.ruta(ctx.inicio, destino.terna, evitar=[ident])
	if directa is None or cortada is None:
		return True
	return cortada.longitud > directa.longitud + 0.3 or cortada.conectores != directa.conectores


def _validar_examen(ctx: _Contexto) -> None:
	"""Genera las pruebas como lo haría la partida y comprueba que hay suficientes."""
	from app.motor.sesion import Sesion

	datos = ctx.datos
	actividad = crear_actividad(datos, ctx.entorno, ctx.catalogo)
	generar = getattr(actividad, "_generar", None)
	if not callable(generar):
		return
	sesion = Sesion(ctx.entorno, ctx.catalogo, inicio=actividad.inicio(), semilla=int(datos.get("semilla") or 1))
	try:
		pruebas = generar(sesion)
	except Exception:  # noqa: BLE001 - un entorno raro no debe tumbar la validación: se informa y se sigue
		log.exception("No se han podido generar las pruebas del examen %s", datos.get("id"))
		ctx.error(
			"examen_no_generable",
			_("No se han podido generar las pruebas del examen en este entorno."),
			"",
			"",
			_("Define las pruebas a mano."),
		)
		return
	definidas = len(datos["pruebas"])
	pedidas = definidas or int(datos.get("numero_pruebas") or 0)
	if not pruebas:
		ctx.error(
			"examen_sin_pruebas",
			_("En este entorno no se puede generar ninguna prueba para este examen."),
			"",
			"",
			_("Hace falta un entorno con más espacios comunicados, o definir las pruebas a mano."),
		)
	elif len(pruebas) < pedidas:
		if definidas:
			ctx.error(
				"pruebas_no_validas",
				_("De las {pedidas} pruebas definidas solo valen {n}: las demás apuntan a lugares que no existen.").format(
					pedidas=pedidas, n=len(pruebas)
				),
				"",
				"",
				_("Revisa los lugares de cada prueba."),
			)
		else:
			ctx.aviso(
				"pruebas_insuficientes",
				_("Se pidieron {pedidas} pruebas pero el entorno solo da para {n}.").format(pedidas=pedidas, n=len(pruebas)),
				"",
				"",
				_("Reduce el número de pruebas o amplía el entorno."),
			)
	if datos["tipo"] == "examen_rutas" and len(pruebas) >= 2:
		largos = [float(p["longitud"]) for p in pruebas if isinstance(p.get("longitud"), (int, float))]
		if largos and max(largos) > 2.0 * max(1.0, min(largos)):
			ctx.aviso(
				"rutas_poco_comparables",
				_("Las rutas generadas no son de longitud parecida (de {a} a {b} metros).").format(
					a=round(min(largos)), b=round(max(largos))
				),
				"",
				"",
				_("Con menos rutas, o definiéndolas a mano, se pueden igualar."),
			)
	regla = datos.get("regla_parada")
	if regla and regla.get("activa", True) and pruebas and int(regla["de"]) > len(pruebas):
		ctx.aviso(
			"regla_parada_larga",
			_("La regla de parada mira {de} pruebas y el examen solo tiene {n}.").format(de=regla["de"], n=len(pruebas)),
			"",
			"",
			_("Ajusta la regla al número de pruebas."),
		)


def _tiene_recurso(nombre: str, recursos: set[str]) -> bool:
	"""True si el paquete trae ese recurso, escrito con su carpeta («sonidos/x.wav») o sin ella, como lo busca ``Paquete.recurso``."""
	if nombre in recursos:
		return True
	return any(f"{carpeta}/{nombre}" in recursos for carpeta in (CARPETA_SONIDOS, CARPETA_IMAGENES))


def _validar_audios(datos: dict[str, Any], recursos: set[str]) -> list[Aviso]:
	"""Avisa de cada premio cuyo audio grabado no viaja en el paquete: al recogerlo no sonaría nada.

	Es un aviso y no un error: la actividad se puede jugar igual, solo se
	pierde el mensaje grabado (el profesional o la familia lo volverán a añadir).
	"""
	avisos: list[Aviso] = []
	for premio in datos.get("premios") or []:
		audio = premio.get("audio") if isinstance(premio, dict) else None
		if not audio or _tiene_recurso(str(audio), recursos):
			continue
		avisos.append(
			Aviso(
				"aviso",
				"audio_no_existe",
				_("El audio «{audio}» del premio «{nombre}» no está en el paquete: al recogerlo no sonará.").format(
					audio=audio, nombre=premio.get("nombre") or premio.get("id") or ""
				),
				str(premio.get("id") or ""),
				"",
				_("Vuelve a añadir el audio al premio o quítaselo."),
			)
		)
	return avisos


def validar_actividad(
	datos: dict,
	entorno: Entorno,
	catalogo: Catalogo | None = None,
	recursos: Iterable[str] | None = None,
) -> list[Aviso]:
	"""Problemas de una actividad en su entorno: lista vacía si está lista para jugar.

	Los errores van primero. No modifica ni los datos ni el entorno.

	:param recursos: nombres de los recursos del paquete (``sonidos/x.wav``;
		vale el diccionario ``contexto.recursos`` o ``Paquete.recursos``). Si se
		dan, se comprueba que el audio de cada premio está entre ellos
		(``audio_no_existe``). Sin ellos no se comprueba: quien valida sin el
		paquete delante no puede saberlo.
	"""
	if not isinstance(datos, dict):
		return [Aviso("error", "formato", _("La actividad no es un diccionario de datos."), "", "", _("Vuelve a crearla."))]
	avisos = _validar_sin_recursos(datos, entorno, catalogo)
	if recursos is not None:
		avisos.extend(_validar_audios(normalizar(datos), {str(nombre) for nombre in recursos}))
	avisos.sort(key=lambda aviso: 0 if aviso.es_error else 1)
	return avisos


def _validar_sin_recursos(datos: dict, entorno: Entorno, catalogo: Catalogo | None) -> list[Aviso]:
	"""Todo lo que se comprueba con el entorno y el catálogo; los recursos del paquete los mira ``validar_actividad``."""
	limpio = normalizar(datos)
	ctx = _Contexto(limpio, entorno, catalogo)
	tipo = limpio["tipo"]
	if tipo not in TIPOS or tipo not in CLASES:
		ctx.error(
			"tipo_desconocido",
			_("Tipo de actividad desconocido: {tipo}.").format(tipo=tipo),
			"",
			"",
			_("Puede venir de una versión más nueva del programa."),
		)
		return ctx.avisos
	if not entorno.plantas or all(not planta.espacios for planta in entorno.plantas):
		ctx.error(
			"entorno_vacio", _("El entorno no tiene espacios: no se puede jugar en él."), "", "", _("Dibuja al menos una habitación.")
		)
		return ctx.avisos
	if datos.get("estilo") not in (None, "", ESTILO_DEL_ALUMNO, *ESTILOS):
		ctx.aviso("estilo_desconocido", _("Estilo de presentación desconocido: se usará el de la ficha del alumno."), "", "", "")
	if datos.get("inicio") is not None and limpio["inicio"] is None:
		ctx.error("inicio_no_valido", _("El punto de inicio no está bien definido."), "", "", _("Vuelve a marcarlo en el plano."))
	planta, x, y = ctx.inicio
	if ctx.mundo.planta(planta) is None:
		ctx.error(
			"inicio_sin_planta", _("El punto de inicio está en una planta que no existe."), "", planta, _("Vuelve a marcarlo en el plano.")
		)
		return ctx.avisos
	donde = ctx.mundo.espacio_en(planta, x, y, macizos=True)
	if donde is None or donde.macizo or not (math.isfinite(x) and math.isfinite(y)):
		ctx.error(
			"inicio_fuera",
			_("El punto de inicio no está dentro de un espacio transitable."),
			"",
			planta,
			_("Vuelve a marcarlo dentro de una habitación."),
		)
		return ctx.avisos
	for ayuda in limpio["ayudas"]:
		if ayuda not in AYUDAS:
			ctx.aviso("ayuda_desconocida", _("Ayuda desconocida: {ayuda}. Se ignora.").format(ayuda=ayuda), "", "", "")
	if isinstance(datos.get("nivel"), int) and limpio["niveles"] and not 0 <= datos["nivel"] < len(limpio["niveles"]):
		ctx.aviso("nivel_fuera_de_rango", _("El nivel de partida no existe: se usará el más cercano."), "", "", "")
	_validar_premios(ctx)
	_validar_objetivos(ctx)
	_validar_cortes(ctx)
	if tipo in TIPOS_CON_SALIDAS:
		_validar_salidas(ctx)
	if tipo == "cruce" and not any(e.tipo in ("calzada", "paso_peatones") for p in entorno.plantas for e in p.espacios):
		ctx.error(
			"sin_calzada", _("En este entorno no hay ninguna calzada que cruzar."), "", "", _("Esta actividad es para entornos de calle.")
		)
	if tipo == "sigue_guia" and limpio.get("destino") is not None:
		destino = resolver_lugar(entorno, limpio["destino"])
		if (
			destino is not None
			and ctx.nav.ruta(ctx.inicio, destino.terna) is None
			and ctx.nav_con_llave.ruta(ctx.inicio, destino.terna) is not None
		):
			ctx.error(
				"guia_sin_camino",
				_("El guía no puede llegar al destino: hay una puerta con llave en el camino."),
				destino.elemento_id,
				destino.planta,
				_("Quita la llave o cambia el destino."),
			)
	if limpio["modo"] == "examen":
		_validar_examen(ctx)
	ctx.avisos.sort(key=lambda aviso: 0 if aviso.es_error else 1)
	return ctx.avisos
