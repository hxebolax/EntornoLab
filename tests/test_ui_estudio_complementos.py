"""Pruebas de «Complementos instalados» y del asistente «Crear un complemento propio»."""

from __future__ import annotations

import struct

import pytest
import wx

from app.core import paths
from app.core.config import Configuracion
from app.dominio.catalogo import Catalogo, empaquetar_complemento, instalar_complemento, validar_complemento
from app.dominio.modelo import hay_errores
from app.services import complementos_en_linea as servicio
from app.ui import asistente_complemento as asistente
from app.ui import complemento_propio as propio
from app.ui import dialogo_complementos as dcomp
from app.ui.accesibilidad.revision_teclado import afirmar_teclado_correcto
from app.ui.contexto import ContextoEstudio
from app.ui.esquemas import ErrorCampo
from tests.test_dominio_comun import FICHA_PRUEBA, escribir_complemento

MESA = {
	"nombre": "Mesa alta",
	"categoria": "Bar",
	"etiquetas": "mesa, barra",
	"descripcion": "Mesa alta de bar, redonda.",
	"forma": "circulo",
	"ancho_min": "0,5",
	"ancho_normal": "0,7",
	"ancho_max": "1",
	"fondo_min": 0.5,
	"fondo_normal": 0.7,
	"fondo_max": 1.0,
	"alto_min": 1.0,
	"alto_normal": 1.1,
	"alto_max": 1.2,
	"variantes": "Pequeña: 0,6 x 0,6 x 1,1\nGrande: 0,9 x 0,9 x 1,1",
	"material": "metal",
	"sonido_golpe": "golpe/metal",
	"letra": "Ma",
	"color": "#1F4E9C",
}
ARCON = {
	"nombre": "Arcón",
	"categoria": "Bar",
	"descripcion": "Arcón bajo con una esquina cortada.",
	"forma": "poligono",
	"puntos": "0, 0; 1, 0; 1, 1; 0.5, 1; 0, 0.5",
	"ancho_min": 0.8,
	"ancho_normal": 1.2,
	"ancho_max": 1.6,
	"fondo_min": 0.5,
	"fondo_normal": 0.6,
	"fondo_max": 0.8,
	"alto_min": 0.6,
	"alto_normal": 0.8,
	"alto_max": 1.0,
	"estados": "cerrado, abierto",
	"acciones": "Abrir: cerrado > abierto\nCerrar: abierto > cerrado\nGolpear",
	"contenedor": True,
	"colocacion": ["suelo", "pared"],
}


@pytest.fixture
def contexto(data_temporal):
	"""Contexto sin ventana con el complemento de prueba instalado en la carpeta data de la prueba."""
	escribir_complemento(paths.ruta_complementos())
	ctx = ContextoEstudio(None, Configuracion())
	ctx.recargar_catalogo()
	return ctx


def _elabc(tmp_path, identificador="mio", nombre="Complemento mío"):
	"""Crea un .elabc de prueba con dos objetos del complemento de pruebas."""
	ficha = dict(FICHA_PRUEBA, id=identificador, nombre=nombre, objetos=FICHA_PRUEBA["objetos"][:2])
	carpeta = escribir_complemento(tmp_path / "origen", ficha)
	return empaquetar_complemento(carpeta, tmp_path / f"{identificador}.elabc")


def _valores(numeros_como_texto: dict) -> dict:
	"""Los valores como salen del formulario: las medidas ya convertidas a número."""
	from app.ui.esquemas import leer_numero

	return {
		k: (leer_numero(v) if isinstance(v, str) and (k.endswith(("_min", "_normal", "_max"))) else v)
		for k, v in numeros_como_texto.items()
	}


# ── Complementos instalados ──────────────────────────────────────────────────


def _anterior(control):
	hermanos = list(control.GetParent().GetChildren())
	return hermanos[hermanos.index(control) - 1]


def test_veinte_complementos_filtro_y_desglose(app_wx, data_temporal, voz_simulada, dialogo_modal):
	import copy

	for numero in range(20):
		ficha = copy.deepcopy(FICHA_PRUEBA)
		ficha["id"] = f"comp{numero:02d}"
		ficha["nombre"] = ("Hospital" if numero % 5 == 0 else "Complemento") + f" {numero:02d}"
		ficha["subcategorias"] = {"asientos": "Asientos"}
		ficha["objetos"] = ficha["objetos"][: 3 + numero]
		for objeto in ficha["objetos"]:
			if objeto["id"] in ("silla", "sofa"):
				objeto["subcategoria"] = "asientos"
		escribir_complemento(paths.ruta_complementos(), ficha)
	contexto = ContextoEstudio(None, Configuracion())
	contexto.recargar_catalogo()
	dialogo = dcomp.DialogoComplementos(None, contexto)
	try:
		afirmar_teclado_correcto(dialogo, teclas_propias=["Supr"])
		assert dialogo.lista.GetItemCount() == 20 and dialogo.texto_recuento.GetLabel().startswith("20 complementos, ")
		assert dialogo.filtrar("hospital") == 4 and voz_simulada.ultimo == "4 complementos"
		assert all(dialogo.lista.valores_fila(i)[0].startswith("Hospital") for i in range(4))
		assert dialogo.lista.GetFocusedItem() == 0
		# También por categoría, sin tildes; y una búsqueda sin resultados deja los botones desactivados.
		assert dialogo.filtrar("bano") == sum(1 for n in range(20) if 3 + n >= 14)
		assert dialogo.filtrar("zzz") == 0 and not dialogo.boton_detalles.IsEnabled()
		assert dialogo.filtrar("") == 20
		# Detalles con el desglose por categoría y subcategoría.
		assert dialogo.enfocar("comp19")
		dialogo.detalles()
		texto = " ".join(dialogo_modal.ultimo.textos)
		assert "Objetos por categoría:" in texto and "Dormitorio: 3 objetos." in texto
		assert "Salón: 8 objetos" in texto and (
			"Asientos 2" in texto or not hasattr(contexto.catalogo.objeto("comp19/silla"), "subcategoria")
		)
	finally:
		dialogo.Destroy()


def test_complementos_teclado_y_lista(app_wx, contexto):
	dialogo = dcomp.DialogoComplementos(None, contexto)
	try:
		afirmar_teclado_correcto(dialogo, teclas_propias=["Supr"])
		assert dialogo.GetEscapeId() == wx.ID_CANCEL
		hijos = list(dialogo.GetChildren())
		anterior = hijos[hijos.index(dialogo.lista) - 1]
		assert isinstance(anterior, wx.StaticText) and anterior.GetLabel() == "Co&mplementos instalados:"
		assert dialogo.lista.GetItemCount() == 1 and dialogo.lista.GetFocusedItem() == 0
		fila = dialogo.lista.valores_fila(0)
		assert fila[:3] == ["Complemento de prueba", "1.0", str(len(FICHA_PRUEBA["objetos"]))] and fila[4:] == ["Activo", "De serie"]
		assert fila[3].startswith("Salón, Dormitorio") and fila[3].endswith("más"), "las categorías con más objetos, primero"
		assert [dialogo.lista.GetColumn(i).GetText() for i in range(6)] == [
			"Nombre",
			"Versión",
			"Objetos",
			"Categorías",
			"Estado",
			"Origen",
		]
		assert isinstance(_anterior(dialogo.campo_filtro), wx.StaticText) and "&" in _anterior(dialogo.campo_filtro).GetLabel()
		assert dialogo.texto_recuento.GetLabel() == f"1 complemento, {len(FICHA_PRUEBA['objetos'])} objetos en total"
		assert not dialogo.boton_quitar.IsEnabled(), "uno de serie no se puede quitar"
		for boton in (dialogo.boton_activar, dialogo.boton_anadir, dialogo.boton_comprobar, dialogo.boton_quitar, dialogo.boton_detalles):
			assert "&" in boton.GetLabel() and boton.GetHelpText()
		menu = dialogo._crear_menu()
		assert [i.GetItemLabelText() for i in menu.GetMenuItems()] == ["Activar o desactivar", "Comprobar", "Detalles", "Quitar"]
		menu.Destroy()
	finally:
		dialogo.Destroy()


def test_activar_y_desactivar_sin_reiniciar_y_persiste(app_wx, contexto, voz_simulada):
	avisos = []
	contexto.suscribir("catalogo_cambiado", lambda: avisos.append(True))
	dialogo = dcomp.DialogoComplementos(None, contexto)
	try:
		assert contexto.catalogo.buscar("cama")
		dialogo.alternar()
		assert dialogo.lista.valores_fila(0)[4] == "Desactivado"
		assert contexto.catalogo.buscar("") == [] and contexto.catalogo.vacio
		assert Configuracion().obtener("complementos.desactivados") == ["prueba"], "queda guardado en disco"
		assert voz_simulada.contiene("desactivado") and avisos
		# Los objetos ya colocados conservan su ficha aunque el complemento esté desactivado.
		assert contexto.catalogo.objeto("prueba/cama") is not None
		dialogo.alternar()
		assert dialogo.lista.valores_fila(0)[4] == "Activo"
		assert contexto.catalogo.buscar("cama") and Configuracion().obtener("complementos.desactivados") == []
		assert dialogo.lista.GetFocusedItem() == 0
	finally:
		dialogo.Destroy()


def test_anadir_desde_fichero_comprobar_detalles_y_quitar(app_wx, contexto, tmp_path, dialogo_modal, voz_simulada):
	ruta = _elabc(tmp_path)
	dialogo = dcomp.DialogoComplementos(None, contexto)
	try:
		assert dialogo.anadir(ruta) == "mio"
		assert dialogo.lista.GetItemCount() == 2
		assert dialogo.actual().id == "mio", "el foco queda en el recién instalado"
		assert dialogo.lista.valores_fila(dialogo.lista.fila_actual())[5] == "Del usuario"
		assert contexto.catalogo.objeto("mio/cama") is not None, "disponible sin reiniciar"
		assert dialogo.boton_quitar.IsEnabled()
		# Comprobar: el resultado va a un campo de solo lectura.
		texto = dialogo.comprobar()
		assert texto and dialogo_modal.ultimo.clase == "DialogoTexto" and texto in dialogo_modal.ultimo.textos
		dialogo.detalles()
		assert any("Identificador: mio" in t and "añadido por el usuario" in t for t in dialogo_modal.ultimo.textos)
		# Quitar: «Conservarlo» no hace nada; «Quitar el complemento» lo borra.
		dialogo_modal.responder(lambda d: d.ids_opciones[1])
		assert dialogo.quitar() is False and (paths.ruta_complementos() / "mio").is_dir()
		assert any("Quitar el complemento" in t for t in dialogo_modal.ultimo.textos)
		dialogo_modal.responder(lambda d: d.ids_opciones[0])
		assert dialogo.quitar() is True
		assert not (paths.ruta_complementos() / "mio").exists()
		assert contexto.catalogo.objeto("mio/cama") is None and dialogo.lista.GetItemCount() == 1
		assert "mio" not in servicio.leer_registro()["instalados"]
		# El de serie no se quita ni pidiéndolo.
		assert dialogo.enfocar("prueba") and dialogo.quitar() is False
		assert (paths.ruta_complementos() / "prueba").is_dir()
	finally:
		dialogo.Destroy()


def test_anadir_fichero_danado_o_cancelado(app_wx, contexto, tmp_path, dialogo_modal):
	malo = tmp_path / "roto.elabc"
	malo.write_bytes(b"esto no es un zip")
	dialogo = dcomp.DialogoComplementos(None, contexto)
	try:
		assert dialogo.anadir(malo) is None
		assert "no se ha instalado" in " ".join(dialogo_modal.ultimo.textos)
		dialogo_modal.responder(wx.ID_CANCEL)
		assert dialogo.anadir() is None
		assert dialogo.lista.GetItemCount() == 1
	finally:
		dialogo.Destroy()


def test_mostrar_complementos_no_bloquea(contexto, dialogo_modal):
	dcomp.mostrar_complementos(contexto)
	assert dialogo_modal.ultimo.titulo == "Complementos instalados"


# ── Lógica del complemento propio (sin ventanas) ─────────────────────────────


def test_textos_a_listas():
	assert propio.leer_puntos("0,0; 1,0; 0,1") == [[0, 0], [1, 0], [0, 1]]
	assert propio.leer_puntos("0 0\n1 0\n0,5 1") == [[0, 0], [1, 0], [0.5, 1]]
	assert propio.texto_puntos([[0, 0], [1, 0], [0.5, 1]]) == "0, 0; 1, 0; 0.5, 1"
	with pytest.raises(ErrorCampo):
		propio.leer_puntos("0,0; 2,0; 0,1")
	with pytest.raises(ErrorCampo):
		propio.leer_puntos("0,0; 1,0")
	variantes = propio.leer_variantes("De dos plazas: 1,5 x 0,9 x 0,85\nGrande: 2 × 1 × 0.9")
	assert variantes[0] == {"id": "de_dos_plazas", "nombre": "De dos plazas", "ancho": 1.5, "fondo": 0.9, "alto": 0.85}
	assert propio.leer_variantes(propio.texto_variantes(variantes)) == variantes
	with pytest.raises(ErrorCampo):
		propio.leer_variantes("sin medidas")
	acciones = propio.leer_acciones("Abrir: cerrado > abierto\nPulsar", ["cerrado", "abierto"])
	assert acciones == [{"id": "abrir", "nombre": "Abrir", "de": "cerrado", "a": "abierto"}, {"id": "pulsar", "nombre": "Pulsar"}]
	with pytest.raises(ErrorCampo):
		propio.leer_acciones("Abrir: cerrado > roto", ["cerrado", "abierto"])
	assert propio.id_de("Mesa de Café Ñ") == "mesa_de_cafe_n"


def test_objeto_a_dict_valida_y_es_reversible():
	from app.ui.esquemas import valores_por_defecto

	base = valores_por_defecto(propio.esquema_objeto())
	ficha = propio.objeto_a_dict({**base, **_valores(MESA)})
	assert ficha["id"] == "mesa_alta" and ficha["forma"] == {"tipo": "circulo"}
	assert ficha["medidas"]["ancho"] == [0.5, 0.7, 1.0]
	assert [v["id"] for v in ficha["variantes"]] == ["pequena", "grande"]
	assert ficha["sonidos"] == {"golpe": "golpe/metal"} and ficha["simbolo"] == {"letra": "Ma", "color": "#1F4E9C"}
	assert propio.objeto_a_dict({**base, **propio.dict_a_valores(ficha)}, ficha["id"]) == ficha
	with pytest.raises(ErrorCampo) as error:
		propio.objeto_a_dict({**base, **_valores(MESA), "ancho_max": 0.6})
	assert error.value.clave == "ancho_max"
	with pytest.raises(ErrorCampo) as error:
		propio.objeto_a_dict({**base, **_valores(MESA), "variantes": "Enorme: 3 x 3 x 1,1"})
	assert error.value.clave == "variantes"
	with pytest.raises(ErrorCampo) as error:
		propio.objeto_a_dict({**base, **_valores(ARCON), "puntos": ""})
	assert error.value.clave == "puntos"
	with pytest.raises(ErrorCampo):
		propio.construir_complemento({"nombre": "Vacío"}, [])


@pytest.mark.parametrize(
	"forma", [{"tipo": "rectangulo"}, {"tipo": "circulo"}, {"tipo": "ele"}, {"tipo": "poligono", "puntos": [[0, 0], [1, 0], [0, 1]]}]
)
def test_miniatura_png_valida(tmp_path, forma):
	ruta = propio.generar_miniatura(forma, tmp_path / "m.png", lado=64, letra="Ñá", color="#C62828", ancho=2.0, fondo=1.0)
	datos = ruta.read_bytes()
	assert datos[:8] == b"\x89PNG\r\n\x1a\n" and datos[12:16] == b"IHDR"
	assert struct.unpack(">II", datos[16:24]) == (64, 64)
	assert datos[-12:-8] == struct.pack(">I", 0) and datos[-8:-4] == b"IEND"


def test_miniatura_se_puede_cargar_y_tiene_el_color(app_wx, tmp_path):
	ruta = propio.generar_miniatura({"tipo": "rectangulo"}, tmp_path / "m.png", lado=64, letra="M", color="#2E7D32")
	imagen = wx.Image(str(ruta))
	assert imagen.IsOk() and imagen.GetSize() == (64, 64)
	assert (imagen.GetRed(10, 10), imagen.GetGreen(10, 10), imagen.GetBlue(10, 10)) == (0x2E, 0x7D, 0x32)
	assert (imagen.GetRed(0, 0), imagen.GetGreen(0, 0), imagen.GetBlue(0, 0)) == (255, 255, 255)


def test_sonidos_de_serie_y_wav(tmp_path):
	sonidos = propio.sonidos_de_serie()
	assert any(clave == "golpe/madera" for clave, _nombre in sonidos)
	opciones = propio.opciones_sonido("golpe")
	assert opciones[0][0] == "" and opciones[1][0].startswith("golpe/")
	assert propio.sonido_a_wav("") is None
	ruta = propio.sonido_a_wav("golpe/madera", tmp_path / "s.wav")
	if ruta is not None:  # depende de las bibliotecas de sonido del equipo
		assert ruta.read_bytes()[:4] == b"RIFF"


# ── Asistente ────────────────────────────────────────────────────────────────


def test_asistente_teclado(app_wx, contexto):
	dialogo = asistente.AsistenteComplemento(None, contexto)
	try:
		afirmar_teclado_correcto(dialogo, teclas_propias=["Supr"])
		assert dialogo.GetEscapeId() == wx.ID_CANCEL
		assert [dialogo.cuaderno.GetPageText(i) for i in range(3)] == ["Ficha", "Objetos", "Guardar"]
		for control in (dialogo.lista, dialogo.campo_resultado):
			hermanos = list(control.GetParent().GetChildren())
			anterior = hermanos[hermanos.index(control) - 1]
			assert isinstance(anterior, wx.StaticText) and "&" in anterior.GetLabel()
		assert not dialogo.campo_resultado.IsEditable()
		assert not dialogo.boton_editar.IsEnabled()
	finally:
		dialogo.Destroy()


def test_dialogo_de_objeto_teclado_y_escuchar(app_wx, monkeypatch, tmp_path, dialogo_modal):
	sonados = []
	monkeypatch.setattr(propio, "sonido_a_wav", lambda nombre, destino=None, segundos=4.0: tmp_path / f"{nombre.replace('/', '_')}.wav")
	monkeypatch.setattr(asistente, "_reproducir_wav", lambda ruta: sonados.append(ruta.name) or True)
	dialogo = asistente.DialogoObjeto(None)
	try:
		afirmar_teclado_correcto(dialogo)
		assert "&" in dialogo.boton_escuchar.GetLabel() and dialogo.boton_escuchar.GetHelpText()
		for clave, control in dialogo.formulario.controles.items():
			assert not isinstance(control, (wx.SpinCtrlDouble, wx.SearchCtrl)), clave
		# Sin sonido elegido lo dice y no suena nada.
		assert dialogo.escuchar_elegido() is False and "No hay ningún sonido" in dialogo.ultimo_aviso
		dialogo.fijar({"sonido_golpe": "golpe/metal", "sonido_propio": "fuente/frigorifico"})
		assert dialogo.sonido_elegido() == "golpe/metal"
		assert dialogo.escuchar_elegido() is True and sonados == ["golpe_metal.wav"]
		# Un fallo de sonido no rompe nada.
		monkeypatch.setattr(asistente, "_reproducir_wav", lambda ruta: False)
		assert dialogo.escuchar_elegido() is False and "No se ha podido" in dialogo.ultimo_aviso
		# El polígono enseña el campo de puntos.
		dialogo.fijar({"forma": "poligono"})
		assert "puntos" in dialogo.formulario.controles
		afirmar_teclado_correcto(dialogo)
		# Validación con foco en el campo: falta el nombre.
		assert dialogo.aceptar() is False and "Falta" in dialogo.ultimo_error
	finally:
		dialogo.Destroy()


def test_asistente_crea_un_complemento_valido_y_exportable(app_wx, contexto, tmp_path, dialogo_modal, voz_simulada):
	dialogo = asistente.AsistenteComplemento(None, contexto)
	try:
		# Sin nombre ni objetos no se guarda nada.
		assert dialogo.guardar() is None and "Falta" in dialogo.ultimo_error
		dialogo.fijar_ficha({"nombre": "Muebles de bar", "autor": "Pruebas", "descripcion": "Mesas y arcones."})
		assert dialogo.guardar() is None and "ningún objeto" in dialogo.ultimo_error
		# Un objeto directo y otro por su formulario (diálogo simulado).
		assert dialogo.anadir_objeto(_valores(MESA))["id"] == "mesa_alta"
		dialogo_modal.responder(lambda d: (d.fijar(ARCON), wx.ID_OK)[1])
		arcon = dialogo.anadir_objeto()
		assert arcon is not None and arcon["forma"]["tipo"] == "poligono" and len(arcon["acciones"]) == 3
		assert dialogo.lista.GetItemCount() == 2 and dialogo.lista.valores_fila(0)[:3] == ["Mesa alta", "Bar", "Círculo o elipse"]
		# Duplicar, editar la copia y quitarla.
		copia = dialogo.duplicar_objeto()
		assert copia["id"] == "arcon_2" and dialogo.lista.GetItemCount() == 3 and dialogo.lista.fila_actual() == 2
		dialogo_modal.responder(lambda d: (d.fijar({"nombre": "Arcón grande", "ancho_max": 2}), wx.ID_OK)[1])
		editado = dialogo.editar_objeto()
		assert editado["nombre"] == "Arcón grande" and editado["id"] == "arcon_2" and editado["medidas"]["ancho"][2] == 2.0
		dialogo_modal.responder(lambda d: d.ids_opciones[0])
		assert dialogo.quitar_objeto() and dialogo.lista.GetItemCount() == 2
		# Un objeto mal definido no entra.
		assert dialogo.anadir_objeto({**_valores(MESA), "ancho_min": 5}) is None and len(dialogo.objetos) == 2
		# Comprobar no instala nada.
		avisos = dialogo.comprobar()
		assert avisos is not None and not hay_errores(avisos), [str(a) for a in avisos]
		assert not (paths.ruta_complementos() / "muebles_de_bar").exists()
		# Guardar.
		carpeta = dialogo.guardar()
		assert carpeta == paths.ruta_complementos() / "muebles_de_bar" and dialogo.id_guardado == "muebles_de_bar"
		assert "guardado en" in dialogo.campo_resultado.GetValue()
		assert voz_simulada.contiene("guardado")
		# Volver a guardar (el mismo, en esta sesión) no pregunta nada.
		assert dialogo.guardar() == carpeta
		ruta_zip = dialogo.exportar(tmp_path / "bar.elabc")
		assert ruta_zip is not None and ruta_zip.is_file()
	finally:
		dialogo.Destroy()

	assert validar_complemento(carpeta) == [], [str(a) for a in validar_complemento(carpeta)]
	for id_objeto in ("mesa_alta", "arcon"):
		assert (carpeta / "imagenes" / f"{id_objeto}.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
	# Disponible en el catálogo abierto, sin reiniciar, y como complemento del usuario.
	mesa = contexto.catalogo.objeto("muebles_de_bar/mesa_alta")
	assert mesa is not None and mesa.letra() == "Ma" and mesa.imagen["descripcion"].startswith("Huella en planta")
	assert contexto.catalogo.nombre_categoria("bar") == "Bar"
	assert servicio.instalados()["muebles_de_bar"].de_serie is False
	cargado = Catalogo.cargar(paths.ruta_complementos())
	assert {d.id for d in cargado.complemento("muebles_de_bar").objetos} == {"mesa_alta", "arcon"}
	assert len(cargado.objeto("muebles_de_bar/arcon").puntos_forma()) == 5
	# El .elabc se instala en otro equipo (otra carpeta de complementos).
	otra = tmp_path / "otro_equipo"
	otra.mkdir()
	assert instalar_complemento(ruta_zip, otra) == "muebles_de_bar"
	assert validar_complemento(otra / "muebles_de_bar") == []


def test_asistente_no_pisa_un_complemento_de_serie(app_wx, contexto, dialogo_modal):
	dialogo = asistente.AsistenteComplemento(None, contexto)
	try:
		dialogo.fijar_ficha({"nombre": "Otro", "id": "prueba"})
		dialogo.anadir_objeto(_valores(MESA))
		assert dialogo.guardar() is None and "de serie" in dialogo.ultimo_error
		assert contexto.catalogo.objeto("prueba/cama") is not None
	finally:
		dialogo.Destroy()


def test_mostrar_asistente_devuelve_none_si_no_se_guarda(contexto, dialogo_modal):
	dialogo_modal.responder(wx.ID_CANCEL)
	assert asistente.mostrar_asistente_complemento(contexto) is None


# ── Clasificación en el asistente ────────────────────────────────────────────


def test_clasificacion_en_el_formulario_del_objeto(app_wx, dialogo_modal):
	from app.ui.esquemas import valores_por_defecto

	campos = {campo.clave: campo for campo in propio.esquema_objeto()}
	for clave in ("subcategoria", "funcion", "lugares", "estancias", "obstaculo", "riesgos", "frecuencia"):
		assert campos[clave].grupo == propio.G_CLASE, clave
	base = valores_por_defecto(propio.esquema_objeto())
	# Sin rellenar nada, la ficha no lleva ninguna clave de clasificación.
	sin = propio.objeto_a_dict({**base, **_valores(MESA)})
	assert not {"subcategoria", "funcion", "lugares", "estancias", "obstaculo", "riesgos", "frecuencia"} & set(sin)
	if propio.tabla_taxonomia("funcion") is None:
		# Dominio sin taxonomía: texto libre.
		assert campos["funcion"].tipo == "texto" and campos["lugares"].tipo == "texto"
		con = propio.objeto_a_dict(
			{**base, **_valores(MESA), "subcategoria": "Mesas altas", "funcion": "Mesa", "lugares": "bar, cafetería"}
		)
		assert con["subcategoria"] == "mesas_altas" and con["funcion"] == "mesa" and con["lugares"] == ["bar", "cafeteria"]
		return
	# Dominio con taxonomía: listas cerradas con sus valores.
	assert campos["funcion"].tipo == "opcion" and campos["obstaculo"].tipo == "opcion" and campos["frecuencia"].tipo == "opcion"
	assert campos["lugares"].tipo == "casillas" and campos["estancias"].tipo == "casillas" and campos["riesgos"].tipo == "casillas"
	funcion = next(iter(propio.tabla_taxonomia("funcion")))
	lugares = list(propio.tabla_taxonomia("lugar"))[:2]
	estancia = next(iter(propio.tabla_taxonomia("estancia")))
	obstaculo = list(propio.tabla_taxonomia("obstaculo"))[-1]
	frecuencia = next(iter(propio.tabla_taxonomia("frecuencia")))
	clasificacion = {
		"subcategoria": "Mesas altas",
		"funcion": funcion,
		"lugares": lugares,
		"estancias": [estancia],
		"obstaculo": obstaculo,
		"frecuencia": frecuencia,
	}
	con = propio.objeto_a_dict({**base, **_valores(MESA), **clasificacion})
	assert con["subcategoria"] == "mesas_altas" and con["funcion"] == funcion and con["lugares"] == lugares
	assert con["estancias"] == [estancia] and con["obstaculo"] == obstaculo and con["frecuencia"] == frecuencia and "riesgos" not in con
	assert propio.objeto_a_dict({**base, **propio.dict_a_valores(con)}, con["id"]) == con
	datos = propio.construir_complemento({"nombre": "Bar"}, [con, sin])
	assert datos["subcategorias"] == {"mesas_altas": "Mesas altas"}
	assert "subcategorias" not in propio.construir_complemento({"nombre": "Bar"}, [sin])
	# El formulario los enseña en su pestaña, con teclado correcto, y los devuelve.
	dialogo = asistente.DialogoObjeto(None, {**_valores(MESA), **clasificacion})
	try:
		afirmar_teclado_correcto(dialogo)
		for clave in clasificacion:
			assert clave in dialogo.formulario.controles, clave
		assert isinstance(dialogo.formulario.controles["lugares"], wx.CheckListBox)
		assert dialogo.aceptar() and dialogo.producto == con
	finally:
		dialogo.Destroy()


def test_asistente_con_clasificacion_pasa_el_validador(app_wx, contexto, dialogo_modal):
	clasificacion = {"subcategoria": "Mesas altas"}
	if propio.tabla_taxonomia("funcion") is not None:
		clasificacion.update(
			funcion=next(iter(propio.tabla_taxonomia("funcion"))),
			lugares=list(propio.tabla_taxonomia("lugar"))[:2],
			estancias=[next(iter(propio.tabla_taxonomia("estancia")))],
			obstaculo=next(iter(propio.tabla_taxonomia("obstaculo"))),
			riesgos=[next(iter(propio.tabla_taxonomia("riesgo")))],
			frecuencia=next(iter(propio.tabla_taxonomia("frecuencia"))),
		)
	dialogo = asistente.AsistenteComplemento(None, contexto)
	try:
		dialogo.fijar_ficha({"nombre": "Bar clasificado", "autor": "Pruebas"})
		assert dialogo.anadir_objeto({**_valores(MESA), **clasificacion}) is not None
		assert dialogo.anadir_objeto(_valores(ARCON)) is not None
		carpeta = dialogo.guardar()
		assert carpeta is not None
	finally:
		dialogo.Destroy()
	assert validar_complemento(carpeta) == [], [str(a) for a in validar_complemento(carpeta)]
	mesa = contexto.catalogo.objeto("bar_clasificado/mesa_alta")
	assert mesa is not None and getattr(mesa, "subcategoria", "mesas_altas") == "mesas_altas"
	if propio.tabla_taxonomia("funcion") is not None:
		assert mesa.funcion == clasificacion["funcion"] and mesa.lugares == clasificacion["lugares"]
		assert mesa.obstaculo == clasificacion["obstaculo"] and mesa.frecuencia == clasificacion["frecuencia"]
		assert contexto.catalogo.complemento("bar_clasificado").nombre_subcategoria("mesas_altas") == "Mesas altas"
