"""Teclado: mapa de teclas a acciones por contexto, reasignable por intercambio.

El mapa de serie sigue el apartado 12.4 del informe (flechas para moverse, C
para «dónde estoy», W A S D para mirar, Tabulador para lo cercano...), que
conserva las letras que el autor ya usa en sus otros juegos.

Reasignar una acción **intercambia** las teclas, como en Puerto Bravo: si se
pone «dónde estoy» en la P, lo que hacía la P pasa a la C. Así ninguna acción
se queda sin tecla y no hace falta una pantalla para resolver conflictos, que
con voz sería larga de recorrer.

Las teclas se guardan con un nombre propio y estable («arriba»,
«mayus+tabulador», «c»), no con el código de SDL: el fichero de configuración
se puede leer y corregir a mano, y no cambia si cambia la biblioteca.

Este módulo no lee ni escribe la configuración: recibe y devuelve
diccionarios (``MapaTeclado.de_dict`` y ``a_dict``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pygame

from app.core.i18n import N_, _, pgettext
from app.entrada import acciones

log = logging.getLogger(__name__)

# ── Nombres estables de las teclas ───────────────────────────────────────────

# código de pygame → (identificador que se guarda, nombre que se dice)
_ESPECIALES: dict[int, tuple[str, str]] = {
	pygame.K_UP: ("arriba", N_("flecha arriba")),
	pygame.K_DOWN: ("abajo", N_("flecha abajo")),
	pygame.K_LEFT: ("izquierda", N_("flecha izquierda")),
	pygame.K_RIGHT: ("derecha", N_("flecha derecha")),
	pygame.K_SPACE: ("espacio", N_("Espacio")),
	pygame.K_RETURN: ("intro", N_("Intro")),
	pygame.K_KP_ENTER: ("intro_numerico", N_("Intro del teclado numérico")),
	pygame.K_TAB: ("tabulador", N_("Tabulador")),
	pygame.K_ESCAPE: ("escape", N_("Escape")),
	pygame.K_BACKSPACE: ("retroceso", N_("Retroceso")),
	pygame.K_HOME: ("inicio", N_("Inicio")),
	pygame.K_END: ("fin", N_("Fin")),
	pygame.K_PAGEUP: ("repag", N_("Retroceder página")),
	pygame.K_PAGEDOWN: ("avpag", N_("Avanzar página")),
	pygame.K_INSERT: ("insertar", N_("Insertar")),
	pygame.K_DELETE: ("suprimir", N_("Suprimir")),
	pygame.K_COMMA: ("coma", N_("coma")),
	pygame.K_PERIOD: ("punto", N_("punto")),
	pygame.K_MINUS: ("guion", N_("guion")),
	pygame.K_LCTRL: ("control_izquierdo", N_("Control izquierdo")),
	pygame.K_RCTRL: ("control_derecho", N_("Control derecho")),
	pygame.K_LSHIFT: ("mayus_izquierda", N_("Mayúsculas izquierda")),
	pygame.K_RSHIFT: ("mayus_derecha", N_("Mayúsculas derecha")),
	pygame.K_LALT: ("alt_izquierdo", N_("Alt izquierdo")),
	pygame.K_RALT: ("alt_derecho", N_("Alt derecho")),
	pygame.K_LGUI: ("windows_izquierda", N_("Windows izquierda")),
	pygame.K_RGUI: ("windows_derecha", N_("Windows derecha")),
	pygame.K_CAPSLOCK: ("bloq_mayus", N_("Bloqueo de mayúsculas")),
	pygame.K_NUMLOCK: ("bloq_num", N_("Bloqueo numérico")),
	pygame.K_PRINTSCREEN: ("imprimir_pantalla", N_("Imprimir pantalla")),
}
_TECLADO_NUMERICO = (
	pygame.K_KP0,
	pygame.K_KP1,
	pygame.K_KP2,
	pygame.K_KP3,
	pygame.K_KP4,
	pygame.K_KP5,
	pygame.K_KP6,
	pygame.K_KP7,
	pygame.K_KP8,
	pygame.K_KP9,
)
_CODIGO_DE_ID: dict[str, int] = {ident: codigo for codigo, (ident, _nombre) in _ESPECIALES.items()}
_NOMBRE_DE_ID: dict[str, str] = {ident: nombre for ident, nombre in _ESPECIALES.values()}

# Modificadores que pueden formar parte de una combinación, en el orden en que se escriben.
MAYUS = "mayus"
CTRL = "ctrl"
_NOMBRE_MODIFICADOR = {MAYUS: N_("Mayúsculas"), CTRL: N_("Control")}

_TECLAS_MAYUS = (pygame.K_LSHIFT, pygame.K_RSHIFT)
_TECLAS_CTRL = (pygame.K_LCTRL, pygame.K_RCTRL)
_TECLAS_ALT = (pygame.K_LALT, pygame.K_RALT)

# Teclas que ni se reasignan ni sirven de destino. Escape, Intro y F1 son la
# salida, la confirmación y la ayuda: si se pudieran mover, un alumno podría
# quedarse sin forma de pedir ayuda o de salir. F12 está reservada para
# Control+F12, que devuelve la voz automática a quien se ha quedado sin voz
# (ver ``app.reproductor.aplicacion.es_tecla_restablecer_voz``). Las demás son
# del sistema o solo valen como modificador.
FIJAS: frozenset[str] = frozenset(
	{
		"escape",
		"intro",
		"intro_numerico",
		"f1",
		"f12",
		"mayus_izquierda",
		"mayus_derecha",
		"alt_izquierdo",
		"alt_derecho",
		"windows_izquierda",
		"windows_derecha",
		"bloq_mayus",
		"bloq_num",
		"imprimir_pantalla",
	}
)


def id_tecla(codigo: int) -> str:
	"""Identificador estable de una tecla de pygame («c», «f2», «arriba»)."""
	if codigo in _ESPECIALES:
		return _ESPECIALES[codigo][0]
	if pygame.K_a <= codigo <= pygame.K_z or pygame.K_0 <= codigo <= pygame.K_9:
		return chr(codigo)
	if pygame.K_F1 <= codigo <= pygame.K_F12:
		return f"f{codigo - pygame.K_F1 + 1}"
	if codigo in _TECLADO_NUMERICO:
		return f"numerico_{_TECLADO_NUMERICO.index(codigo)}"
	return f"k{int(codigo)}"


def codigo_tecla(identificador: str) -> int | None:
	"""Código de pygame de un identificador de tecla; None si no se reconoce."""
	ident = identificador.strip().lower()
	if ident in _CODIGO_DE_ID:
		return _CODIGO_DE_ID[ident]
	if len(ident) == 1 and ("a" <= ident <= "z" or "0" <= ident <= "9"):
		return ord(ident)
	if ident.startswith("f") and ident[1:].isdigit() and 1 <= int(ident[1:]) <= 12:
		return pygame.K_F1 + int(ident[1:]) - 1
	if ident.startswith("numerico_") and ident[9:].isdigit() and int(ident[9:]) < 10:
		return _TECLADO_NUMERICO[int(ident[9:])]
	if ident.startswith("k") and ident[1:].isdigit():
		return int(ident[1:])
	return None


def combinacion(codigo: int, mod: int = 0) -> str:
	"""Combinación con nombre para una tecla y sus modificadores («mayus+tabulador»).

	Si la tecla es ella misma un modificador (Control solo, para callar la
	voz), ese modificador no se antepone: «control_izquierdo», no
	«ctrl+control_izquierdo».
	"""
	partes: list[str] = []
	if mod & pygame.KMOD_SHIFT and codigo not in _TECLAS_MAYUS:
		partes.append(MAYUS)
	if mod & pygame.KMOD_CTRL and codigo not in _TECLAS_CTRL:
		partes.append(CTRL)
	partes.append(id_tecla(codigo))
	return "+".join(partes)


def _partir(comb: str) -> tuple[list[str], str]:
	"""(modificadores, tecla) de una combinación con nombre."""
	partes = [p.strip().lower() for p in str(comb).split("+") if p.strip()]
	if not partes:
		return [], ""
	return partes[:-1], partes[-1]


def normalizar(comb: str) -> str | None:
	"""Una combinación escrita a mano, en su forma canónica; None si no es válida."""
	modificadores, tecla = _partir(comb)
	if not tecla or codigo_tecla(tecla) is None:
		return None
	if any(m not in (MAYUS, CTRL) for m in modificadores):
		return None
	orden = [m for m in (MAYUS, CTRL) if m in modificadores]
	return "+".join([*orden, id_tecla(codigo_tecla(tecla) or 0)])


def es_fija(comb: str) -> bool:
	"""Si la combinación usa una tecla reservada, que no se puede reasignar."""
	return _partir(comb)[1] in FIJAS


def _traducir_nombre(nombre: str) -> str:
	"""Traduce el nombre de una tecla. «Inicio» y «Mayúsculas» llevan contexto.

	En español son también la hora de comienzo de una sesión y el grupo de
	letras mayúsculas; en otros idiomas son palabras distintas (Home y Start,
	Shift y Uppercase).
	"""
	if nombre == "Inicio":
		return pgettext("tecla", "Inicio")
	if nombre == "Mayúsculas":
		return pgettext("tecla", "Mayúsculas")
	return _(nombre)


def nombre_tecla(identificador: str) -> str:
	"""Nombre hablado de una tecla sola."""
	if identificador in _NOMBRE_DE_ID:
		return _traducir_nombre(_NOMBRE_DE_ID[identificador])
	if len(identificador) == 1:
		return identificador.upper()
	if identificador.startswith("f") and identificador[1:].isdigit():
		return identificador.upper()
	if identificador.startswith("numerico_"):
		return _("{numero} del teclado numérico").format(numero=identificador[9:])
	return _("tecla {codigo}").format(codigo=identificador.lstrip("k"))


def nombre_combinacion(comb: str) -> str:
	"""Nombre hablado de una combinación: «Mayúsculas Tabulador», «flecha arriba», «C»."""
	modificadores, tecla = _partir(comb)
	if not tecla:
		return ""
	return " ".join([*(_traducir_nombre(_NOMBRE_MODIFICADOR[m]) for m in modificadores if m in _NOMBRE_MODIFICADOR), nombre_tecla(tecla)])


# ── Mapa de serie (apartado 12.4 del informe) ────────────────────────────────

POR_DEFECTO: dict[str, dict[str, str]] = {
	acciones.JUEGO: {
		"arriba": "avanzar",
		"abajo": "retroceder",
		"izquierda": "girar_izquierda",
		"derecha": "girar_derecha",
		"mayus+izquierda": "paso_izquierda",
		"mayus+derecha": "paso_derecha",
		"u": "media_vuelta",
		"intro": "interactuar",
		"intro_numerico": "interactuar",
		"espacio": "interactuar",
		"c": "donde_estoy",
		"w": "mirar_delante",
		"a": "mirar_izquierda",
		"s": "mirar_detras",
		"d": "mirar_derecha",
		"q": "alrededor",
		"tabulador": "cercano_siguiente",
		"mayus+tabulador": "cercano_anterior",
		"l": "descubiertos",
		"k": "brujula",
		"b": "sonda",
		"e": "eco",
		"o": "objetivo",
		"p": "pista",
		"m": "confirmar",
		"f2": "repetir",
		"f3": "historial_anterior",
		"mayus+f3": "historial_siguiente",
		"repag": "historial_anterior",
		"avpag": "historial_siguiente",
		"control_izquierdo": "callar",
		"control_derecho": "callar",
		"inicio": "volver_inicio",
		"f1": "ayuda",
		"escape": "pausa",
	},
	acciones.MENU: {
		"arriba": "menu_arriba",
		"abajo": "menu_abajo",
		"izquierda": "menu_izquierda",
		"derecha": "menu_derecha",
		"intro": "menu_aceptar",
		"intro_numerico": "menu_aceptar",
		"espacio": "menu_aceptar",
		"escape": "menu_atras",
		"retroceso": "menu_atras",
		"f1": "ayuda",
		"f2": "repetir",
		"f3": "historial_anterior",
		"mayus+f3": "historial_siguiente",
		"repag": "historial_anterior",
		"avpag": "historial_siguiente",
		"control_izquierdo": "callar",
		"control_derecho": "callar",
	},
}


@dataclass(frozen=True)
class Cambio:
	"""Resultado de intentar reasignar una acción.

	``desplazada`` es la acción que estaba en la tecla elegida y que ha pasado
	a la tecla antigua; ``frase`` es lo que se le puede decir al usuario.
	"""

	hecho: bool
	frase: str
	combinacion: str = ""
	desplazada: str | None = None


class MapaTeclado:
	"""Qué acción hace cada combinación de teclas, por contexto."""

	def __init__(self, datos: dict | None = None) -> None:
		self._mapa: dict[str, dict[str, str]] = {c: dict(m) for c, m in POR_DEFECTO.items()}
		if datos:
			self._cargar(datos)

	# ── Cargar y guardar ──

	@classmethod
	def de_dict(cls, datos: dict | None) -> MapaTeclado:
		"""Crea el mapa desde lo guardado; tolera claves que faltan, sobran o están mal."""
		return cls(datos)

	def a_dict(self) -> dict[str, dict[str, str]]:
		"""El mapa completo, listo para guardar como JSON."""
		return {c: dict(m) for c, m in self._mapa.items()}

	def _cargar(self, datos: dict) -> None:
		"""Aplica lo guardado sobre el mapa de serie, descartando lo que no valga.

		Después se completan las acciones que el fichero no traía (una versión
		nueva del programa puede añadir acciones) y se reponen las teclas
		fijas, para que un fichero tocado a mano no deje al alumno sin Escape
		o sin ayuda.
		"""
		for contexto in acciones.CONTEXTOS:
			guardado = datos.get(contexto) if isinstance(datos, dict) else None
			if not isinstance(guardado, dict):
				continue
			nuevo: dict[str, str] = {}
			for comb, accion in guardado.items():
				canonica = normalizar(str(comb))
				if canonica is None or es_fija(canonica):
					if canonica is None:
						log.warning("Mapa de teclado: se descarta la tecla desconocida %s.", comb)
					continue
				if not acciones.vale_en(str(accion), contexto):
					log.warning("Mapa de teclado: se descarta la acción desconocida %s (%s).", accion, contexto)
					continue
				nuevo[canonica] = str(accion)
			for comb, accion in POR_DEFECTO[contexto].items():
				if es_fija(comb):
					nuevo[comb] = accion
				elif comb not in nuevo and accion not in nuevo.values():
					nuevo[comb] = accion
			self._mapa[contexto] = nuevo

	def restablecer(self, contexto: str | None = None) -> None:
		"""Vuelve al mapa de serie, en un contexto o en todos."""
		for c in acciones.CONTEXTOS:
			if contexto is None or contexto == c:
				self._mapa[c] = dict(POR_DEFECTO[c])

	# ── Consultar ──

	def accion_de(self, contexto: str, comb: str) -> str | None:
		"""La acción de una combinación; None si no tiene."""
		return self._mapa.get(contexto, {}).get(comb)

	def buscar(self, contexto: str, codigo: int, mod: int = 0) -> str | None:
		"""La acción de una pulsación real.

		Si la combinación exacta no tiene acción se prueba la tecla sola: con
		Mayúsculas pulsada por descuido, la flecha arriba sigue andando.
		"""
		mapa = self._mapa.get(contexto, {})
		exacta = mapa.get(combinacion(codigo, mod))
		if exacta is not None:
			return exacta
		return mapa.get(id_tecla(codigo))

	def combinaciones_de(self, contexto: str, accion: str) -> list[str]:
		"""Las combinaciones que hacen una acción, en el orden del mapa."""
		return [c for c, a in self._mapa.get(contexto, {}).items() if a == accion]

	def nombre_de(self, contexto: str, accion: str) -> str:
		"""Nombre hablado de la tecla principal de una acción; cadena vacía si no tiene."""
		combinaciones = self.combinaciones_de(contexto, accion)
		return nombre_combinacion(combinaciones[0]) if combinaciones else ""

	def reasignables(self, contexto: str) -> list[tuple[str, str]]:
		"""(acción, combinación) de todo lo que se puede cambiar en un contexto, para la pantalla de teclas."""
		return [(a, c) for c, a in self._mapa.get(contexto, {}).items() if not es_fija(c)]

	# ── Reasignar ──

	def cambiar(self, contexto: str, accion: str, nueva: str, vieja: str | None = None) -> Cambio:
		"""Pone ``accion`` en la combinación ``nueva`` e intercambia lo que hubiera allí.

		``vieja`` es la combinación que se sustituye; si no se da, la primera
		no fija de la acción. La acción que estaba en ``nueva`` pasa a
		``vieja``: ninguna se queda sin tecla.
		"""
		mapa = self._mapa.get(contexto)
		if mapa is None or not acciones.vale_en(accion, contexto):
			return Cambio(False, _("Esa acción no se puede asignar aquí."))
		destino = normalizar(nueva)
		if destino is None:
			return Cambio(False, _("No reconozco esa tecla."))
		if es_fija(destino):
			return Cambio(False, _("{tecla} no se puede usar: está reservada.").format(tecla=nombre_combinacion(destino)))
		if vieja is None:
			origen = next((c for c in self.combinaciones_de(contexto, accion) if not es_fija(c)), None)
		else:
			origen = normalizar(vieja)
			if origen is None or es_fija(origen) or mapa.get(origen) != accion:
				return Cambio(False, _("Esa tecla no se puede cambiar."))
		if origen is None and any(es_fija(c) for c in self.combinaciones_de(contexto, accion)):
			return Cambio(False, _("{accion} tiene una tecla fija que no se puede cambiar.").format(accion=acciones.nombre_accion(accion)))
		ocupante = mapa.get(destino)
		if ocupante == accion:
			return Cambio(
				True,
				_("{accion} ya está en {tecla}.").format(accion=acciones.nombre_accion(accion), tecla=nombre_combinacion(destino)),
				destino,
			)
		# Se reconstruye el diccionario para que la acción conserve su sitio en el orden.
		nuevo: dict[str, str] = {}
		for comb, a in mapa.items():
			if comb == origen:
				nuevo[destino] = accion
				if ocupante is not None:
					nuevo[origen] = ocupante
			elif comb != destino:
				nuevo[comb] = a
		if origen is None:
			nuevo[destino] = accion
		self._mapa[contexto] = nuevo
		frase = _("{accion}, ahora con {tecla}.").format(accion=acciones.nombre_accion(accion), tecla=nombre_combinacion(destino))
		if ocupante is not None and origen is not None:
			frase += " " + _("{accion} pasa a {tecla}.").format(accion=acciones.nombre_accion(ocupante), tecla=nombre_combinacion(origen))
		elif ocupante is not None:
			# Solo pasa con un mapa tocado a mano en el que la acción no tenía tecla: no hay con qué intercambiar.
			frase += " " + _("{accion} se queda sin tecla.").format(accion=acciones.nombre_accion(ocupante))
		return Cambio(True, frase, destino, ocupante)

	def cambios(self) -> list[str]:
		"""Frases con lo cambiado respecto al mapa de serie, para la ayuda."""
		frases: list[str] = []
		for contexto in acciones.CONTEXTOS:
			serie = POR_DEFECTO[contexto]
			for comb, accion in self._mapa[contexto].items():
				if serie.get(comb) == accion:
					continue
				antes = [c for c, a in serie.items() if a == accion and self._mapa[contexto].get(c) != accion]
				if antes:
					frases.append(
						_("{accion}: antes {antes}, ahora {ahora}.").format(
							accion=acciones.nombre_accion(accion),
							antes=nombre_combinacion(antes[0]),
							ahora=nombre_combinacion(comb),
						)
					)
				else:
					frases.append(
						_("{accion}: ahora también {ahora}.").format(accion=acciones.nombre_accion(accion), ahora=nombre_combinacion(comb))
					)
		return frases


class Teclado:
	"""Traduce los eventos de teclado de pygame a acciones.

	Recuerda qué acción lanzó cada tecla al pulsarse, para soltar esa misma
	acción aunque entre medias se haya soltado Mayúsculas o haya cambiado el
	contexto (se abre un menú con la flecha aún pulsada).
	"""

	def __init__(self, mapa: MapaTeclado | dict | None = None) -> None:
		self.mapa = mapa if isinstance(mapa, MapaTeclado) else MapaTeclado(mapa)
		self._pulsadas: dict[int, str] = {}

	def traducir(self, evento: pygame.event.Event, contexto: str = acciones.JUEGO) -> list[tuple[str, bool]]:
		"""(acción, pulsada) de un evento de teclado; lista vacía si no es de teclado o no tiene acción."""
		if evento.type == pygame.KEYDOWN:
			mod = int(getattr(evento, "mod", 0))
			if mod & pygame.KMOD_ALT and evento.key not in _TECLAS_ALT:
				return []  # Alt con otra tecla es del sistema (Alt+F4, Alt+Tabulador)
			accion = self.mapa.buscar(contexto, evento.key, mod)
			if accion is None:
				return []
			salida: list[tuple[str, bool]] = []
			anterior = self._pulsadas.get(evento.key)
			if anterior is not None and anterior != accion:
				salida.append((anterior, False))
			self._pulsadas[evento.key] = accion
			salida.append((accion, True))
			return salida
		if evento.type == pygame.KEYUP:
			accion = self._pulsadas.pop(evento.key, None)
			return [(accion, False)] if accion is not None else []
		return []

	def soltar_todo(self) -> list[tuple[str, bool]]:
		"""Suelta lo que estuviera pulsado (la ventana pierde el foco, se abre un menú)."""
		salida = [(accion, False) for accion in self._pulsadas.values()]
		self._pulsadas.clear()
		return salida


# ── Pantalla lógica de captura ───────────────────────────────────────────────

ESPERANDO = "esperando"
ASIGNADA = "asignada"
RECHAZADA = "rechazada"
CANCELADA = "cancelada"


@dataclass(frozen=True)
class ResultadoCaptura:
	"""Lo que ha pasado con una pulsación durante la captura, y qué decir."""

	estado: str
	frase: str
	combinacion: str = ""
	desplazada: str | None = None


class CapturaTecla:
	"""Espera la tecla que el usuario quiere usar para una acción. Escape cancela.

	Es solo la lógica: no dibuja ni habla. El reproductor le pasa los eventos
	de teclado y dice la ``frase`` de cada resultado; cuando ``terminada`` es
	cierto, cierra la pantalla y guarda ``mapa.a_dict()``.
	"""

	def __init__(self, mapa: MapaTeclado, contexto: str, accion: str, vieja: str | None = None) -> None:
		self.mapa = mapa
		self.contexto = contexto
		self.accion = accion
		self.vieja = vieja
		self.terminada = False
		self.resultado: ResultadoCaptura | None = None
		self._control_pendiente: int | None = None

	def al_entrar(self) -> str:
		"""Frase con la que se abre la pantalla."""
		return _("{accion}. Pulsa la tecla que quieres usar. Escape cancela.").format(accion=acciones.nombre_accion(self.accion))

	def evento(self, evento: pygame.event.Event) -> ResultadoCaptura | None:
		"""Procesa un evento; None si no cambia nada (no es de teclado, o es un modificador a medias)."""
		if self.terminada:
			return None
		if evento.type == pygame.KEYDOWN:
			tecla = evento.key
			if tecla == pygame.K_ESCAPE:
				return self._terminar(ResultadoCaptura(CANCELADA, _("Cancelado.")))
			if tecla in _TECLAS_CTRL:
				# Control puede ser la tecla elegida o el principio de «Control más otra»: se decide al soltarla.
				self._control_pendiente = tecla
				return None
			if tecla in _TECLAS_MAYUS:
				return None  # solo vale como modificador: se espera a la tecla que la acompaña
			self._control_pendiente = None
			return self._probar(combinacion(tecla, int(getattr(evento, "mod", 0))))
		if evento.type == pygame.KEYUP and evento.key == self._control_pendiente:
			self._control_pendiente = None
			return self._probar(id_tecla(evento.key))
		return None

	def _probar(self, comb: str) -> ResultadoCaptura:
		if es_fija(comb):
			frase = _("{tecla} no se puede usar: está reservada. Pulsa otra, o Escape para cancelar.").format(
				tecla=nombre_combinacion(comb)
			)
			self.resultado = ResultadoCaptura(RECHAZADA, frase, comb)
			return self.resultado
		cambio = self.mapa.cambiar(self.contexto, self.accion, comb, self.vieja)
		if not cambio.hecho:
			self.resultado = ResultadoCaptura(RECHAZADA, cambio.frase, comb)
			return self.resultado
		return self._terminar(ResultadoCaptura(ASIGNADA, cambio.frase, cambio.combinacion, cambio.desplazada))

	def _terminar(self, resultado: ResultadoCaptura) -> ResultadoCaptura:
		self.terminada = True
		self.resultado = resultado
		return resultado
