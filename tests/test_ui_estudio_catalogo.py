"""Pruebas de «Insertar objeto»: catálogo, búsqueda, miniatura y colocación a escala."""

from __future__ import annotations

import pytest
import wx

from app.core.config import Configuracion
from app.dominio import edicion as ed
from app.ui import dialogo_catalogo as dc
from app.ui.accesibilidad.revision_teclado import afirmar_teclado_correcto
from app.ui.contexto import ContextoEstudio
from app.ui.formulario import DialogoFormulario
from tests.test_dominio_comun import catalogo_de_prueba, piso_minimo


@pytest.fixture
def catalogo(tmp_path):
	return catalogo_de_prueba(tmp_path)


@pytest.fixture
def contexto(catalogo):
	"""Contexto sin ventana con el piso mínimo abierto (salón de 5 × 4 y cocina de 3 × 4)."""
	ctx = ContextoEstudio(None, Configuracion(), catalogo)
	entorno, _planta, _salon, _cocina = piso_minimo()
	ctx.abrir_documento(entorno)
	return ctx


def _planta(contexto):
	return contexto.entorno.plantas[0]


def _espacio(contexto, nombre):
	return next(e for e in _planta(contexto).espacios if e.nombre == nombre)


def _elegir(tipo, variante=None):
	return lambda d: (d.elegir(tipo, variante), wx.ID_OK)[1]


def _rellenar(**valores):
	return lambda d: (d.fijar(valores), wx.ID_OK)[1]


# ── Diálogo del catálogo ─────────────────────────────────────────────────────


def _etiqueta_de(control):
	hermanos = list(control.GetParent().GetChildren())
	return hermanos[hermanos.index(control) - 1]


def _textos_arbol(dialogo):
	"""Textos de todos los nodos del árbol, en orden, con su profundidad."""
	arbol = dialogo.arbol
	salida = []

	def recorrer(elemento, nivel):
		hijo, galleta = arbol.GetFirstChild(elemento)
		while hijo.IsOk():
			salida.append((nivel, arbol.GetItemText(hijo)))
			recorrer(hijo, nivel + 1)
			hijo, galleta = arbol.GetNextChild(elemento, galleta)

	recorrer(arbol.GetRootItem(), 0)
	return salida


def _clasificar(catalogo):
	"""Pone en algunas fichas los campos nuevos de clasificación, como hará el dominio."""
	datos = {
		"prueba/cama": ("camas", ["vivienda"], ["dormitorio"], "descanso", "bajo", "comun"),
		"prueba/mesilla": ("mesillas", ["vivienda"], ["dormitorio"], "almacenaje", "bajo", "ocasional"),
		"prueba/sofa": ("asientos", ["vivienda", "oficina"], ["salon"], "descanso", "bajo", "comun"),
		"prueba/silla": ("asientos", ["vivienda", "colegio"], ["salon", "cocina"], "descanso", "prueba_movil", "muy_comun"),
		"prueba/lampara": ("iluminacion", ["vivienda"], ["salon"], "iluminacion", "cabeza", "ocasional"),
	}
	for tipo, (sub, lugares, estancias, funcion, obstaculo, frecuencia) in datos.items():
		definicion = catalogo.objeto(tipo)
		definicion.subcategoria, definicion.lugares, definicion.estancias = sub, lugares, estancias
		definicion.funcion, definicion.obstaculo, definicion.frecuencia = funcion, obstaculo, frecuencia
	return catalogo


NUEVOS = ("arbol", "facetas", "relacionados", "buscar_avanzado", "nombre_de", "nombre_subcategoria", "subcategorias")


class CatalogoDoble:
	"""Un catálogo que delega en el real pero SIN los métodos nuevos del dominio, salvo los que se le den.

	Es el catálogo «de antes»: con él se prueba que el diálogo se las arregla
	solo con ``complementos()``, ``categorias()`` y las fichas.
	"""

	def __init__(self, real, arbol=None, relacionados=None, facetas=None):
		self._real = real
		if arbol is not None:
			self.arbol = arbol
		if relacionados is not None:
			self.relacionados = relacionados
		if facetas is not None:
			self.facetas = facetas

	def __getattr__(self, nombre):
		if nombre in NUEVOS:
			raise AttributeError(nombre)
		return getattr(self._real, nombre)


def test_catalogo_teclado_y_etiquetas(app_wx, catalogo):
	for cat in (catalogo, CatalogoDoble(_clasificar(catalogo), relacionados=lambda tipo: [])):
		dialogo = dc.DialogoCatalogo(None, cat)
		try:
			afirmar_teclado_correcto(dialogo, teclas_propias=["Ctrl+D"])
			assert dialogo.GetEscapeId() == wx.ID_CANCEL
			controles = [
				dialogo.arbol,
				dialogo.campo_buscar,
				dialogo.eleccion_ambito,
				dialogo.lista,
				dialogo.campo_descripcion,
				dialogo.eleccion_variante,
			]
			controles += list(dialogo.elecciones_faceta.values())
			for control in controles:
				anterior = _etiqueta_de(control)
				assert isinstance(anterior, wx.StaticText) and "&" in anterior.GetLabel(), control.GetName()
				assert control.GetHelpText()
			for boton in (dialogo.casilla_premio, dialogo.casilla_sonido, dialogo.boton_favorito):
				assert "&" in boton.GetLabel() and boton.GetHelpText()
			interactivos = [h for h in dialogo.GetChildren() if not isinstance(h, (wx.StaticText, wx.StaticBitmap))]
			assert interactivos[0] is dialogo.arbol, "la clasificación es el primer control"
			assert isinstance(dialogo.arbol, wx.TreeCtrl) and type(dialogo.arbol).__module__.startswith("wx._core")
			assert not any(isinstance(h, (wx.SearchCtrl, wx.SpinCtrlDouble)) for h in dialogo.GetChildren())
			assert not dialogo.campo_descripcion.IsEditable()
			assert dialogo.lista.GetWindowStyleFlag() & wx.LC_VIRTUAL, "lista virtual: mil filas no se crean una a una"
			assert [dialogo.lista.GetColumn(i).GetText() for i in range(4)] == ["Nombre", "Categoría", "Medidas", "Complemento"]
			assert dialogo.lista.GetItemCount() == len(catalogo.objetos())
			assert dialogo.lista.GetFocusedItem() == 0, "con filas, siempre hay una enfocada"
			assert dialogo.texto_recuento.GetLabel() == f"{len(catalogo.objetos())} objetos"
		finally:
			dialogo.Destroy()
	# Sin campos nuevos en las fichas no se crean filtros vacíos; con ellos, sí.
	assert set(dc.facetas_de(catalogo.objetos())) == set(dc.FACETAS)


def test_arbol_de_clasificacion_sin_arbol_en_el_dominio(app_wx, catalogo):
	sin = CatalogoDoble(_clasificar(catalogo))
	assert not hasattr(sin, "arbol") and dc.arbol_del_dominio(sin) is None
	dialogo = dc.DialogoCatalogo(None, sin)
	try:
		textos = _textos_arbol(dialogo)
		total = len(catalogo.objetos())
		assert textos[:3] == [(0, f"Todos ({total})"), (0, "Favoritos (0)"), (0, "Usados recientemente (0)")]
		assert (0, f"Complemento de prueba ({total})") in textos
		assert (1, "Dormitorio (3)") in textos and (1, "Salón (8)") in textos
		assert (2, "Asientos (2)") in textos and (2, "Camas (1)") in textos
		# Elegir un nodo acota la lista; los recuentos del árbol coinciden con ella.
		assert dialogo.elegir_nodo("cat", "prueba", "dormitorio") and dialogo.lista.GetItemCount() == 3
		assert dialogo.elegir_nodo("sub", "prueba", "salon", "asientos") and dialogo.lista.GetItemCount() == 2
		assert {d.tipo for d in dialogo._definiciones} == {"prueba/sofa", "prueba/silla"}
		assert dialogo.elegir_nodo("comp", "prueba") and dialogo.lista.GetItemCount() == total
		assert dialogo.elegir_nodo("comp", "no_existe") is False
		# Elegirlo con el teclado o el ratón (evento del árbol) hace lo mismo.
		dialogo.arbol.SelectItem(dialogo._nodos[("cat", "prueba", "cocina")])
		assert dialogo.lista.GetItemCount() == 2 and dialogo.texto_recuento.GetLabel() == "2 objetos"
	finally:
		dialogo.Destroy()


def test_arbol_del_dominio_si_existe(app_wx, catalogo):
	def arbol():
		return [
			{
				"id": "prueba",
				"nombre": "Complemento de prueba",
				"recuento": 21,
				"hijos": [
					{
						"id": "salon",
						"nombre": "Salón y estar",
						"recuento": 8,
						"hijos": [{"id": "asientos", "nombre": "Asientos", "recuento": 2}],
					}
				],
			}
		]

	con = CatalogoDoble(_clasificar(catalogo), arbol=arbol)
	dialogo = dc.DialogoCatalogo(None, con)
	try:
		textos = _textos_arbol(dialogo)
		assert (1, "Salón y estar (8)") in textos and (2, "Asientos (2)") in textos
		assert dialogo.elegir_nodo("sub", "prueba", "salon", "asientos") and dialogo.lista.GetItemCount() == 2
	finally:
		dialogo.Destroy()
	# Un árbol con una forma que no se entiende no rompe nada: se usa el construido de las fichas.
	raro = CatalogoDoble(catalogo, arbol=lambda: [42, "x"])
	assert dc.arbol_del_dominio(raro) is None
	dialogo = dc.DialogoCatalogo(None, raro)
	try:
		assert (1, "Dormitorio (3)") in _textos_arbol(dialogo)
	finally:
		dialogo.Destroy()


def test_catalogo_busqueda_y_filtros_combinados(app_wx, catalogo, voz_simulada):
	dialogo = dc.DialogoCatalogo(None, CatalogoDoble(_clasificar(catalogo)))
	try:
		assert set(dialogo.elecciones_faceta) == {"lugar", "estancia", "funcion", "obstaculo"}
		assert dialogo.filtrar("sofa") == 2
		assert {d.tipo for d in dialogo._definiciones} == {"prueba/sofa", "prueba/rinconera"}
		assert dialogo.filtrar("", categoria="cocina") == 2
		assert dialogo.filtrar("", categoria=dc.TODOS, ambito="exterior") == 2
		assert dialogo.filtrar("zzz no existe", ambito=dc.TODOS) == 0
		assert "No hay ningún objeto" in dialogo.campo_descripcion.GetValue()
		assert dialogo.texto_recuento.GetLabel() == "Ningún objeto" and dialogo.seleccion() is None
		assert dialogo.filtrar("", complemento="prueba") == len(catalogo.objetos())
		# Facetas nuevas, solas y combinadas entre sí, con el árbol y con el texto.
		assert dialogo.filtrar(lugar="vivienda") == 5
		assert dialogo.filtrar(funcion="descanso") == 3
		assert dialogo.filtrar(estancia="salon") == 2
		assert dialogo.filtrar(obstaculo="prueba_movil") == 1 and dialogo.definicion_actual().tipo == "prueba/silla"
		assert dialogo.filtrar(obstaculo=dc.TODOS, estancia=dc.TODOS, lugar="oficina") == 1
		assert dialogo.filtrar(lugar=dc.TODOS, funcion=dc.TODOS, contenedor=True) == 2
		assert dialogo.filtrar(contenedor=False, sonido_propio=True) == 1 and dialogo.definicion_actual().tipo == "prueba/frigorifico"
		assert dialogo.filtrar(sonido_propio=False) == len(catalogo.objetos())
		dialogo.elegir_nodo("cat", "prueba", "salon")
		assert dialogo.filtrar("s", funcion="descanso") == 2
		# Los controles reflejan lo filtrado (se puede seguir a mano desde ahí).
		eleccion = dialogo.elecciones_faceta["funcion"]
		assert eleccion.GetString(eleccion.GetSelection()) == dc.nombre_valor("funcion", "descanso") + " (3)"
		# Cambiar un control a mano filtra igual.
		dialogo.casilla_premio.SetValue(True)
		from tests.ayudas_wx import enviar_orden

		enviar_orden(dialogo.casilla_premio, wx.wxEVT_CHECKBOX)
		assert dialogo.lista.GetItemCount() == 0
	finally:
		dialogo.Destroy()


def test_recuento_anunciado_una_vez_por_filtrado(app_wx, catalogo, voz_simulada):
	contexto = ContextoEstudio(None, Configuracion(), catalogo)
	dialogo = dc.DialogoCatalogo(None, catalogo, contexto=contexto)
	try:
		assert voz_simulada.textos == [], "al abrir no se anuncia nada: el lector ya lee el diálogo"
		dialogo.filtrar("sofa")
		assert voz_simulada.textos == ["2 objetos"]
		dialogo.filtrar("frigo")
		dialogo.filtrar("zzz")
		assert voz_simulada.textos == ["2 objetos", "1 objeto", "Ningún objeto"]
	finally:
		dialogo.Destroy()
	# Sin contexto se usa la voz del proyecto.
	voz_simulada.limpiar()
	dialogo = dc.DialogoCatalogo(None, catalogo)
	try:
		dialogo.filtrar("cama")
		assert voz_simulada.textos == ["1 objeto"] and dialogo.ultimo_anuncio == "1 objeto"
	finally:
		dialogo.Destroy()


def test_orden_por_relevancia(catalogo):
	indice = dc.Indice(_clasificar(catalogo))
	# «mes»: los tres empiezan igual; manda la frecuencia (la mesilla es ocasional) y después el nombre.
	tipos = [d.tipo for d in indice.filtrar(dc.Filtros(texto="mes"))]
	assert tipos == ["prueba/mesa", "prueba/mesa_redonda", "prueba/mesilla"]
	# El principio del nombre puntúa más que otra palabra del nombre.
	catalogo.objeto("prueba/estanteria").nombre = "Redonda estantería"
	tipos = [d.tipo for d in dc.Indice(catalogo).filtrar(dc.Filtros(texto="redonda"))]
	assert tipos == ["prueba/estanteria", "prueba/mesa_redonda"]
	# Coincidencia en el nombre antes que en etiquetas o descripción.
	catalogo.objeto("prueba/armario").etiquetas.append("silla plegable guardada")
	tipos = [d.tipo for d in indice.__class__(catalogo).filtrar(dc.Filtros(texto="silla"))]
	assert tipos[0] == "prueba/silla" and tipos[-1] == "prueba/armario"
	# Sin tildes ni mayúsculas, y todas las palabras tienen que aparecer.
	assert [d.tipo for d in indice.filtrar(dc.Filtros(texto="SOFÁ rinconera"))] == ["prueba/rinconera"]
	assert indice.filtrar(dc.Filtros(texto="sofa nevera")) == []
	# A igualdad de coincidencia manda la frecuencia y después el nombre.
	descanso = [d.tipo for d in indice.filtrar(dc.Filtros(facetas={"funcion": "descanso"}))]
	assert descanso == ["prueba/silla", "prueba/cama", "prueba/sofa"]
	sin_frecuencia = [d.nombre for d in indice.filtrar(dc.Filtros(categoria="cocina"))]
	assert sin_frecuencia == sorted(sin_frecuencia)


def test_favoritos_y_recientes_persisten(app_wx, catalogo, data_temporal, voz_simulada):
	dialogo = dc.DialogoCatalogo(None, catalogo)
	try:
		afirmar_teclado_correcto(dialogo, teclas_propias=["Ctrl+D"])
		assert dialogo.elegir("prueba/cama")
		assert dialogo.boton_favorito.GetLabel() == "Marcar como fa&vorito"
		assert dialogo.alternar_favorito() is True
		assert dialogo.boton_favorito.GetLabel() == "Quitar de fa&voritos"
		afirmar_teclado_correcto(dialogo, teclas_propias=["Ctrl+D"])
		assert voz_simulada.contiene("marcado como favorito")
		assert (0, "Favoritos (1)") in _textos_arbol(dialogo)
		# Control+D hace lo mismo desde cualquier control, y las demás teclas siguen su camino.
		dialogo.elegir("prueba/silla")
		from tests.ayudas_wx import simular_tecla

		assert simular_tecla(dialogo, "d", ctrl=True).gestionado
		assert simular_tecla(dialogo, "d").saltado
		assert (0, "Favoritos (2)") in _textos_arbol(dialogo)
		assert dialogo.elegir_nodo("favoritos") and {d.tipo for d in dialogo._definiciones} == {"prueba/cama", "prueba/silla"}
		# Quitar un favorito estando en «Favoritos» lo saca de la lista.
		dialogo.elegir("prueba/cama")
		dialogo.elegir_nodo("favoritos")
		dialogo.lista.enfocar_fila([d.tipo for d in dialogo._definiciones].index("prueba/cama"), anunciar=False)
		assert dialogo.alternar_favorito() is False and [d.tipo for d in dialogo._definiciones] == ["prueba/silla"]
	finally:
		dialogo.Destroy()
	assert (data_temporal / "config" / "catalogo_uso.json").is_file()
	assert dc.leer_uso()["favoritos"] == ["prueba/silla"]
	dc.apuntar_reciente("prueba/mesa")
	dc.apuntar_reciente("prueba/sofa")
	dc.apuntar_reciente("prueba/mesa")
	assert dc.leer_uso()["recientes"] == ["prueba/mesa", "prueba/sofa"]
	# Otro diálogo (otra sesión) los encuentra, con los recientes en su orden.
	dialogo = dc.DialogoCatalogo(None, catalogo)
	try:
		textos = _textos_arbol(dialogo)
		assert (0, "Favoritos (1)") in textos and (0, "Usados recientemente (2)") in textos
		assert dialogo.elegir_nodo("recientes") and [d.tipo for d in dialogo._definiciones] == ["prueba/mesa", "prueba/sofa"]
	finally:
		dialogo.Destroy()
	# Un fichero dañado no impide abrir: se empieza de cero.
	dc.ruta_uso().write_text("{esto no es json", encoding="utf-8")
	assert dc.leer_uso() == {"favoritos": [], "recientes": []}


def test_colocar_apunta_el_objeto_como_reciente(contexto, dialogo_modal):
	datos = {"planta": _planta(contexto).id, "modo": "punto", "x": 2.5, "y": 2.0}
	assert dc.colocar_objeto(contexto, "prueba/mesa_redonda", None, datos)
	assert dc.leer_uso()["recientes"] == ["prueba/mesa_redonda"]
	# Lo que no llega a colocarse no se apunta.
	assert dc.colocar_objeto(contexto, "prueba/cama", None, {"planta": _planta(contexto).id, "modo": "punto", "x": 500, "y": 500}) is None
	assert dc.leer_uso()["recientes"] == ["prueba/mesa_redonda"]


def test_miniatura_perezosa(app_wx, catalogo, data_temporal, monkeypatch):
	generadas = []
	original = dc.complemento_propio.generar_miniatura
	monkeypatch.setattr(dc.complemento_propio, "generar_miniatura", lambda *a, **k: generadas.append(a[0].tipo) or original(*a, **k))
	dialogo = dc.DialogoCatalogo(None, catalogo)
	try:
		dialogo.filtrar("")
		dialogo.elegir("prueba/sofa")
		dialogo.elegir("prueba/mesa")
		assert generadas == [] and dialogo.miniaturas_cargadas == 0, "abrir, filtrar y recorrer no genera miniaturas"
		assert not (data_temporal / "cache" / "miniaturas").exists()
		assert not dialogo.miniatura.GetBitmap().IsOk()
		# Pasado el retardo se carga solo la de la fila enfocada.
		assert dialogo.cargar_miniatura_ahora() is True
		assert generadas == ["prueba/mesa"] and dialogo.miniaturas_cargadas == 1
		assert dialogo.miniatura.GetBitmap().IsOk()
		assert dialogo.cargar_miniatura_ahora() is True and dialogo.miniaturas_cargadas == 1, "no se recarga la que ya está"
		# La caché en disco evita generarla otra vez.
		dialogo.elegir("prueba/sofa")
		dialogo.elegir("prueba/mesa")
		dialogo.cargar_miniatura_ahora()
		assert generadas == ["prueba/mesa"]
	finally:
		dialogo.Destroy()


def test_miniatura_llega_sola_tras_el_retardo(app_wx, catalogo, ayudas_wx, monkeypatch):
	monkeypatch.setattr(dc, "RETARDO_MINIATURA_MS", 20)
	dialogo = dc.DialogoCatalogo(None, catalogo)
	try:
		dialogo.elegir("prueba/cama")
		ayudas_wx.esperar_hasta(lambda: dialogo.miniaturas_cargadas == 1, 3.0, "la miniatura no se cargó con el temporizador")
		assert dialogo.miniatura.GetBitmap().IsOk()
	finally:
		dialogo.Destroy()


def test_objetos_relacionados(app_wx, catalogo, voz_simulada):
	sin = dc.DialogoCatalogo(None, CatalogoDoble(catalogo))
	try:
		assert sin.boton_relacionados is None and sin.mostrar_relacionados() == 0
	finally:
		sin.Destroy()
	# Sin método en el catálogo pero con la lista en la ficha, se usa la ficha.
	catalogo.objeto("prueba/mesa").relacionados = ["silla", "prueba/alfombra", "no_existe"]
	de_ficha = dc.DialogoCatalogo(None, CatalogoDoble(catalogo))
	try:
		de_ficha.elegir("prueba/mesa")
		assert de_ficha.boton_relacionados is not None and de_ficha.mostrar_relacionados() == 2
		assert {d.tipo for d in de_ficha._definiciones} == {"prueba/silla", "prueba/alfombra"}
	finally:
		de_ficha.Destroy()
	catalogo.objeto("prueba/mesa").relacionados = []
	relacion = {"prueba/cama": [catalogo.objeto("prueba/mesilla"), "prueba/armario"]}
	dialogo = dc.DialogoCatalogo(None, CatalogoDoble(catalogo, relacionados=lambda tipo: relacion.get(tipo, [])))
	try:
		afirmar_teclado_correcto(dialogo, teclas_propias=["Ctrl+D"])
		assert "&" in dialogo.boton_relacionados.GetLabel()
		dialogo.elegir("prueba/cama")
		assert dialogo.mostrar_relacionados() == 2
		assert {d.tipo for d in dialogo._definiciones} == {"prueba/mesilla", "prueba/armario"}
		assert voz_simulada.contiene("Relacionados con «Cama»: 2 objetos")
		# Sin relacionados lo dice y la lista no cambia.
		assert dialogo.mostrar_relacionados() == 0 and dialogo.lista.GetItemCount() == 2
		# Elegir otro nodo de la clasificación vuelve a enseñar todo.
		assert dialogo.elegir_nodo("todos") and dialogo.lista.GetItemCount() == len(catalogo.objetos())
	finally:
		dialogo.Destroy()


def _catalogo_grande(complementos=20, por_complemento=75, sin_dominio=True):
	"""Catálogo sintético en memoria: 20 complementos, 1.500 objetos, con clasificación."""
	from app.dominio.catalogo import Catalogo, Complemento, DefObjeto

	grande = Catalogo()
	palabras = ["mesa", "silla", "armario", "banco", "farola", "papelera", "estante", "vitrina", "mostrador", "cajón"]
	for c in range(complementos):
		objetos = []
		for o in range(por_complemento):
			definicion = DefObjeto(
				id=f"obj{o}",
				complemento=f"comp{c}",
				nombre=f"{palabras[o % 10].capitalize()} modelo {c}-{o}",
				categoria=f"cat{o % 5}",
				etiquetas=[palabras[(o + 3) % 10]],
				descripcion=f"Objeto sintético número {o} del complemento {c}.",
				ambito=["interior"] if o % 2 else ["exterior"],
				contenedor=o % 7 == 0,
			)
			definicion.subcategoria = f"sub{o % 3}"
			definicion.lugares = [f"lugar{o % 4}"]
			definicion.frecuencia = ("ocasional", "comun", "muy_comun")[o % 3]
			objetos.append(definicion)
		grande.anadir(
			Complemento(
				id=f"comp{c}",
				nombre=f"Complemento {c:02d}",
				version="1.0",
				objetos=objetos,
				categorias={f"cat{i}": f"Categoría {i}" for i in range(5)},
			)
		)
	return CatalogoDoble(grande) if sin_dominio else grande


def test_catalogo_de_1500_objetos_abre_y_filtra_rapido(app_wx, data_temporal):
	import time

	grande = _catalogo_grande()
	assert len(grande.objetos()) == 1500
	inicio = time.perf_counter()
	dialogo = dc.DialogoCatalogo(None, grande)
	abrir = time.perf_counter() - inicio
	try:
		assert dialogo.lista.GetItemCount() == 1500 and dialogo.miniaturas_cargadas == 0
		assert not (data_temporal / "cache" / "miniaturas").exists(), "abrir no genera ninguna miniatura"
		# 3 nodos especiales + 20 complementos × (1 + 5 categorías × (1 + 3 subcategorías)).
		assert len(_textos_arbol(dialogo)) == 3 + 20 * (1 + 5 * 4)
		assert (0, "Complemento 07 (75)") in _textos_arbol(dialogo) and (1, "Categoría 2 (15)") in _textos_arbol(dialogo)
		inicio = time.perf_counter()
		assert dialogo.filtrar("mesa") == 300
		n = dialogo.filtrar("mesa modelo 3-")
		assert 0 < n < 300 and dialogo.definicion_actual().nombre.startswith("Mesa modelo 3-"), "lo que empieza por lo buscado, primero"
		esperados = sum(1 for d in grande.objetos() if "exterior" in d.ambito and "lugar2" in d.lugares and d.contenedor)
		assert esperados > 0 and dialogo.filtrar("", ambito="exterior", lugar="lugar2", contenedor=True) == esperados
		assert dialogo.filtrar(ambito=dc.TODOS, lugar=dc.TODOS, contenedor=False, complemento=dc.TODOS) == 1500
		assert dialogo.elegir_nodo("sub", "comp4", "cat1", "sub0") and dialogo.lista.GetItemCount() == 5
		assert dialogo.elegir_nodo("todos") and dialogo.lista.GetItemCount() == 1500
		filtrar = time.perf_counter() - inicio
		# La lista virtual guarda el texto íntegro de cualquier fila sin haberla pintado.
		assert dialogo.lista.valores_fila(1499)[0].startswith(
			("Mesa", "Silla", "Armario", "Banco", "Farola", "Papelera", "Estante", "Vitrina", "Mostrador", "Cajón")
		)
	finally:
		dialogo.Destroy()
	assert abrir < 5.0, f"abrir tardó {abrir:.2f} s"
	assert filtrar < 5.0, f"cinco filtrados tardaron {filtrar:.2f} s"


def test_catalogo_detalle_y_variantes(app_wx, catalogo, dialogo_modal):
	dialogo = dc.DialogoCatalogo(None, _clasificar(catalogo))
	try:
		assert dialogo.elegir("prueba/cama", "individual")
		texto = dialogo.campo_descripcion.GetValue()
		assert "Ancho: 1,5 metros (de 0,8 a 2)" in texto
		assert "Variantes:" in texto and "Individual" in texto
		assert "Corta el paso" in texto and "contra una pared" in texto
		assert "Clasificación: Dormitorio, camas." in texto
		assert "Estancias: " + dc.nombre_valor("estancia", "dormitorio").lower() + "." in texto
		assert "Función: " + dc.nombre_valor("funcion", "descanso").lower() + "." in texto
		assert dialogo.eleccion_variante.GetCount() == 3
		assert dialogo.seleccion() == ("prueba/cama", "individual")
		assert dialogo.aceptar() and dialogo.resultado == ("prueba/cama", "individual")
		dialogo.filtrar("zzz")
		assert dialogo.aceptar() is False and "Elija un objeto" in dialogo.ultimo_error
		# «elegir» encuentra el objeto aunque los filtros lo escondan.
		dialogo.filtrar("zzz", funcion="descanso", contenedor=True)
		assert dialogo.elegir("prueba/frigorifico") and dialogo.definicion_actual().tipo == "prueba/frigorifico"
	finally:
		dialogo.Destroy()


def test_miniatura_y_textos_sin_ventanas(catalogo, data_temporal):
	cama = catalogo.objeto("prueba/cama")
	assert dc.texto_medidas(cama) == "1,5 × 2 × 0,5 m"
	assert dc.fila_de(catalogo, cama) == ("Cama", "Dormitorio", "1,5 × 2 × 0,5 m", "Complemento de prueba")
	ruta = dc.ruta_miniatura(catalogo, cama)
	assert ruta is not None and ruta.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
	assert data_temporal in ruta.parents


def test_elegir_objeto_sin_colocar(contexto, dialogo_modal):
	dialogo_modal.responder(_elegir("prueba/mesa"))
	assert dc.elegir_objeto(contexto) == ("prueba/mesa", None)
	dialogo_modal.responder(wx.ID_CANCEL)
	assert dc.elegir_objeto(contexto) is None
	assert not contexto.historial.puede_deshacer


def test_formulario_de_colocacion_teclado(app_wx, contexto):
	for modo in dc.MODOS:
		valores = {"planta": _planta(contexto).id, "modo": modo, "alineacion": "distancia"}
		dialogo = DialogoFormulario(None, "Colocar", dc.esquema_colocacion(contexto), valores)
		try:
			afirmar_teclado_correcto(dialogo)
		finally:
			dialogo.Destroy()


# ── Reglas de escala ─────────────────────────────────────────────────────────


def test_objeto_que_no_cabe_no_se_coloca_ni_deja_historial(catalogo, dialogo_modal, voz_simulada):
	ctx = ContextoEstudio(None, Configuracion(), catalogo)
	entorno = ed.crear_entorno("Trastero")
	planta = ed.crear_planta(entorno, "Planta baja")
	cuarto = ed.crear_habitacion_rectangular(entorno, planta, "Trastero", 0, 0, 1, 1)
	ctx.abrir_documento(entorno)
	antes = ctx.entorno.a_dict()
	datos = {"planta": planta.id, "modo": "pared", "espacio": cuarto.id, "lado": "norte", "alineacion": "centro"}
	assert dc.colocar_objeto(ctx, "prueba/cama", None, datos) is None
	assert ctx.entorno.plantas[0].objetos == []
	assert ctx.entorno.a_dict() == antes
	assert not ctx.historial.puede_deshacer and not ctx.modificado
	assert dialogo_modal.ultimo is not None and dialogo_modal.ultimo.titulo == "No cabe"
	assert voz_simulada.contiene("no se ha colocado")
	# Tampoco en un punto ni en una esquina.
	assert dc.colocar_objeto(ctx, "prueba/cama", None, {"planta": planta.id, "modo": "punto", "x": 0.5, "y": 0.5}) is None
	assert dc.colocar_objeto(ctx, "prueba/cama", None, {"planta": planta.id, "modo": "esquina", "espacio": cuarto.id}) is None
	assert ctx.entorno.plantas[0].objetos == [] and not ctx.historial.puede_deshacer


def test_objeto_que_cabe_en_variante_menor_se_coloca_con_ella(catalogo, dialogo_modal, voz_simulada):
	ctx = ContextoEstudio(None, Configuracion(), catalogo)
	entorno = ed.crear_entorno("Cuarto")
	planta = ed.crear_planta(entorno, "Planta baja")
	cuarto = ed.crear_habitacion_rectangular(entorno, planta, "Cuarto", 0, 0, 1.2, 3.5)
	ctx.abrir_documento(entorno)
	datos = {"planta": planta.id, "modo": "pared", "espacio": cuarto.id, "lado": "norte", "alineacion": "centro"}
	# Cabe solo en la variante individual y deja un paso estrecho junto a la pared: se avisa y se pregunta.
	dialogo_modal.responder(lambda d: d.ids_opciones[0])
	id_objeto = dc.colocar_objeto(ctx, "prueba/cama", None, datos)
	assert id_objeto
	pregunta = " ".join(dialogo_modal.ultimo.textos)
	assert "paso de" in pregunta and "variante «Individual»" in pregunta
	cama = ctx.entorno.buscar(id_objeto)[1]
	assert cama.variante == "individual" and cama.ancho == pytest.approx(0.9)
	assert ctx.seleccion == id_objeto
	assert voz_simulada.contiene("variante «Individual»"), voz_simulada.textos
	assert ctx.historial.operaciones() == ["colocar Cama"]
	assert ctx.deshacer() == "colocar Cama"
	assert ctx.entorno.plantas[0].objetos == []


def test_aviso_de_tapar_una_puerta_pregunta_que_hacer(contexto, dialogo_modal):
	salon = _espacio(contexto, "Salón")
	datos = {"planta": _planta(contexto).id, "modo": "pared", "espacio": salon.id, "lado": "este", "alineacion": "centro"}
	ensayo = dc.ensayar(contexto, "prueba/armario", None, datos)
	assert ensayo.colocado and any("puerta" in str(a).lower() for a in ensayo.avisos), ensayo.avisos
	assert _planta(contexto).objetos == [], "el ensayo no toca el entorno abierto"
	# «Quitarlo»: no queda ni objeto ni historial.
	dialogo_modal.responder(lambda d: d.ids_opciones[1])
	assert dc.colocar_objeto(contexto, "prueba/armario", None, datos) is None
	assert _planta(contexto).objetos == [] and not contexto.historial.puede_deshacer
	assert "puerta" in " ".join(dialogo_modal.ultimo.textos).lower()
	assert any("Dejarlo así" in t for t in dialogo_modal.ultimo.textos) and any("Quitarlo" in t for t in dialogo_modal.ultimo.textos)
	# Escape (cancelar) equivale a no colocarlo.
	dialogo_modal.responder(wx.ID_CANCEL)
	assert dc.colocar_objeto(contexto, "prueba/armario", None, datos) is None
	# «Dejarlo así»: se coloca y se puede deshacer.
	dialogo_modal.responder(lambda d: d.ids_opciones[0])
	assert dc.colocar_objeto(contexto, "prueba/armario", None, datos)
	assert len(_planta(contexto).objetos) == 1 and contexto.historial.puede_deshacer


# ── Las cuatro formas de colocar, por el diálogo ─────────────────────────────


def test_insertar_contra_pared_esquina_junto_y_punto(contexto, dialogo_modal, voz_simulada):
	planta_id = _planta(contexto).id
	salon = _espacio(contexto, "Salón")
	# Contra la pared norte, a 1,20 m del extremo oeste.
	dialogo_modal.responder(
		_elegir("prueba/estanteria"),
		_rellenar(planta=planta_id, modo="pared", espacio=salon.id, lado="norte", alineacion="distancia", desplazamiento="1,20"),
	)
	id_estanteria = dc.insertar_objeto(contexto)
	estanteria = contexto.entorno.buscar(id_estanteria)[1]
	assert estanteria.x - estanteria.ancho / 2 == pytest.approx(1.2, abs=0.01)
	assert estanteria.y + estanteria.fondo / 2 == pytest.approx(4.0, abs=0.03)
	assert voz_simulada.ultimo and "Estantería" in voz_simulada.ultimo
	# En la esquina suroeste.
	dialogo_modal.responder(_elegir("prueba/mesilla"), _rellenar(planta=planta_id, modo="esquina", espacio=salon.id, esquina="suroeste"))
	mesilla = contexto.entorno.buscar(dc.insertar_objeto(contexto))[1]
	assert mesilla.x < 0.5 and mesilla.y < 0.5
	# Junto a la mesilla, a un metro al norte de ella.
	dialogo_modal.responder(
		_elegir("prueba/silla"), _rellenar(planta=planta_id, modo="junto", referencia=mesilla.id, lado_junto="norte", separacion_junto="1")
	)
	silla = contexto.entorno.buscar(dc.insertar_objeto(contexto))[1]
	mesilla = contexto.entorno.buscar(mesilla.id)[1]
	huella = contexto.catalogo.huella
	assert min(y for _x, y in huella(silla)) == pytest.approx(max(y for _x, y in huella(mesilla)) + 1.0, abs=0.02)
	assert silla.x == pytest.approx(mesilla.x, abs=0.02)
	# En un punto por coordenadas, con nombre propio.
	dialogo_modal.responder(
		_elegir("prueba/mesa_redonda"), _rellenar(planta=planta_id, modo="punto", x=2.5, y=2, rumbo=90, nombre="Mesa del centro")
	)
	mesa = contexto.entorno.buscar(dc.insertar_objeto(contexto))[1]
	assert (mesa.x, mesa.y) == (2.5, 2.0) and mesa.nombre == "Mesa del centro"
	assert contexto.historial.operaciones() == [
		"colocar Estantería",
		"colocar Mesilla de noche",
		"colocar Silla",
		"colocar Mesa del centro",
	]
	assert contexto.seleccion == mesa.id and contexto.modificado


def test_insertar_en_punto_del_plano_o_del_recorrido(contexto, dialogo_modal):
	cocina = _espacio(contexto, "Cocina")
	dialogo_modal.responder(_elegir("prueba/silla"))
	id_silla = dc.insertar_objeto(contexto, planta_id=_planta(contexto).id, punto=(6.5, 2.0), rumbo=180.0)
	silla = contexto.entorno.buscar(id_silla)[1]
	assert (silla.x, silla.y, silla.rumbo) == (6.5, 2.0, 180.0)
	assert cocina.contiene(silla.x, silla.y)
	# Solo se abrió el catálogo: con punto no se pregunta dónde.
	assert [m.titulo for m in dialogo_modal.mostrados] == ["Insertar objeto del catálogo"]


def test_insertar_cancelado_o_sin_entorno(catalogo, contexto, dialogo_modal):
	dialogo_modal.responder(wx.ID_CANCEL)
	assert dc.insertar_objeto(contexto) is None
	dialogo_modal.responder(_elegir("prueba/silla"), wx.ID_CANCEL)
	assert dc.insertar_objeto(contexto) is None
	assert not contexto.historial.puede_deshacer
	vacio = ContextoEstudio(None, Configuracion(), catalogo)
	assert dc.insertar_objeto(vacio) is None
	assert "entorno abierto" in " ".join(dialogo_modal.ultimo.textos)


def test_valores_iniciales_segun_la_seleccion(contexto):
	cocina = _espacio(contexto, "Cocina")
	contexto.seleccionar(cocina.id)
	valores = dc._valores_iniciales(contexto, None, None)
	assert valores["planta"] == _planta(contexto).id and valores["espacio"] == cocina.id


# ── Con lo que el dominio ya ofrece (árbol, facetas, relacionados y taxonomía reales) ──


def _catalogo_clasificado(tmp_path):
	"""Complemento escrito en disco con la clasificación en su JSON, cargado por el dominio de verdad."""
	import copy

	from app.dominio.catalogo import Catalogo
	from tests.test_dominio_comun import FICHA_PRUEBA, escribir_complemento

	ficha = copy.deepcopy(FICHA_PRUEBA)
	ficha["id"] = "clasificado"
	ficha["subcategorias"] = {"asientos": "Asientos y sofás", "camas": "Camas"}
	clasificacion = {
		"cama": {
			"subcategoria": "camas",
			"funcion": "descanso",
			"lugares": ["vivienda"],
			"estancias": ["dormitorio"],
			"frecuencia": "muy_comun",
		},
		"sofa": {
			"subcategoria": "asientos",
			"funcion": "asiento",
			"lugares": ["vivienda"],
			"estancias": ["salon"],
			"relacionados": ["mesa"],
		},
		"silla": {
			"subcategoria": "asientos",
			"funcion": "asiento",
			"lugares": ["vivienda"],
			"estancias": ["salon"],
			"frecuencia": "muy_comun",
		},
		"mesa": {"funcion": "mesa", "lugares": ["vivienda"], "estancias": ["salon"]},
	}
	for objeto in ficha["objetos"]:
		objeto.update(clasificacion.get(objeto["id"], {}))
	escribir_complemento(tmp_path / "clasificados", ficha)
	return Catalogo.cargar(tmp_path / "clasificados")


def test_con_el_dominio_real_arbol_facetas_y_relacionados(app_wx, tmp_path, voz_simulada):
	real = _catalogo_clasificado(tmp_path)
	if not all(callable(getattr(real, nombre, None)) for nombre in ("arbol", "facetas", "relacionados")):
		pytest.skip("el dominio todavía no ofrece arbol(), facetas() y relacionados()")
	dialogo = dc.DialogoCatalogo(None, real)
	try:
		afirmar_teclado_correcto(dialogo, teclas_propias=["Ctrl+D"])
		textos = _textos_arbol(dialogo)
		total = len(real.objetos())
		assert textos[0] == (0, f"Todos ({total})") and (0, f"Complemento de prueba ({total})") in textos
		assert (2, "Asientos y sofás (2)") in textos and (2, "Camas (1)") in textos
		# Los recuentos del árbol del dominio coinciden con lo que enseña la lista.
		assert dialogo.elegir_nodo("sub", "clasificado", "salon", "asientos") and dialogo.lista.GetItemCount() == 2
		assert dialogo.elegir_nodo("cat", "clasificado", "dormitorio") and dialogo.lista.GetItemCount() == 3
		assert dialogo.elegir_nodo("todos")
		# Facetas del dominio, con sus nombres y recuentos.
		assert {"lugar", "estancia", "funcion", "obstaculo"} <= set(dialogo.elecciones_faceta)
		funciones = dialogo.elecciones_faceta["funcion"]
		assert f"{dc.nombre_valor('funcion', 'asiento')} (2)" in funciones.GetStrings()
		assert dialogo.filtrar(funcion="asiento") == 2
		assert [d.tipo for d in dialogo._definiciones] == ["clasificado/silla", "clasificado/sofa"], "la más común, primero"
		assert dialogo.filtrar(funcion=dc.TODOS, estancia="salon") == 3
		assert dialogo.filtrar(estancia=dc.TODOS, sonido_propio=True) == 1
		dialogo.filtrar(sonido_propio=False)
		# El tipo de obstáculo se deduce de las medidas aunque el complemento no lo declare.
		assert sum(cuenta for _valor, cuenta in dialogo._facetas()["obstaculo"]) == total
		# Relacionados: lo que declara la ficha y lo que el dominio deduce por función y estancia.
		assert dialogo.boton_relacionados is not None
		dialogo.elegir("clasificado/sofa")
		assert dialogo.mostrar_relacionados() >= 1
		assert "clasificado/mesa" in {d.tipo for d in dialogo._definiciones}
		assert "Clasificación: Salón, asientos y sofás." in dc.texto_descripcion(real, real.objeto("clasificado/sofa"))
	finally:
		dialogo.Destroy()
