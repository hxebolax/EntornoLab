"""Presupuesto de tiempo del hilo de la interfaz del Estudio con un barrio de 3.000 espacios.

Por qué existe: el profesional importó un barrio de OpenStreetMap (350
espacios) y cada clic en el árbol dejaba el Estudio colgado diez segundos: el
lector de pantalla se quedaba mudo y Windows marcaba la ventana como «No
responde». Esta prueba repite lo que hace una persona con un entorno diez
veces mayor (3.000 espacios, más de 1.400 objetos reales del catálogo) y falla
si alguna acción tiene ocupado el hilo de la interfaz más de lo permitido.

Límites (medidos en la máquina de desarrollo, con margen para un equipo más
lento o cargado por otras pruebas):

- NAVEGAR (elegir en el árbol cualquier tipo de nodo, desplegar un espacio,
  elegir en la lista, ver las propiedades, pinchar en el plano, repintar
  la selección): 100 ms, que es la regla del Estudio. Medido: 3 a 65 ms.
- EDITAR (mover un elemento, deshacer, rehacer, aplicar una propiedad):
  500 ms. Medido: 100 a 260 ms. Cada edición guarda una copia del entorno
  entero para poder deshacer y pone al día un árbol de diez mil nodos; bajar
  de 100 ms con 3.000 espacios exigiría un historial por diferencias.
- ABRIR el entorno (crear el árbol): 1,5 s. Medido: 0,5 s.
- La primera vez que se ven las propiedades de cada tipo de elemento se
  crean sus controles (unos 7 ms cada lista desplegable de Windows, el
  doble o el triple con un lector de pantalla abierto, que escucha cada
  control nuevo); esa primera vez se mide aparte con 400 ms (medido: de 100
  a 260 ms con NVDA en marcha) y las siguientes con el límite de navegar.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import pytest

from app.dominio.catalogo import Catalogo
from app.ui import operaciones
from tests import _entornos_grandes as eg

from ._ui_estudio_util import cerrar_ventana, crear_ventana

# Mide tiempos: se ejecuta sola (pytest -m rendimiento), no con la batería normal,
# porque con el equipo ocupado por otras pruebas los tiempos no significan nada.
pytestmark = [pytest.mark.lento, pytest.mark.rendimiento]

LIMITE_NAVEGAR_S = 0.100
LIMITE_PRIMERA_VEZ_S = 0.400
LIMITE_EDITAR_S = 0.500
LIMITE_ABRIR_S = 1.5
PLUGINS = Path(__file__).resolve().parent.parent / "data" / "plugins"


class Cronometro:
	"""Apunta cuánto tarda cada acción y cuáles se pasan de su límite."""

	def __init__(self) -> None:
		self.medidas: list[tuple[str, float, float]] = []

	def medir(
		self, nombre: str, limite: float, accion: Callable[[], object], veces: int = 1, preparar: Callable[[], object] | None = None
	) -> None:
		"""Hace la acción ``veces`` veces y se queda con la vez más rápida.

		La más rápida es la que mide el coste propio de la acción: las demás
		incluyen lo que el sistema haya hecho a la vez (otras pruebas, el
		lector de pantalla atendiendo los controles nuevos, el antivirus).
		"""
		mejor = float("inf")
		for _vez in range(max(1, veces)):
			if preparar is not None:
				# Lo que deja la ventana como antes de la acción (otra fila elegida): no se cronometra.
				preparar()
			inicio = time.perf_counter()
			accion()
			mejor = min(mejor, time.perf_counter() - inicio)
		self.medidas.append((nombre, mejor, limite))

	def excesos(self) -> list[str]:
		return [
			f"{nombre}: {duracion * 1000:.0f} ms (límite {limite * 1000:.0f} ms)"
			for nombre, duracion, limite in self.medidas
			if duracion > limite
		]


@pytest.fixture(scope="module")
def catalogo() -> Catalogo:
	return Catalogo.cargar([PLUGINS])


def test_estudio_con_3000_espacios_no_bloquea(app_wx, monkeypatch, catalogo: Catalogo) -> None:
	entorno = eg.barrio(3000)
	eg.amueblar(entorno, catalogo, 800)
	ventana = crear_ventana(monkeypatch, catalogo=catalogo)
	ventana.confirmar_descartar = lambda: True
	contexto = ventana.contexto
	reloj = Cronometro()
	try:
		reloj.medir("abrir el entorno", LIMITE_ABRIR_S, lambda: ventana.adoptar_borrador(entorno))
		planta = contexto.entorno.plantas[0]
		arbol = ventana._arbol_logico
		assert arbol is not None

		def elegir(clave: str) -> None:
			item = ventana._asegurar_item(clave)
			assert item is not None, clave
			ventana.arbol.SelectItem(item)

		tipos = {}
		for espacio in planta.espacios:
			tipos.setdefault(espacio.tipo, espacio)
		con_hijos = [nodo for nodo in arbol.buscar(planta.id).hijos if nodo.hijos and "/" not in nodo.clave][:15]
		hijos = [nodo.hijos[0].clave for nodo in con_hijos]
		grupos = [nodo.clave for nodo in arbol.buscar(planta.id).hijos if nodo.clave.startswith(operaciones.PREFIJO_GRUPO)]
		# Primera visita de cada tipo de nodo: se crean los controles de sus propiedades.
		for espacio in tipos.values():
			reloj.medir(f"primera vez: espacio {espacio.tipo}", LIMITE_PRIMERA_VEZ_S, lambda e=espacio: elegir(e.id))
		for clave in hijos[:3] + grupos:
			reloj.medir(f"primera vez: {clave}", LIMITE_PRIMERA_VEZ_S, lambda c=clave: elegir(c))
		reloj.medir("primera vez: planta", LIMITE_PRIMERA_VEZ_S, lambda: elegir(planta.id))
		reloj.medir("primera vez: entorno", LIMITE_PRIMERA_VEZ_S, lambda: elegir(operaciones.CLAVE_ENTORNO))
		# Recorrer el árbol como con las flechas: espacios de todos los tipos, sus hijos, grupos, planta y entorno.
		for vuelta in range(2):
			for espacio in [*tipos.values(), *planta.espacios[100:130]]:
				reloj.medir(f"árbol: espacio {espacio.id} ({vuelta})", LIMITE_NAVEGAR_S, lambda e=espacio: elegir(e.id))
			for nodo in con_hijos:
				reloj.medir(
					f"árbol: desplegar {nodo.clave}",
					LIMITE_NAVEGAR_S,
					lambda c=nodo.clave: (
						ventana.arbol.Collapse(ventana._asegurar_item(c)),
						ventana.arbol.Expand(ventana._asegurar_item(c)),
					),
					veces=3,
				)
			for clave in hijos + grupos:
				reloj.medir(f"árbol: {clave} ({vuelta})", LIMITE_NAVEGAR_S, lambda c=clave: elegir(c))
			reloj.medir(f"árbol: planta ({vuelta})", LIMITE_NAVEGAR_S, lambda: elegir(planta.id))
			reloj.medir(f"árbol: entorno ({vuelta})", LIMITE_NAVEGAR_S, lambda: elegir(operaciones.CLAVE_ENTORNO))
		# La lista de la planta tiene miles de filas: elegir una (como con las flechas) y ver sus propiedades.
		elegir(planta.id)
		assert len(ventana._ids) > 9000
		ids_planta = list(ventana._ids)

		def elegir_fila(fila: int) -> None:
			# Como ``_al_elegir_en_lista``: la selección viene de la lista y la lista no se rehace.
			ventana._origen_seleccion = "lista"
			contexto.seleccionar(ids_planta[fila])

		filas = (0, 10, 2500, 6000, len(ids_planta) - 1)
		# La primera vez, cada tipo de elemento crea los controles de sus propiedades.
		for fila in filas:
			reloj.medir(f"primera vez: lista fila {fila}", LIMITE_PRIMERA_VEZ_S, lambda f=fila: elegir_fila(f))
		for fila in reversed(filas):
			reloj.medir(
				f"lista: fila {fila}",
				LIMITE_NAVEGAR_S,
				lambda f=fila: elegir_fila(f),
				veces=3,
				preparar=lambda f=fila: elegir_fila(0 if f else 10),
			)
		assert ventana._ids == ids_planta, "elegir en la lista no la rehace"
		assert ventana.lista.texto_celda(len(ids_planta) - 1, 0), "las filas se componen al pedirlas"
		# Plano: pintar una vez (con la vista de conjunto simplificada) y luego solo la selección encima.
		import wx

		mapa = wx.Bitmap(1000, 700)

		def pintar() -> None:
			dc = wx.MemoryDC(mapa)
			ventana.plano.pintar(dc, 1000, 700)
			dc.SelectObject(wx.NullBitmap)

		pintar()
		reloj.medir("plano: repintar la selección", LIMITE_NAVEGAR_S, pintar, veces=3)
		reloj.medir("plano: pinchar", LIMITE_NAVEGAR_S, lambda: ventana.plano.elemento_en_pixel(500, 350), veces=3)
		reloj.medir("plano: volver a pintar tras acercar", LIMITE_EDITAR_S, lambda: (ventana.plano.acercar(), pintar()))
		# Editar.
		objeto = planta.objetos[0]
		espacio = tipos.get("acera") or planta.espacios[10]
		reloj.medir("mover un objeto", LIMITE_EDITAR_S, lambda: ventana.plano.mover_elemento(objeto.id, 0.5, 0.0), veces=3)
		reloj.medir("mover un espacio", LIMITE_EDITAR_S, lambda: ventana.plano.mover_elemento(espacio.id, 0.5, 0.0), veces=3)
		reloj.medir("deshacer", LIMITE_EDITAR_S, contexto.deshacer, veces=3)
		reloj.medir("rehacer", LIMITE_EDITAR_S, contexto.rehacer, veces=3)
		from app.ui import dialogos_insertar

		reloj.medir(
			"aplicar una propiedad",
			LIMITE_EDITAR_S,
			lambda: dialogos_insertar.aplicar_propiedades(contexto, objeto.id, {"nombre": "Mesa nueva"}),
		)
		reloj.medir("árbol tras editar", LIMITE_NAVEGAR_S, lambda: elegir(espacio.id))
		# La página «Descripción» se compone en segundo plano: cambiar a ella no espera.
		reloj.medir("pestaña Descripción", LIMITE_NAVEGAR_S, lambda: (ventana.cuaderno.SetSelection(1), ventana._actualizar_descripcion()))
		ventana.cuaderno.SetSelection(0)
	finally:
		cerrar_ventana(ventana)
	excesos = reloj.excesos()
	assert not excesos, "Acciones que bloquean la interfaz más de lo permitido:\n" + "\n".join(excesos)
