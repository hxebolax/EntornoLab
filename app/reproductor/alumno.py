"""El alumno en el reproductor: un ALIAS y un fichero pequeño con lo suyo.

El reproductor no abre la base de datos del profesional (puede estar en otro
ordenador y va cifrada). Solo conoce un alias —nunca un nombre real— y guarda
por alias, en ``data/config/alumnos/<alias>.json``:

- sus preferencias de juego (cómo se mueve, cómo se le dicen las direcciones,
  cuánto detalle quiere, su estilo);
- su colección de premios (estrellas, medallas y objetos encontrados);
- la última actividad que jugó, para «Continuar»;
- si ya hizo el tutorial;
- el nivel de ayudas en que va en cada actividad (``niveles``);
- lo último que le llegó de su ficha del Estudio por la sala (``ficha``:
  ajustes de juego, lista de trabajo y niveles), para usarlo también los días
  que juegue sin conexión.

El fichero no lleva ningún dato personal: aunque se copie o se pierda, solo
dice que «Luna» tiene doce estrellas.
"""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core import paths

log = logging.getLogger(__name__)

FORMATO = 1
CARPETA = "alumnos"
ALIAS_INVITADO = "invitado"
LONGITUD_MAXIMA = 40
# Premios que se conservan por alumno: de sobra para años de uso, y el fichero no crece sin fin.
PREMIOS_MAXIMOS = 2000

_NO_VALIDOS = re.compile(r"[^a-z0-9]+")


def normalizar_alias(alias: str) -> str:
	"""El alias tal como se guarda y se dice: sin espacios de más y con longitud acotada."""
	limpio = " ".join(str(alias or "").split())
	return "".join(c for c in limpio if c.isprintable())[:LONGITUD_MAXIMA].strip()


def alias_para_mostrar(alias: str) -> str:
	"""El alias como se dice o se enseña: el del invitado, traducido («guest» en inglés).

	``ALIAS_INVITADO`` es un identificador (nombre de fichero y de la sesión) y
	no se traduce; solo cambia lo que oye el alumno.
	"""
	from app.core.i18n import _

	return _("invitado") if alias == ALIAS_INVITADO else alias


def _nombre_fichero(alias: str) -> str:
	"""Nombre de fichero seguro para un alias («Luna Ñ» → ``luna_n``)."""
	plano = unicodedata.normalize("NFD", alias.casefold())
	plano = "".join(c for c in plano if unicodedata.category(c) != "Mn")
	return _NO_VALIDOS.sub("_", plano).strip("_") or ALIAS_INVITADO


def carpeta_alumnos() -> Path:
	"""``data/config/alumnos`` (se crea si falta)."""
	carpeta = paths.ruta_configuracion() / CARPETA
	carpeta.mkdir(parents=True, exist_ok=True)
	return carpeta


def _leer(ruta: Path) -> dict[str, Any] | None:
	try:
		datos = json.loads(ruta.read_text(encoding="utf-8"))
	except OSError, ValueError, UnicodeDecodeError:
		# El nombre del fichero lleva el alias: no se escribe en el registro.
		log.warning("No se pudo leer un perfil de alumno; se ignora.", exc_info=True)
		return None
	return datos if isinstance(datos, dict) else None


def _ficha_limpia(ficha: dict[str, Any]) -> dict[str, Any]:
	"""La parte de la ficha del Estudio que se guarda en el perfil, con los tipos esperados (el fichero se puede haber tocado a mano)."""
	limpia: dict[str, Any] = {}
	ajustes = ficha.get("ajustes")
	if isinstance(ajustes, dict):
		limpia["ajustes"] = {str(k): v for k, v in ajustes.items() if isinstance(v, (str, int, float)) and not isinstance(v, bool)}
	lista = ficha.get("lista")
	if isinstance(lista, list):
		limpia["lista"] = [{str(k): str(v) for k, v in entrada.items()} for entrada in lista if isinstance(entrada, dict)]
	niveles = ficha.get("niveles")
	if isinstance(niveles, dict):
		limpia["niveles"] = {str(k): int(v) for k, v in niveles.items() if isinstance(v, int) and not isinstance(v, bool)}
	if isinstance(ficha.get("recibida"), str):
		limpia["recibida"] = ficha["recibida"]
	return limpia


def listar_alias() -> list[str]:
	"""Alias con perfil en este equipo, por orden alfabético."""
	encontrados: list[str] = []
	for ruta in sorted(carpeta_alumnos().glob("*.json")):
		datos = _leer(ruta)
		alias = normalizar_alias(str((datos or {}).get("alias") or ""))
		if alias and alias not in encontrados:
			encontrados.append(alias)
	return sorted(encontrados, key=str.casefold)


class Perfil:
	"""Lo que el reproductor recuerda de un alias. Se guarda solo, de forma atómica, cada vez que cambia."""

	def __init__(self, alias: str, ruta: Path | None = None, datos: dict[str, Any] | None = None) -> None:
		self.alias = normalizar_alias(alias) or ALIAS_INVITADO
		self.ruta = ruta if ruta is not None else carpeta_alumnos() / f"{_nombre_fichero(self.alias)}.json"
		datos = datos if isinstance(datos, dict) else {}
		preferencias = datos.get("preferencias")
		premios = datos.get("premios")
		actividades = datos.get("actividades")
		ultima = datos.get("ultima")
		self.preferencias: dict[str, Any] = dict(preferencias) if isinstance(preferencias, dict) else {}
		self.premios: list[dict[str, Any]] = [dict(p) for p in premios if isinstance(p, dict)] if isinstance(premios, list) else []
		self.actividades: dict[str, dict[str, Any]] = (
			{str(k): dict(v) for k, v in actividades.items() if isinstance(v, dict)} if isinstance(actividades, dict) else {}
		)
		self.ultima: dict[str, Any] = dict(ultima) if isinstance(ultima, dict) else {}
		self.tutorial_hecho = bool(datos.get("tutorial_hecho", False))
		niveles = datos.get("niveles")
		self.niveles: dict[str, int] = (
			{str(k): int(v) for k, v in niveles.items() if isinstance(v, int) and not isinstance(v, bool) and v >= 0}
			if isinstance(niveles, dict)
			else {}
		)
		ficha = datos.get("ficha")
		self.ficha: dict[str, Any] = _ficha_limpia(ficha) if isinstance(ficha, dict) else {}

	# ── Cargar y guardar ──

	@classmethod
	def cargar(cls, alias: str) -> Perfil:
		"""El perfil de ese alias; uno nuevo y vacío si no existe o su fichero está dañado."""
		limpio = normalizar_alias(alias) or ALIAS_INVITADO
		base = _nombre_fichero(limpio)
		carpeta = carpeta_alumnos()
		# Dos alias distintos pueden dar el mismo nombre de fichero («Ana» y «Aná»): se busca el que lleva ESE alias dentro.
		libre: Path | None = None
		for numero in range(0, 50):
			ruta = carpeta / (f"{base}.json" if numero == 0 else f"{base}_{numero + 1}.json")
			if not ruta.is_file():
				libre = libre or ruta
				continue
			datos = _leer(ruta)
			if datos is not None and normalizar_alias(str(datos.get("alias") or "")).casefold() == limpio.casefold():
				return cls(limpio, ruta, datos)
		return cls(limpio, libre)

	def a_dict(self) -> dict[str, Any]:
		"""Contenido del fichero."""
		return {
			"formato": FORMATO,
			"alias": self.alias,
			"preferencias": dict(self.preferencias),
			"premios": [dict(p) for p in self.premios],
			"actividades": {clave: dict(valor) for clave, valor in self.actividades.items()},
			"ultima": dict(self.ultima),
			"tutorial_hecho": self.tutorial_hecho,
			"niveles": dict(self.niveles),
			"ficha": _ficha_limpia(self.ficha),
		}

	def guardar(self) -> bool:
		"""Escribe el fichero (temporal + sustitución). No lanza: un disco lleno no debe parar el juego."""
		temporal = self.ruta.with_name(f"{self.ruta.name}.{os.getpid()}.tmp")
		try:
			self.ruta.parent.mkdir(parents=True, exist_ok=True)
			temporal.write_text(json.dumps(self.a_dict(), ensure_ascii=False, indent="\t"), encoding="utf-8", newline="\n")
			os.replace(temporal, self.ruta)
		except OSError:
			log.exception("No se pudo guardar el perfil del alumno")
			try:
				temporal.unlink(missing_ok=True)
			except OSError:
				log.debug("No se pudo borrar el temporal del perfil", exc_info=True)
			return False
		return True

	# ── Preferencias ──

	def poner_preferencia(self, clave: str, valor: Any) -> None:
		"""Apunta una preferencia de juego («juego.unidad» → «pasos») y guarda."""
		if self.preferencias.get(clave) != valor:
			self.preferencias[clave] = valor
			self.guardar()

	def quitar_preferencia(self, clave: str) -> None:
		"""Olvida una preferencia (vuelve a valer la de la ficha o la del equipo) y guarda."""
		if clave in self.preferencias:
			del self.preferencias[clave]
			self.guardar()

	# ── Ficha del Estudio y niveles ──

	@staticmethod
	def clave_nivel(entorno_id: str, actividad_id: str) -> str:
		"""Clave del nivel de una actividad: «entorno/actividad» (la misma que usa la ficha del Estudio)."""
		return f"{entorno_id}/{actividad_id}"

	def nivel(self, entorno_id: str, actividad_id: str) -> int | None:
		"""Nivel de ayudas en que va el alumno en esa actividad, o None si nunca la ha jugado con niveles."""
		return self.niveles.get(self.clave_nivel(entorno_id, actividad_id))

	def poner_nivel(self, entorno_id: str, actividad_id: str, nivel: int) -> None:
		"""Apunta el nivel con el que empezará la próxima vez y guarda."""
		clave = self.clave_nivel(entorno_id, actividad_id)
		if self.niveles.get(clave) != int(nivel):
			self.niveles[clave] = max(0, int(nivel))
			self.guardar()

	def recibir_ficha(
		self, ajustes: dict[str, Any] | None, lista: list[dict[str, Any]] | None, niveles: dict[str, int] | None
	) -> list[str]:
		"""Guarda lo que llega de la ficha del Estudio. Devuelve las claves de nivel que han cambiado aquí.

		Los ajustes y la lista sustituyen a los anteriores (``None`` = no venían).
		Un nivel de la ficha manda sobre el local solo si la ficha ha cambiado
		desde la última vez (el profesional lo ha tocado, o se ha incorporado
		una sesión): así una ficha aún sin poner al día no hace retroceder al
		alumno que acaba de subir de nivel jugando en este equipo.
		"""
		nueva = dict(self.ficha)
		if ajustes is not None:
			nueva["ajustes"] = dict(ajustes)
		if lista is not None:
			nueva["lista"] = [dict(entrada) for entrada in lista]
		cambiados: list[str] = []
		if niveles is not None:
			vistos = dict(nueva.get("niveles") or {})
			for clave, nivel in niveles.items():
				if vistos.get(clave) != nivel:
					vistos[clave] = nivel
					if self.niveles.get(clave) != nivel:
						self.niveles[clave] = nivel
						cambiados.append(clave)
			nueva["niveles"] = vistos
		nueva["recibida"] = datetime.now().isoformat(timespec="seconds")
		self.ficha = _ficha_limpia(nueva)
		self.guardar()
		return cambiados

	def olvidar_ajuste_de_ficha(self, clave: str) -> None:
		"""El alumno ha cambiado él mismo un ajuste que fijaba la ficha: desde ahora vale el suyo (hasta que llegue otra ficha)."""
		ajustes = self.ficha.get("ajustes")
		if isinstance(ajustes, dict) and clave in ajustes:
			del ajustes[clave]
			self.guardar()

	@property
	def lista_trabajo(self) -> list[dict[str, Any]]:
		"""Actividades que el profesional le ha asignado (la última lista recibida)."""
		return [dict(entrada) for entrada in self.ficha.get("lista") or [] if isinstance(entrada, dict)]

	# ── Última actividad ──

	def recordar_ultima(self, ruta: Path | str, actividad_id: str, entorno: str, actividad: str) -> None:
		"""Apunta lo último que se jugó, para «Continuar la última actividad»."""
		self.ultima = {"ruta": str(ruta), "actividad": actividad_id, "entorno": entorno, "nombre": actividad}
		self.guardar()

	# ── Premios ──

	def anadir_premios(self, recompensas: list[dict[str, Any]], entorno: str, actividad: str) -> list[dict[str, Any]]:
		"""Guarda en la colección las recompensas de una actividad. Devuelve las que se han guardado."""
		fecha = datetime.now().strftime("%Y-%m-%d")
		nuevas: list[dict[str, Any]] = []
		for recompensa in recompensas:
			if not isinstance(recompensa, dict):
				continue
			nombre = str(recompensa.get("nombre") or recompensa.get("texto") or "").strip()
			tipo = str(recompensa.get("tipo") or "objeto").strip() or "objeto"
			if not nombre:
				continue
			nuevas.append(
				{"tipo": tipo[:30], "nombre": nombre[:200], "entorno": entorno[:200], "actividad": actividad[:200], "fecha": fecha}
			)
		if nuevas:
			self.premios.extend(nuevas)
			del self.premios[:-PREMIOS_MAXIMOS]
			self.guardar()
		return nuevas

	def apuntar_actividad(self, clave: str, estrellas: int, completada: bool) -> bool:
		"""Cuenta una partida de una actividad. Devuelve True si se ha superado la mejor marca de estrellas."""
		ficha = self.actividades.setdefault(clave, {"veces": 0, "completadas": 0, "estrellas": 0})
		ficha["veces"] = int(ficha.get("veces", 0)) + 1
		if completada:
			ficha["completadas"] = int(ficha.get("completadas", 0)) + 1
		mejora = estrellas > int(ficha.get("estrellas", 0))
		if mejora:
			ficha["estrellas"] = int(estrellas)
		self.guardar()
		return mejora

	def estrellas(self) -> int:
		"""Suma de la mejor marca de estrellas de cada actividad."""
		return sum(int(ficha.get("estrellas", 0)) for ficha in self.actividades.values())

	def cuenta_premios(self) -> dict[str, int]:
		"""Cuántos premios hay de cada tipo."""
		cuenta: dict[str, int] = {}
		for premio in self.premios:
			tipo = str(premio.get("tipo") or "objeto")
			cuenta[tipo] = cuenta.get(tipo, 0) + 1
		return cuenta
