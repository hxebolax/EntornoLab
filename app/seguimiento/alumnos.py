"""Fichas de alumnos: alta, edición, archivado, búsqueda, exportación, borrado y caducidad.

Principios (apartado 17 del informe del proyecto):

- El alumno se identifica por un ALIAS, obligatorio y único. El nombre real y
  las notas son opcionales y se guardan cifrados.
- El alumno (o su familia) puede pedir todos sus datos: ``exportar`` los
  entrega en un ZIP con JSON y CSV legibles sin el programa.
- Y puede pedir que se borren: ``borrar`` elimina la ficha y todo lo suyo
  (sesiones, marcas, evaluaciones, recompensas, ficheros de sesión sin
  incorporar y copias de seguridad que lo contenían). No se puede deshacer.
- Los datos no se guardan para siempre: ``caducar_sesiones`` borra las
  sesiones con más de N días.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import sqlite3
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.i18n import _
from app.seguimiento import cuaderno, recompensas, sesiones
from app.seguimiento.base import ESTILOS, PERFILES, BaseSeguimiento, ErrorDatos, ahora_iso, normalizar_busqueda

log = logging.getLogger(__name__)

ALIAS_MAXIMO = 60

# Campos que admite ``Fichas.editar``.
_EDITABLES = ("alias", "nombre_real", "notas", "ano_nacimiento", "perfil", "estilo", "ajustes")


@dataclass
class Alumno:
	"""Ficha de un alumno, con los campos sensibles ya descifrados."""

	id: int
	alias: str
	nombre_real: str = ""
	notas: str = ""
	ano_nacimiento: int | None = None
	perfil: str = "otro"
	estilo: str = "adulto"
	ajustes: dict[str, Any] = field(default_factory=dict)
	alta: str = ""
	archivado: bool = False


def _validar_alias(alias: str) -> str:
	limpio = " ".join(str(alias).split())
	if not limpio:
		raise ErrorDatos(_("El alias es obligatorio."))
	if len(limpio) > ALIAS_MAXIMO:
		raise ErrorDatos(_("El alias no puede tener más de {maximo} caracteres.").format(maximo=ALIAS_MAXIMO))
	return limpio


def _validar_campos(perfil: str, estilo: str, ano_nacimiento: int | None, ajustes: Any) -> None:
	if perfil not in PERFILES:
		raise ErrorDatos(_("Perfil de movilidad desconocido: {valor}").format(valor=perfil))
	if estilo not in ESTILOS:
		raise ErrorDatos(_("Estilo desconocido: {valor}").format(valor=estilo))
	if ano_nacimiento is not None:
		actual = datetime.now().year
		if isinstance(ano_nacimiento, bool) or not isinstance(ano_nacimiento, int) or not 1900 <= ano_nacimiento <= actual:
			raise ErrorDatos(_("El año de nacimiento debe estar entre 1900 y {actual}.").format(actual=actual))
	if not isinstance(ajustes, dict):
		raise ErrorDatos(_("Los ajustes de juego deben ser un diccionario."))


def _fila_csv(valores: list[Any]) -> list[str]:
	"""Valores listos para CSV; se desactivan las fórmulas (una celda que empieza por = se abriría como tal)."""
	celdas: list[str] = []
	for valor in valores:
		texto = "" if valor is None else str(valor)
		if texto[:1] in ("=", "+", "-", "@") and not _es_numero(texto):
			texto = "'" + texto
		celdas.append(texto)
	return celdas


def _es_numero(texto: str) -> bool:
	try:
		float(texto.replace(",", "."))
	except ValueError:
		return False
	return True


def _csv(cabecera: list[str], filas: list[list[Any]]) -> bytes:
	"""CSV con punto y coma y BOM: se abre bien en la hoja de cálculo en español."""
	salida = io.StringIO()
	escritor = csv.writer(salida, delimiter=";", lineterminator="\r\n")
	escritor.writerow(cabecera)
	for fila in filas:
		escritor.writerow(_fila_csv(fila))
	return salida.getvalue().encode("utf-8-sig")


class Fichas:
	"""Operaciones sobre las fichas de alumnos de una base."""

	def __init__(self, base: BaseSeguimiento) -> None:
		self.base = base

	# ── Lectura ──────────────────────────────────────────────────────────────

	def _de_fila(self, fila: sqlite3.Row) -> Alumno:
		try:
			ajustes = json.loads(fila["ajustes"])
		except ValueError:
			log.error("Los ajustes de una ficha no son JSON válido; se usan los de serie")
			ajustes = {}
		return Alumno(
			id=fila["id"],
			alias=fila["alias"],
			nombre_real=self.base.descifrar_texto(fila["nombre_real"]) or "",
			notas=self.base.descifrar_texto(fila["notas"]) or "",
			ano_nacimiento=fila["ano_nacimiento"],
			perfil=fila["perfil"],
			estilo=fila["estilo"],
			ajustes=ajustes if isinstance(ajustes, dict) else {},
			alta=fila["alta"],
			archivado=bool(fila["archivado"]),
		)

	def obtener(self, alumno_id: int) -> Alumno | None:
		"""Ficha por id, o ``None``."""
		fila = self.base.consultar_uno("SELECT * FROM alumnos WHERE id = ?", (alumno_id,))
		return None if fila is None else self._de_fila(fila)

	def por_alias(self, alias: str) -> Alumno | None:
		"""Ficha por alias (sin distinguir mayúsculas ni acentos), o ``None``."""
		fila = self.base.consultar_uno("SELECT * FROM alumnos WHERE alias_busqueda = ?", (normalizar_busqueda(" ".join(alias.split())),))
		return None if fila is None else self._de_fila(fila)

	def buscar(self, texto: str = "", *, incluir_archivados: bool = False) -> list[Alumno]:
		"""Alumnos cuyo alias contiene ``texto``, por orden alfabético.

		Solo se busca en el alias: el nombre real está cifrado y no se indexa
		a propósito (un índice en claro anularía el cifrado).
		"""
		sql = "SELECT * FROM alumnos WHERE 1 = 1"
		parametros: list[Any] = []
		buscado = normalizar_busqueda(texto)
		if buscado:
			escapado = buscado.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
			sql += " AND alias_busqueda LIKE ? ESCAPE '\\'"
			parametros.append(f"%{escapado}%")
		if not incluir_archivados:
			sql += " AND archivado = 0"
		return [self._de_fila(fila) for fila in self.base.consultar(sql + " ORDER BY alias_busqueda", parametros)]

	# ── Escritura ────────────────────────────────────────────────────────────

	def alta(
		self,
		alias: str,
		*,
		nombre_real: str = "",
		notas: str = "",
		ano_nacimiento: int | None = None,
		perfil: str = "otro",
		estilo: str = "adulto",
		ajustes: dict[str, Any] | None = None,
	) -> Alumno:
		"""Crea una ficha. El alias es obligatorio y único."""
		alias = _validar_alias(alias)
		ajustes = ajustes if ajustes is not None else {}
		_validar_campos(perfil, estilo, ano_nacimiento, ajustes)
		if self.por_alias(alias) is not None:
			raise ErrorDatos(_("Ya hay un alumno con ese alias."))
		try:
			nuevo = self.base.insertar(
				"INSERT INTO alumnos (alias, alias_busqueda, nombre_real, notas, ano_nacimiento, perfil, estilo, ajustes, alta) "
				"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
				(
					alias,
					normalizar_busqueda(alias),
					self.base.cifrar_texto(nombre_real.strip()),
					self.base.cifrar_texto(notas),
					ano_nacimiento,
					perfil,
					estilo,
					json.dumps(ajustes, ensure_ascii=False),
					ahora_iso(),
				),
			)
		except sqlite3.IntegrityError as error:
			raise ErrorDatos(_("Ya hay un alumno con ese alias.")) from error
		log.info("Ficha de alumno creada")
		ficha = self.obtener(nuevo)
		assert ficha is not None
		return ficha

	def editar(self, alumno_id: int, **cambios: Any) -> Alumno:
		"""Cambia campos de una ficha: alias, nombre_real, notas, ano_nacimiento, perfil, estilo, ajustes."""
		ficha = self.obtener(alumno_id)
		if ficha is None:
			raise ErrorDatos(_("El alumno no existe."))
		desconocidos = set(cambios) - set(_EDITABLES)
		if desconocidos:
			raise ErrorDatos(_("Campos que no se pueden editar: {campos}").format(campos=", ".join(sorted(desconocidos))))
		nuevo = asdict(ficha)
		nuevo.update(cambios)
		nuevo["alias"] = _validar_alias(nuevo["alias"])
		_validar_campos(nuevo["perfil"], nuevo["estilo"], nuevo["ano_nacimiento"], nuevo["ajustes"])
		otro = self.por_alias(nuevo["alias"])
		if otro is not None and otro.id != alumno_id:
			raise ErrorDatos(_("Ya hay un alumno con ese alias."))
		try:
			self.base.ejecutar(
				"UPDATE alumnos SET alias = ?, alias_busqueda = ?, nombre_real = ?, notas = ?, ano_nacimiento = ?, perfil = ?, "
				"estilo = ?, ajustes = ? WHERE id = ?",
				(
					nuevo["alias"],
					normalizar_busqueda(nuevo["alias"]),
					self.base.cifrar_texto(str(nuevo["nombre_real"] or "").strip()),
					self.base.cifrar_texto(str(nuevo["notas"] or "")),
					nuevo["ano_nacimiento"],
					nuevo["perfil"],
					nuevo["estilo"],
					json.dumps(nuevo["ajustes"], ensure_ascii=False),
					alumno_id,
				),
			)
		except sqlite3.IntegrityError as error:
			raise ErrorDatos(_("Ya hay un alumno con ese alias.")) from error
		ficha = self.obtener(alumno_id)
		assert ficha is not None
		return ficha

	def archivar(self, alumno_id: int, si: bool = True) -> bool:
		"""Archiva (o recupera) una ficha: deja de salir en las listas, pero no se borra nada."""
		return self.base.ejecutar("UPDATE alumnos SET archivado = ? WHERE id = ?", (int(si), alumno_id)) > 0

	# ── Exportar ─────────────────────────────────────────────────────────────

	def exportar(self, alumno_id: int, destino: Path | str) -> Path:
		"""Escribe en ``destino`` un ZIP con TODOS los datos del alumno, legibles sin el programa.

		Contenido: ``LEEME.txt``, ``alumno.json``, ``sesiones.csv``,
		``sesiones/<id>.json`` (resumen, traza, notas y marcas),
		``evaluaciones_reales.json`` y ``.csv``, ``recompensas.csv``.

		El ZIP va SIN cifrar (es para entregarlo): quien lo pide debe guardarlo
		con cuidado, y así lo dice el LEEME.
		"""
		ficha = self.obtener(alumno_id)
		if ficha is None:
			raise ErrorDatos(_("El alumno no existe."))
		destino = Path(destino)
		destino.parent.mkdir(parents=True, exist_ok=True)
		lista = sesiones.listar(self.base, alumno_id)
		evaluaciones = cuaderno.listar(self.base, alumno_id)
		ganadas = recompensas.de_alumno(self.base, alumno_id)
		leeme = "\r\n".join(
			[
				_("Datos de un alumno exportados de EntornoLab"),
				"",
				_("Fecha de la exportación: {fecha}").format(fecha=ahora_iso()),
				"",
				_("Este archivo contiene todos los datos guardados del alumno y NO está cifrado. Guárdelo en un lugar seguro."),
				"",
				_("alumno.json: la ficha."),
				_("sesiones.csv: una fila por sesión con sus medidas principales."),
				_("sesiones/: una sesión por fichero, con el resumen completo, el recorrido, las notas y las marcas."),
				_("evaluaciones_reales.json y .csv: el cuaderno de evaluación en el lugar real."),
				_("recompensas.csv: estrellas, medallas y objetos ganados."),
				"",
				_("Los ficheros CSV usan punto y coma como separador y codificación UTF-8."),
				_("Las medidas son descriptivas: el rendimiento en el simulador no equivale a competencia en el lugar real."),
				"",
			]
		)
		filas_sesiones: list[list[Any]] = []
		for sesion in lista:
			resumen = sesion["resumen"]
			filas_sesiones.append(
				[
					sesion["id"],
					sesion["inicio"],
					sesion["fin"],
					sesion["entorno_nombre"],
					sesion["actividad_nombre"],
					sesion["actividad_tipo"],
					sesion["modo"],
					int(sesion["completada"]),
					sesion["tiempo_activo"],
					sesion["tiempo_pausa"],
					resumen.get("distancia_m"),
					(resumen.get("choques") or {}).get("total"),
					(resumen.get("ayudas") or {}).get("total"),
					resumen.get("cociente_camino"),
				]
			)
		temporal = destino.with_name(destino.name + ".tmp")
		try:
			with zipfile.ZipFile(temporal, "w", zipfile.ZIP_DEFLATED) as paquete:
				paquete.writestr("LEEME.txt", leeme.encode("utf-8-sig"))
				paquete.writestr("alumno.json", json.dumps(asdict(ficha), ensure_ascii=False, indent=2))
				paquete.writestr(
					"sesiones.csv",
					_csv(
						[
							_("Sesión"),
							_("Inicio"),
							_("Fin"),
							_("Entorno"),
							_("Actividad"),
							_("Tipo de actividad"),
							_("Modo"),
							_("Completada"),
							_("Tiempo activo (s)"),
							_("Tiempo en pausa (s)"),
							_("Distancia (m)"),
							_("Choques"),
							_("Ayudas pedidas"),
							_("Cociente camino real / óptimo"),
						],
						filas_sesiones,
					),
				)
				for sesion in lista:
					completa = sesiones.obtener(self.base, sesion["id"], con_traza=True)
					paquete.writestr(f"sesiones/{sesion['id']}.json", json.dumps(completa, ensure_ascii=False, indent=1))
				paquete.writestr("evaluaciones_reales.json", json.dumps([asdict(e) for e in evaluaciones], ensure_ascii=False, indent=2))
				paquete.writestr(
					"evaluaciones_reales.csv",
					_csv(
						[
							_("Fecha"),
							_("Lugar"),
							_("Entorno"),
							_("Rutas"),
							_("Nivel de ayuda"),
							_("Tipo de recorrido"),
							_("Ayudas de movilidad"),
							_("Días desde el último entrenamiento"),
							_("Observaciones"),
						],
						[
							[
								e.fecha,
								e.lugar,
								e.entorno_nombre,
								" | ".join(f"{r.get('nombre', '')}: {r.get('resultado', '')}" for r in e.rutas),
								e.nivel_ayuda,
								e.tipo_recorrido,
								", ".join(e.ayudas_movilidad),
								e.dias_desde_entrenamiento,
								e.observaciones,
							]
							for e in evaluaciones
						],
					),
				)
				paquete.writestr(
					"recompensas.csv",
					_csv(
						[_("Fecha"), _("Tipo"), _("Nombre"), _("Sesión")],
						[[r.fecha, r.tipo, r.nombre, r.sesion_id or ""] for r in ganadas],
					),
				)
			temporal.replace(destino)
		finally:
			if temporal.exists():
				temporal.unlink()
		log.info("Datos de un alumno exportados: %d sesiones, %d evaluaciones", len(lista), len(evaluaciones))
		return destino

	# ── Borrar y caducar ─────────────────────────────────────────────────────

	def borrar(
		self,
		alumno_id: int,
		*,
		carpeta_sesiones: Path | str | None = None,
		purgar_copias: bool = True,
	) -> dict[str, int]:
		"""Borra por completo y sin vuelta atrás un alumno y todo lo suyo.

		Además de las filas de la base (ficha, sesiones, marcas, evaluaciones
		y recompensas), borra sus ficheros de sesión sin incorporar, elimina
		las copias de seguridad anteriores (seguirían conteniéndolo) y compacta
		la base para que los datos no queden en páginas libres del fichero.
		Al final deja una copia nueva, ya sin el alumno.

		Devuelve cuánto se borró de cada cosa. Quien llama debe haber pedido
		confirmación: aquí no se pregunta.
		"""
		# Importación diferida: grabadora.py importa este módulo para crear fichas al incorporar.
		from app.seguimiento.grabadora import borrar_ficheros_de_alias

		ficha = self.obtener(alumno_id)
		if ficha is None:
			raise ErrorDatos(_("El alumno no existe."))
		cuenta = {
			"sesiones": int(self.base.valor("SELECT COUNT(*) FROM sesiones WHERE alumno_id = ?", (alumno_id,), 0)),
			"marcas": int(
				self.base.valor(
					"SELECT COUNT(*) FROM marcas WHERE sesion_id IN (SELECT id FROM sesiones WHERE alumno_id = ?)", (alumno_id,), 0
				)
			),
			"evaluaciones": int(self.base.valor("SELECT COUNT(*) FROM evaluaciones_reales WHERE alumno_id = ?", (alumno_id,), 0)),
			"recompensas": int(self.base.valor("SELECT COUNT(*) FROM recompensas WHERE alumno_id = ?", (alumno_id,), 0)),
		}
		with self.base.transaccion() as tx:
			# Las claves foráneas ON DELETE CASCADE se llevan todo lo que cuelga de la ficha.
			tx.execute("DELETE FROM alumnos WHERE id = ?", (alumno_id,))
		cuenta["ficheros"] = borrar_ficheros_de_alias(carpeta_sesiones, ficha.alias)
		cuenta["copias"] = 0
		if purgar_copias:
			cuenta["copias"] = self.base.purgar_copias()
		self.base.compactar()
		if purgar_copias and cuenta["copias"]:
			self.base.copia_seguridad(motivo="tras-borrar-alumno")
		log.info(
			"Alumno borrado por completo: %d sesiones, %d evaluaciones, %d recompensas, %d ficheros",
			cuenta["sesiones"],
			cuenta["evaluaciones"],
			cuenta["recompensas"],
			cuenta["ficheros"],
		)
		return cuenta

	def caducar_sesiones(self, dias: int, *, ahora: datetime | None = None, alumno_id: int | None = None) -> int:
		"""Borra las sesiones terminadas hace más de ``dias`` días. Devuelve cuántas.

		Las fichas, las evaluaciones reales y las recompensas se conservan: lo
		que caduca es el detalle de cada sesión (recorrido y medidas). El
		número de días lo decide el profesional en las preferencias.
		"""
		if isinstance(dias, bool) or not isinstance(dias, int) or dias < 1:
			raise ErrorDatos(_("La caducidad debe ser de un día o más."))
		momento = ahora if ahora is not None else datetime.now(UTC)
		limite = (momento - timedelta(days=dias)).astimezone(UTC).isoformat(timespec="seconds")
		sql = "DELETE FROM sesiones WHERE fin < ?"
		parametros: list[Any] = [limite]
		if alumno_id is not None:
			sql += " AND alumno_id = ?"
			parametros.append(alumno_id)
		borradas = self.base.ejecutar(sql, parametros)
		if borradas:
			self.base.compactar()
			log.info("Sesiones caducadas y borradas: %d", borradas)
		return borradas
