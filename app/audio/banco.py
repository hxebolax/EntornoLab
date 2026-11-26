"""Banco de sonidos: dado un nombre, encuentra el sonido que toca.

Orden de búsqueda de un nombre como ``puerta/abrir`` o ``sonidos/timbre.ogg``:

1. **El paquete del entorno** (``sonidos/<nombre>`` dentro del ``.elab``): el profesional puede
   grabar el timbre de verdad de esa casa, o sustituir cualquier sonido de serie para ese entorno.
2. **Un complemento**: ``<complemento>/<sonido>`` se busca en ``data/plugins/<complemento>/sonidos``.
3. **El paquete de sonidos elegido** (``data/sounds/<paquete>``), si no es el de por defecto.
4. **El paquete por defecto** (``data/sounds/por_defecto``): un paquete puede ser parcial, y lo que
   no trae suena con el sonido de serie.
5. **Reserva sintetizada**: si no está en ningún sitio, se sintetiza en el momento (el propio sonido
   si es de serie y falta su fichero; si no, uno neutro de su familia). El programa nunca se queda
   mudo ni se cae porque falte un fichero; queda apuntado en el registro una vez.

Un **paquete de sonidos** es una carpeta de ``data/sounds`` con ficheros que se llaman igual que los
sonidos del catálogo (``puerta/abrir.flac``) y, si quiere, un ``pack.json`` con su nombre visible,
descripción, autor y licencia. Los paquetes se buscan en la carpeta de datos del usuario y en la del
programa: para añadir uno basta con copiar su carpeta. Se cambia de paquete **en caliente** con
:meth:`Banco.poner_paquete`; quien tenga un motor de sonido en marcha vuelve a cargar lo que cambie
con :meth:`Banco.recargar_en` (el :class:`~app.audio.presentador.Presentador` lo hace solo).

**Igualado.** Cada sonido de un paquete que no es el de por defecto se lleva al nivel del sonido de
serie del mismo nombre (:mod:`app.audio.niveles`), para que al cambiar de paquete no suba ni baje
el volumen general. Encima, el usuario puede subir o bajar cada sonido (``volumenes``).

Un nombre sin variante (``pasos/baldosa`` o ``pasos/baldosa_izq``) se resuelve a una de sus variantes
de serie al azar, para que el motor del juego no tenga que saber cuántas hay.

Los nombres vienen de entornos y complementos, que son datos de terceros: nunca se aceptan rutas
absolutas ni ``..``. Lo leído se guarda en una caché en memoria.
"""

from __future__ import annotations

import io
import json
import logging
import random
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import numpy as np

from app.audio import niveles, sintesis
from app.audio.base import FRECUENCIA, carpetas_de_serie
from app.core.i18n import N_, _

log = logging.getLogger(__name__)

EXTENSIONES = (".ogg", ".flac", ".wav")
# «paquete» es el paquete de sonidos elegido; «serie», el paquete por defecto.
ORIGENES = ("entorno", "complemento", "paquete", "serie", "sintetizado", "reserva")
PAQUETE_POR_DEFECTO = "por_defecto"
NOMBRE_FICHA = "pack.json"
# Una carpeta es un paquete si su nombre es así de sencillo: sirve de identificador en la configuración.
_ID_PAQUETE = re.compile(r"[a-z0-9][a-z0-9_\-]{0,63}")
# Segundos del fundido con el que un bucle que está sonando pasa al sonido del paquete nuevo.
FUNDIDO_PAQUETE = 0.25
# Los sonidos que ``app.audio.paquetes.escuchar`` carga en el motor como muestra: no son del juego.
PREFIJO_MUESTRA = "_muestra/"
# Nombres y descripciones de los paquetes que viajan con el programa, marcados para traducir
# (el texto sale de su ``pack.json``; aquí solo se anuncia a la herramienta de idiomas).
_TEXTOS_DE_SERIE = (
	N_("Sintético (por defecto)"),
	N_("Los sonidos de serie de EntornoLab: limpios, cortos y muy distintos entre sí, sintetizados uno a uno."),
	N_("Natural"),
	N_(
		"Instrumentos acústicos y objetos con cuerpo: marimba, xilófono y campanas en lugar de tonos electrónicos, y pasos, golpes, puertas y agua "
		"hechos con modelos físicos."
	),
)
# Tope de lo que se lee de un sonido propio (unos 3 minutos en estéreo): un fichero enorme no debe agotar la memoria.
MUESTRAS_MAXIMAS = FRECUENCIA * 180

RecursoEntorno = Callable[[str], bytes | None]


@dataclass(frozen=True)
class Sonido:
	"""Un sonido resuelto: de dónde ha salido y sus muestras."""

	nombre: str
	origen: str
	datos: np.ndarray
	frecuencia: int = FRECUENCIA
	ruta: Path | None = None
	# Paquete de sonidos del que ha salido («» si no viene de ninguno) y ganancia que se le ha aplicado.
	paquete: str = ""
	ganancia: float = 1.0

	def firma(self) -> tuple[str, str, str, float]:
		"""Lo que distingue a este sonido de otro con el mismo nombre: sirve para saber si hay que recargarlo."""
		return (self.origen, self.paquete, "" if self.ruta is None else str(self.ruta), round(self.ganancia, 4))


def nombre_seguro(nombre: str) -> str | None:
	"""El nombre normalizado (con «/»), o None si intenta salirse de su carpeta."""
	texto = str(nombre or "").replace("\\", "/").strip()
	if not texto or texto.startswith("/") or ":" in texto:
		return None
	partes = PurePosixPath(texto).parts
	if any(parte in ("..", ".") for parte in partes):
		return None
	return "/".join(partes)


class Banco:
	"""Resuelve nombres de sonido y guarda en memoria lo ya leído."""

	def __init__(
		self,
		recurso_entorno: RecursoEntorno | None = None,
		carpetas_sonidos: list[Path] | None = None,
		carpetas_complementos: list[Path] | None = None,
		azar: random.Random | None = None,
		paquete: str = PAQUETE_POR_DEFECTO,
		igualar: bool = True,
		volumenes: dict[str, float] | None = None,
	) -> None:
		"""``recurso_entorno(nombre) -> bytes`` suele ser ``Paquete.recurso``; las carpetas, las de serie si no se dan.

		``carpetas_sonidos`` son las carpetas que contienen los paquetes (``data/sounds``), no un
		paquete concreto. ``paquete`` es el identificador del paquete elegido; ``volumenes``, el ajuste
		del usuario para sonidos concretos (``{nombre: factor}``, de 0,3 a 2).
		"""
		self.recurso_entorno = recurso_entorno
		self.carpetas_sonidos = list(carpetas_sonidos) if carpetas_sonidos is not None else carpetas_de_serie("sounds")
		self.carpetas_complementos = list(carpetas_complementos) if carpetas_complementos is not None else carpetas_de_serie("plugins")
		self.igualar = bool(igualar)
		self.volumenes: dict[str, float] = dict(volumenes or {})
		self._azar = azar or random.Random()
		self._cache: dict[str, Sonido] = {}
		self._avisados: set[str] = set()
		self._variantes: dict[str, list[str]] | None = None
		self._paquete = PAQUETE_POR_DEFECTO
		self._fichas: dict[str, dict] = {}
		self._niveles: dict[str, tuple[float, float]] | None = None
		self._referencias: dict[str, float | None] = {}
		self._entregado: dict[str, tuple[str, str, str, float]] = {}
		self._oyentes: list[Callable[[str], None]] = []
		if paquete and paquete != PAQUETE_POR_DEFECTO:
			self.poner_paquete(paquete)

	# ── Configuración ──

	def poner_entorno(self, recurso: RecursoEntorno | None) -> None:
		"""Cambia de entorno: sus sonidos propios dejan de valer, así que se vacía la caché."""
		self.recurso_entorno = recurso
		self.vaciar()

	def vaciar(self) -> None:
		"""Olvida lo leído (tras cambiar de entorno o de paquete, o instalar un complemento)."""
		self._cache.clear()
		self._avisados.clear()
		self._fichas.clear()
		self._niveles = None
		self._referencias.clear()

	# ── Paquetes de sonidos ──

	def paquete_actual(self) -> str:
		"""Identificador del paquete de sonidos elegido (``por_defecto`` si no se ha elegido otro)."""
		return self._paquete

	def paquetes_disponibles(self) -> list[dict]:
		"""Los paquetes instalados, el de por defecto primero.

		Cada elemento: ``{"id", "nombre", "descripcion", "autor", "licencia", "version", "generado",
		"sonidos", "total", "completo", "parcial", "defecto", "actual", "carpeta"}``. ``sonidos`` es
		cuántos sonidos del catálogo trae (``total`` son todos los del catálogo); un paquete ``parcial``
		toma los demás del de por defecto. Una carpeta sin ningún sonido del catálogo y sin ``pack.json``
		no es un paquete; un ``pack.json`` dañado no impide usar el paquete (se llama como su carpeta).
		"""
		catalogo = set(sintesis.nombres())
		encontrados: dict[str, dict] = {}
		for raiz in self.carpetas_sonidos:
			if not raiz.is_dir():
				continue
			try:
				carpetas = sorted(carpeta for carpeta in raiz.iterdir() if carpeta.is_dir())
			except OSError:
				log.warning("No se pudo mirar qué paquetes de sonidos hay en %s.", raiz, exc_info=True)
				continue
			for carpeta in carpetas:
				identificador = carpeta.name
				if not _ID_PAQUETE.fullmatch(identificador):
					continue
				presentes = _sonidos_en(carpeta) & catalogo
				tiene_ficha = (carpeta / NOMBRE_FICHA).is_file()
				if not presentes and not tiene_ficha:
					continue
				ya = encontrados.get(identificador)
				if ya is not None:
					# El mismo paquete en la carpeta del usuario y en la del programa: se suman sus sonidos.
					ya["_presentes"] |= presentes
					continue
				ficha = leer_ficha(carpeta)
				encontrados[identificador] = {
					"id": identificador,
					"nombre": _(str(ficha.get("nombre") or identificador.replace("_", " "))),
					"descripcion": _(str(ficha.get("descripcion"))) if ficha.get("descripcion") else "",
					"autor": str(ficha.get("autor") or ""),
					"licencia": str(ficha.get("licencia") or ""),
					"version": str(ficha.get("version") or ""),
					"generado": str(ficha.get("generado") or ""),
					"carpeta": str(carpeta),
					"_presentes": set(presentes),
				}
		if PAQUETE_POR_DEFECTO not in encontrados:
			# El de por defecto existe siempre, aunque falte su carpeta: sus sonidos se sintetizan al pedirlos.
			encontrados[PAQUETE_POR_DEFECTO] = {
				"id": PAQUETE_POR_DEFECTO,
				"nombre": _(_TEXTOS_DE_SERIE[0]),
				"descripcion": _(_TEXTOS_DE_SERIE[1]),
				"autor": "",
				"licencia": "",
				"version": "",
				"generado": "",
				"carpeta": "",
				"_presentes": set(),
			}
		total = len(catalogo)
		lista: list[dict] = []
		for identificador, datos in encontrados.items():
			presentes = datos.pop("_presentes")
			datos["sonidos"] = len(presentes)
			datos["total"] = total
			datos["completo"] = len(presentes) >= total
			datos["parcial"] = not datos["completo"]
			datos["defecto"] = identificador == PAQUETE_POR_DEFECTO
			datos["actual"] = identificador == self._paquete
			lista.append(datos)
		lista.sort(key=lambda datos: (not datos["defecto"], datos["nombre"].lower()))
		return lista

	def poner_paquete(self, identificador: str | None) -> bool:
		"""Elige el paquete de sonidos, en caliente. Devuelve si quedó puesto el que se pidió.

		Un identificador vacío es el paquete por defecto. Si el paquete pedido no existe (lo han
		borrado, o la configuración viene de otro equipo) se avisa en el registro y queda el de por
		defecto: el programa nunca se queda sin sonidos. Se vacía la caché y se avisa a los suscritos
		(:meth:`suscribir`); quien tenga un motor de sonido llama entonces a :meth:`recargar_en`.
		"""
		pedido = str(identificador or PAQUETE_POR_DEFECTO)
		valido = pedido == PAQUETE_POR_DEFECTO or (bool(_ID_PAQUETE.fullmatch(pedido)) and bool(self._carpetas_de(pedido)))
		nuevo = pedido if valido else PAQUETE_POR_DEFECTO
		if not valido:
			log.warning("El paquete de sonidos «%s» no está instalado; se usa el de por defecto.", pedido)
		cambia = nuevo != self._paquete
		self._paquete = nuevo
		if cambia:
			self.vaciar()
			log.info("Paquete de sonidos en uso: %s.", nuevo)
			self._avisar("paquete")
		return valido

	def poner_igualado(self, si: bool) -> None:
		"""Activa o quita el igualado de sonoridad de los paquetes (en caliente)."""
		if bool(si) != self.igualar:
			self.igualar = bool(si)
			self.vaciar()
			self._avisar("igualado")

	def poner_volumenes(self, volumenes: dict[str, float] | None) -> None:
		"""Sustituye el ajuste de volumen por sonido del usuario (``{nombre: factor}``), en caliente."""
		nuevos = dict(volumenes or {})
		if nuevos != self.volumenes:
			self.volumenes = nuevos
			self._cache.clear()
			self._avisar("volumenes")

	def volumen_sonido(self, nombre: str) -> float:
		"""El ajuste del usuario que de verdad se aplica a ese sonido (1 si no lo ha tocado)."""
		return niveles.ajuste_valido(self.volumenes.get(nombre, 1.0))

	def poner_volumen_sonido(self, nombre: str, factor: float) -> float:
		"""Sube o baja un sonido concreto (de 0,3 a 2; 1 lo deja como viene). Devuelve el ajuste que queda."""
		ajuste = round(niveles.ajuste_valido(factor), 2)
		nuevos = dict(self.volumenes)
		if abs(ajuste - 1.0) < 0.005:
			nuevos.pop(nombre, None)
		else:
			nuevos[nombre] = ajuste
		self.poner_volumenes(nuevos)
		return ajuste

	def suscribir(self, funcion: Callable[[str], None]) -> Callable[[], None]:
		"""Avisa a ``funcion(motivo)`` cuando cambian los sonidos («paquete», «igualado» o «volumenes»).

		El aviso llega en el hilo que hizo el cambio, que puede no ser el del juego: quien toque un
		motor de sonido debe apuntarlo y hacerlo en su propio hilo. Devuelve la función que cancela.
		"""
		self._oyentes.append(funcion)

		def cancelar() -> None:
			if funcion in self._oyentes:
				self._oyentes.remove(funcion)

		return cancelar

	def _avisar(self, motivo: str) -> None:
		for funcion in list(self._oyentes):
			try:
				funcion(motivo)
			except Exception:  # noqa: BLE001 - un suscriptor roto no debe impedir cambiar de paquete ni avisar a los demás
				log.exception("Falló un suscriptor del banco de sonidos al avisar de «%s».", motivo)

	def _carpetas_de(self, identificador: str) -> list[Path]:
		"""Las carpetas de ese paquete, la del usuario antes que la del programa."""
		return [raiz / identificador for raiz in self.carpetas_sonidos if (raiz / identificador).is_dir()]

	def _ficha(self, identificador: str) -> dict:
		"""El ``pack.json`` de un paquete (vacío si no tiene o está dañado), leído una vez."""
		ficha = self._fichas.get(identificador)
		if ficha is None:
			ficha = {}
			for carpeta in self._carpetas_de(identificador):
				if (carpeta / NOMBRE_FICHA).is_file():
					ficha = leer_ficha(carpeta)
					break
			self._fichas[identificador] = ficha
		return ficha

	def referencia(self, nombre: str) -> float | None:
		"""El nivel al que suena ese sonido en el paquete por defecto, o None si allí no existe.

		Sale de ``por_defecto/niveles.json``; si el fichero no está o no trae ese sonido, se mide el
		sonido de serie (o se sintetiza para medirlo) y se recuerda.
		"""
		if nombre in self._referencias:
			return self._referencias[nombre]
		if self._niveles is None:
			self._niveles = {}
			for carpeta in reversed(self._carpetas_de(PAQUETE_POR_DEFECTO)):
				self._niveles.update(niveles.leer_niveles(carpeta))
		par = self._niveles.get(nombre)
		valor: float | None = par[0] if par is not None else None
		if valor is None:
			for carpeta in self._carpetas_de(PAQUETE_POR_DEFECTO):
				ruta = _fichero(carpeta, nombre)
				leido = _leer_ruta(ruta) if ruta is not None else None
				if leido is not None:
					valor = niveles.nivel(leido[0], leido[1])
					break
		if valor is None and nombre in sintesis.CATALOGO:
			valor = niveles.nivel(sintesis.generar(nombre))
		self._referencias[nombre] = valor
		return valor

	# ── Búsqueda ──

	def _del_entorno(self, nombre: str) -> Sonido | None:
		if self.recurso_entorno is None:
			return None
		base = nombre if nombre.startswith("sonidos/") else f"sonidos/{nombre}"
		candidatos = [base] if Path(base).suffix.lower() in EXTENSIONES else [base + extension for extension in EXTENSIONES]
		for candidato in candidatos:
			try:
				contenido = self.recurso_entorno(candidato)
			except KeyError, LookupError, OSError, ValueError:
				continue  # ese nombre no está en el paquete: es lo normal, se prueba el siguiente
			except Exception:  # noqa: BLE001 - el paquete puede lanzar su propio error de formato; no debe tumbar el sonido
				log.debug("El paquete del entorno no pudo dar %s.", candidato, exc_info=True)
				continue
			if not contenido:
				continue
			try:
				datos, frecuencia = _leer_bytes(contenido)
			except OSError, ValueError, RuntimeError:
				log.warning("El sonido %s del entorno no se pudo leer.", candidato, exc_info=True)
				continue
			return Sonido(nombre, "entorno", datos, frecuencia)
		return None

	def _de_complemento(self, nombre: str) -> Sonido | None:
		if "/" not in nombre:
			return None
		complemento, resto = nombre.split("/", 1)
		if resto.startswith("sonidos/"):
			resto = resto[len("sonidos/") :]
		for carpeta in self.carpetas_complementos:
			sonidos = carpeta / complemento / "sonidos"
			if not sonidos.is_dir():
				continue
			ruta = _fichero(sonidos, resto)
			if ruta is not None:
				leido = _leer_ruta(ruta)
				if leido is not None:
					return Sonido(nombre, "complemento", leido[0], leido[1], ruta)
		return None

	def _de_paquete(self, nombre: str, paquete: str) -> Sonido | None:
		"""El sonido tal como lo trae ese paquete (igualado al de serie si no es el de por defecto), o None."""
		for carpeta in self._carpetas_de(paquete):
			ruta = _fichero(carpeta, nombre)
			if ruta is None:
				continue
			leido = _leer_ruta(ruta)
			if leido is None:
				continue
			datos, frecuencia = leido
			if paquete == PAQUETE_POR_DEFECTO:
				return Sonido(nombre, "serie", datos, frecuencia, ruta, paquete)
			ficha = self._ficha(paquete)
			clave = _sin_extension(nombre)
			ganancia = 1.0
			if self.igualar and ficha.get("igualar", True) is not False:
				referencia = self.referencia(clave)
				if referencia is not None:
					ganancia = niveles.ganancia_para_igualar(datos, referencia, frecuencia)
			propios = ficha.get("volumenes")
			if isinstance(propios, dict) and clave in propios:
				# El autor del paquete puede retocar un sonido suyo; se acota igual que el ajuste del usuario.
				ganancia *= niveles.ajuste_valido(propios[clave])
			if abs(ganancia - 1.0) > 1e-4:
				datos = np.ascontiguousarray(datos * np.float32(ganancia))
			return Sonido(nombre, "paquete", datos, frecuencia, ruta, paquete, ganancia)
		return None

	def _de_serie(self, nombre: str, paquete: str | None = None) -> Sonido | None:
		"""En el paquete elegido; si no lo trae, en el de por defecto; y si no, suelto en ``data/sounds``."""
		elegido = self._paquete if paquete is None else paquete
		if elegido != PAQUETE_POR_DEFECTO:
			encontrado = self._de_paquete(nombre, elegido)
			if encontrado is not None:
				return encontrado
		encontrado = self._de_paquete(nombre, PAQUETE_POR_DEFECTO)
		if encontrado is not None:
			return encontrado
		# Compatibilidad: una instalación anterior a los paquetes tenía los sonidos sueltos en data/sounds.
		for carpeta in self.carpetas_sonidos:
			if not carpeta.is_dir():
				continue
			ruta = _fichero(carpeta, nombre)
			if ruta is not None:
				leido = _leer_ruta(ruta)
				if leido is not None:
					return Sonido(nombre, "serie", leido[0], leido[1], ruta)
		return None

	def sonido_de_paquete(self, paquete: str, nombre: str) -> Sonido:
		"""El sonido ``nombre`` tal como sonaría con ese paquete puesto, sin cambiar el paquete en uso.

		Es para escuchar una muestra de un paquete antes de elegirlo. No mira el entorno ni los
		complementos, y no usa la caché. Nunca falla: lo que el paquete no trae sale del de por defecto
		y, si tampoco, de la reserva.
		"""
		seguro = nombre_seguro(nombre)
		if seguro is None:
			return Sonido(str(nombre), "reserva", sintesis.sonido_reserva(""))
		clave = _sin_extension(seguro)
		elegido = paquete if _ID_PAQUETE.fullmatch(str(paquete or "")) else PAQUETE_POR_DEFECTO
		encontrado = self._de_serie(clave, elegido)
		if encontrado is None:
			if clave in sintesis.CATALOGO:
				encontrado = Sonido(seguro, "sintetizado", sintesis.generar(clave))
			else:
				variante = self._variante(clave)
				if variante is not None:
					return self.sonido_de_paquete(elegido, variante)
				encontrado = Sonido(seguro, "reserva", sintesis.sonido_reserva(clave))
		return self._con_ajuste(encontrado, clave)

	def _con_ajuste(self, encontrado: Sonido, clave: str) -> Sonido:
		"""Aplica el ajuste de volumen del usuario para ese sonido, sin dejar que recorte."""
		ajuste = self.volumen_sonido(clave)
		if abs(ajuste - 1.0) < 0.005 or encontrado.origen == "reserva":
			return encontrado
		maximo = niveles.pico(encontrado.datos) * ajuste
		if maximo > 0.98:
			ajuste *= 0.98 / maximo
		datos = np.ascontiguousarray(encontrado.datos * np.float32(ajuste))
		return Sonido(
			encontrado.nombre,
			encontrado.origen,
			datos,
			encontrado.frecuencia,
			encontrado.ruta,
			encontrado.paquete,
			encontrado.ganancia * ajuste,
		)

	def _variante(self, nombre: str) -> str | None:
		"""Una variante de serie al azar de un nombre genérico (``pasos/baldosa`` → ``pasos/baldosa_der_2``)."""
		if self._variantes is None:
			self._variantes = {}
			for clave in sintesis.nombres():
				trozos = clave.split("_")
				for corte in range(1, len(trozos)):
					self._variantes.setdefault("_".join(trozos[:corte]), []).append(clave)
		candidatas = self._variantes.get(nombre)
		return self._azar.choice(candidatas) if candidatas else None

	def _buscar(self, nombre: str) -> Sonido | None:
		"""En un sitio de verdad (entorno, complemento o serie); None si no está en ninguno."""
		return self._del_entorno(nombre) or self._de_complemento(nombre) or self._de_serie(nombre)

	def sonido(self, nombre: str) -> Sonido:
		"""El sonido que corresponde a ``nombre``. Nunca falla: en el peor caso devuelve uno de reserva."""
		seguro = nombre_seguro(nombre)
		if seguro is None:
			if nombre not in self._avisados:
				self._avisados.add(nombre)
				log.warning("Nombre de sonido no admitido: %r; suena el de reserva.", nombre)
			return Sonido(str(nombre), "reserva", sintesis.sonido_reserva(""))
		# El nombre puede traer extensión (un sonido propio): se guarda en caché tal cual se pidió.
		hecho = self._cache.get(seguro)
		if hecho is not None:
			return hecho
		clave = _sin_extension(seguro)
		encontrado = self._buscar(seguro) or (self._buscar(clave) if clave != seguro else None)
		if encontrado is None and clave not in sintesis.CATALOGO:
			variante = self._variante(clave)
			if variante is not None:
				# No se guarda en caché: cada vez toca otra variante.
				elegido = self.sonido(variante)
				return Sonido(seguro, elegido.origen, elegido.datos, elegido.frecuencia, elegido.ruta, elegido.paquete, elegido.ganancia)
		if encontrado is None:
			if clave in sintesis.CATALOGO:
				if seguro not in self._avisados:
					self._avisados.add(seguro)
					log.warning("Falta el fichero del sonido de serie %s: se sintetiza. Ejecute tools/sintetizar_sonidos.py.", clave)
				encontrado = Sonido(seguro, "sintetizado", sintesis.generar(clave))
			else:
				if seguro not in self._avisados:
					self._avisados.add(seguro)
					log.warning("No existe el sonido %s: suena uno de reserva.", seguro)
				encontrado = Sonido(seguro, "reserva", sintesis.sonido_reserva(clave))
		if len(encontrado.datos) > MUESTRAS_MAXIMAS:
			log.warning("El sonido %s es demasiado largo: se recorta a %s segundos.", seguro, MUESTRAS_MAXIMAS // FRECUENCIA)
			encontrado = Sonido(
				seguro,
				encontrado.origen,
				encontrado.datos[:MUESTRAS_MAXIMAS],
				encontrado.frecuencia,
				encontrado.ruta,
				encontrado.paquete,
				encontrado.ganancia,
			)
		encontrado = self._con_ajuste(encontrado, clave)
		self._cache[seguro] = encontrado
		return encontrado

	def datos(self, nombre: str) -> tuple[np.ndarray, int]:
		"""(muestras, frecuencia) de ``nombre``: lo que piden los motores como ``resolver``."""
		encontrado = self.sonido(nombre)
		self._entregado[nombre] = encontrado.firma()
		return encontrado.datos, encontrado.frecuencia

	def origen(self, nombre: str) -> str:
		"""De dónde sale ese sonido: entorno, complemento, serie, sintetizado o reserva."""
		return self.sonido(nombre).origen

	def existe(self, nombre: str) -> bool:
		"""Si el sonido existe de verdad (no haría falta la reserva)."""
		seguro = nombre_seguro(nombre)
		if seguro is None:
			return False
		return self.sonido(seguro).origen != "reserva"

	def precargar(self, motor: object, nombres: list[str]) -> int:
		"""Carga en ``motor`` esos sonidos de antemano (al empezar un entorno) para que el primero no tarde."""
		cargados = 0
		for nombre in nombres:
			encontrado = self.sonido(nombre)
			motor.cargar(nombre, datos=encontrado.datos, frecuencia=encontrado.frecuencia)  # type: ignore[attr-defined]
			self._entregado[nombre] = encontrado.firma()
			cargados += 1
		return cargados

	def recargar_en(
		self, motor: object, fundido: float = FUNDIDO_PAQUETE, forzar: bool = False, nombres: Iterable[str] | None = None
	) -> int:
		"""Vuelve a cargar en ``motor`` los sonidos que ya tenía y que ahora son otros. Devuelve cuántos.

		Es la mitad «motor» del cambio de paquete en caliente: tras :meth:`poner_paquete` (o un cambio
		de igualado o de volumen por sonido), cada sonido que el motor tenía cargado se vuelve a
		resolver; si ha cambiado (otro fichero u otra ganancia) se sustituye con
		``motor.recargar_sonido``, que además pasa al sonido nuevo los **bucles que estén sonando**,
		con un fundido de ``fundido`` segundos y sin tocar su posición, su volumen ni su filtro. Lo que
		no cambia (los sonidos propios del entorno, los de un complemento, lo que el paquete nuevo
		hereda del de por defecto) no se toca: ni se recarga ni se interrumpe.

		Hay que llamarlo desde el hilo que maneja el motor. ``forzar`` recarga todo sin comparar (por
		ejemplo, tras cambiar de entorno); ``nombres`` limita la recarga a esos sonidos.
		"""
		cargados = getattr(motor, "sonidos_cargados", None)
		if nombres is None:
			if cargados is None:
				log.warning("El motor de sonido %s no dice qué sonidos tiene cargados: no se recarga nada.", type(motor).__name__)
				return 0
			nombres = cargados()
		recargar = getattr(motor, "recargar_sonido", None)
		cambiados = 0
		for nombre in list(nombres):
			if nombre.startswith(PREFIJO_MUESTRA):
				continue
			encontrado = self.sonido(nombre)
			firma = encontrado.firma()
			if not forzar and self._entregado.get(nombre) == firma:
				continue
			if recargar is not None:
				recargar(nombre, encontrado.datos, encontrado.frecuencia, fundido)
			else:
				motor.cargar(nombre, datos=encontrado.datos, frecuencia=encontrado.frecuencia)  # type: ignore[attr-defined]
			self._entregado[nombre] = firma
			cambiados += 1
		if cambiados:
			log.info("Sonidos recargados en el motor tras el cambio: %s.", cambiados)
		return cambiados


def _sin_extension(nombre: str) -> str:
	"""El nombre sin su extensión de audio, si la trae (``timbre.ogg`` → ``timbre``)."""
	sufijo = Path(nombre).suffix
	return nombre[: -len(sufijo)] if sufijo.lower() in EXTENSIONES else nombre


def _sonidos_en(carpeta: Path) -> set[str]:
	"""Los nombres de sonido (``puerta/abrir``) de los ficheros de audio que hay en una carpeta de paquete."""
	nombres: set[str] = set()
	try:
		for ruta in carpeta.rglob("*"):
			if ruta.suffix.lower() in EXTENSIONES and ruta.is_file():
				nombres.add(ruta.relative_to(carpeta).with_suffix("").as_posix())
	except OSError:
		log.warning("No se pudo recorrer el paquete de sonidos %s.", carpeta, exc_info=True)
	return nombres


def leer_ficha(carpeta: Path) -> dict:
	"""El ``pack.json`` de un paquete de sonidos; un dict vacío si no está o no se puede leer.

	Un paquete es de terceros: su ficha puede faltar, estar a medio escribir o no ser un objeto. Nada
	de eso impide usar sus sonidos; se avisa en el registro y el paquete se llama como su carpeta.
	"""
	ruta = Path(carpeta) / NOMBRE_FICHA
	if not ruta.is_file():
		return {}
	try:
		leido = json.loads(ruta.read_text(encoding="utf-8-sig"))
	except OSError, ValueError:
		log.warning("La ficha %s del paquete de sonidos no se puede leer; se usa el nombre de la carpeta.", ruta, exc_info=True)
		return {}
	if not isinstance(leido, dict):
		log.warning("La ficha %s del paquete de sonidos no es un objeto JSON; se ignora.", ruta)
		return {}
	return leido


def _fichero(carpeta: Path, nombre: str) -> Path | None:
	"""El fichero de ``nombre`` dentro de ``carpeta``, con o sin extensión, sin salirse de ella."""
	base = carpeta / nombre
	candidatos = [base] if base.suffix.lower() in EXTENSIONES else [carpeta / (nombre + extension) for extension in EXTENSIONES]
	raiz = carpeta.resolve()
	for candidato in candidatos:
		if candidato.is_file():
			try:
				candidato.resolve().relative_to(raiz)
			except ValueError:
				log.warning("El sonido %s apunta fuera de su carpeta; se ignora.", candidato)
				continue
			return candidato
	return None


def _leer_ruta(ruta: Path) -> tuple[np.ndarray, int] | None:
	try:
		return sintesis.leer_audio(ruta)
	except OSError, ValueError, RuntimeError:
		log.warning("No se pudo leer el sonido %s.", ruta, exc_info=True)
		return None


def _leer_bytes(contenido: bytes) -> tuple[np.ndarray, int]:
	"""Decodifica un sonido que viene en memoria (de dentro de un paquete ``.elab``)."""
	import soundfile

	datos, frecuencia = soundfile.read(io.BytesIO(contenido), dtype="float32", always_2d=False)
	if datos.ndim == 2 and datos.shape[1] > 2:
		datos = datos[:, :2]
	return np.ascontiguousarray(datos, dtype=np.float32), int(frecuencia)


def catalogo_sonidos() -> dict:
	"""El catálogo para el menú «Aprender los sonidos»: grupos y, de cada sonido, nombre, explicación y grupo.

	Se lee ``catalogo.json`` de ``data/sounds`` para saber qué ficheros hay de verdad, pero los textos
	salen de :mod:`app.audio.sintesis`, que es donde están marcados para traducir. Si el fichero no
	está, se devuelve el catálogo del código (los sonidos se sintetizarán al pedirlos).

	Formato: ``{"formato": 1, "grupos": [{"id", "nombre"}], "sonidos": {clave: {"nombre", "explicacion",
	"grupo", "bucle", "posicionable", "fichero", "duracion"}}}``.
	"""
	base: dict = {}
	for carpeta in carpetas_de_serie("sounds"):
		ruta = carpeta / "catalogo.json"
		if not ruta.is_file():
			continue
		try:
			leido = json.loads(ruta.read_text(encoding="utf-8"))
		except OSError, ValueError:
			log.warning("No se pudo leer %s.", ruta, exc_info=True)
			continue
		if isinstance(leido, dict) and isinstance(leido.get("sonidos"), dict):
			base = leido
			break
	if not base:
		base = sintesis.datos_catalogo()
	from app.core.i18n import _ as traducir

	grupos = [{"id": identificador, "nombre": traducir(nombre)} for identificador, nombre in sintesis.GRUPOS]
	sonidos: dict[str, dict] = {}
	for clave, ficha in base.get("sonidos", {}).items():
		if not isinstance(ficha, dict):
			continue
		definicion = sintesis.CATALOGO.get(clave)
		copia = dict(ficha)
		if definicion is not None:
			copia["nombre"] = definicion.nombre_visible()
			copia["explicacion"] = definicion.explicacion_visible()
		sonidos[clave] = copia
	return {"formato": base.get("formato", 1), "grupos": grupos, "sonidos": sonidos}
