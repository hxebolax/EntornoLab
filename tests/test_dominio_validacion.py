"""Pruebas del validador del entorno: cada comprobación, con su mensaje y su sugerencia."""

from __future__ import annotations

from app.dominio import colocacion as co
from app.dominio import edicion as ed
from app.dominio.catalogo import Catalogo
from app.dominio.modelo import (
	Abertura,
	Conector,
	Entorno,
	Espacio,
	FuenteSonido,
	Objeto,
	Parada,
	Pared,
	Planta,
	Posicion,
	Tramo,
	Via,
	ZonaSuelo,
)
from app.dominio.validacion import Aviso, hay_errores, resumen, validar
from tests.test_dominio_comun import catalogo_de_prueba, piso_minimo


def _codigos(avisos) -> list[str]:
	return sorted(a.codigo for a in avisos)


def _el(avisos, codigo: str) -> Aviso:
	return next(a for a in avisos if a.codigo == codigo)


def test_entorno_correcto_no_tiene_avisos():
	entorno, _planta, _salon, _cocina = piso_minimo()
	assert validar(entorno) == []
	assert validar(entorno, Catalogo()) == []
	assert resumen([]) == "Sin problemas."


def test_todo_aviso_lleva_mensaje_y_sugerencia():
	entorno = Entorno(nombre="Roto", inicio=Posicion("fantasma", 0, 0, 0))
	entorno.plantas.append(Planta(id="p", nombre="Vacía"))
	entorno.plantas.append(Planta(id="p", nombre="Repetida", espacios=[Espacio(id="", nombre="Mala", contorno=[(0, 0), (1, 1)])]))
	avisos = validar(entorno)
	assert len(avisos) >= 5
	for aviso in avisos:
		assert aviso.gravedad in ("error", "aviso")
		assert aviso.codigo
		assert aviso.mensaje.endswith(".")
		assert aviso.sugerencia
	# Los errores van delante.
	gravedades = [a.gravedad for a in avisos]
	assert gravedades == sorted(gravedades, key=lambda g: 0 if g == "error" else 1)
	assert hay_errores(avisos)
	assert resumen(avisos).endswith(".")


def test_entorno_sin_plantas():
	avisos = validar(Entorno())
	assert _codigos(avisos) == ["entorno_vacio"]
	assert avisos[0].es_error


def test_planta_sin_espacios_y_niveles_repetidos():
	entorno, _planta, _salon, _cocina = piso_minimo()
	vacia = Planta(id="pla-99", nombre="Azotea", nivel=0)
	entorno.plantas.append(vacia)
	avisos = validar(entorno)
	assert _codigos(avisos) == ["nivel_repetido", "nivel_repetido", "planta_sin_espacios"]
	sin = _el(avisos, "planta_sin_espacios")
	assert (sin.elemento_id, sin.planta_id, sin.gravedad) == ("pla-99", "pla-99", "aviso")
	assert "Azotea" in sin.mensaje


def test_ids_duplicados_y_vacios():
	entorno, planta, salon, cocina = piso_minimo()
	cocina.id = salon.id
	planta.aberturas[0].id = ""
	avisos = validar(entorno)
	assert _codigos(avisos) == ["id_duplicado", "id_vacio"]
	assert _el(avisos, "id_duplicado").elemento_id == salon.id
	assert all(a.es_error for a in avisos)


def test_contornos_no_validos():
	entorno, planta, _salon, _cocina = piso_minimo()
	planta.espacios.append(Espacio(id="e1", nombre="Dos puntos", contorno=[(20, 0), (21, 0)]))
	planta.espacios.append(Espacio(id="e2", nombre="Lazo", contorno=[(30, 0), (32, 2), (32, 0), (30, 2)]))
	planta.espacios.append(Espacio(id="e3", nombre="Plano", contorno=[(40, 0), (41, 0), (42, 0)]))
	planta.zonas.append(ZonaSuelo(id="z1", nombre="Zona rota", contorno=[(1, 1)]))
	avisos = validar(entorno)
	assert _codigos(avisos) == ["contorno_no_valido"] * 4
	assert {a.elemento_id for a in avisos} == {"e1", "e2", "e3", "z1"}
	assert all(a.es_error and a.planta_id == planta.id for a in avisos)
	textos = " ".join(a.mensaje for a in avisos)
	assert "menos de tres vértices" in textos
	assert "se corta a sí mismo" in textos
	assert "no encierra superficie" in textos


def test_espacio_cerrado_sin_ninguna_abertura():
	entorno, planta, _salon, _cocina = piso_minimo()
	trastero = ed.crear_habitacion_rectangular(entorno, planta, "Trastero", 20, 0, 2, 2)
	avisos = validar(entorno)
	assert _codigos(avisos) == ["espacio_sin_acceso"]
	assert (avisos[0].elemento_id, avisos[0].gravedad) == (trastero.id, "aviso")
	assert "Trastero" in avisos[0].mensaje
	assert "macizo" in avisos[0].sugerencia
	# Una ventana no es un acceso…
	ventana = ed.anadir_puerta(entorno, planta, trastero, "sur", tipo="ventana")
	assert _codigos(validar(entorno)) == ["espacio_sin_acceso"]
	# …una puerta, aunque esté cerrada con llave, sí lo es.
	ventana.tipo, ventana.estado = "puerta", "con_llave"
	assert validar(entorno) == []
	planta.aberturas.remove(ventana)
	trastero.lados_abiertos = [0]
	assert validar(entorno) == []
	trastero.lados_abiertos = []
	trastero.macizo = True
	assert validar(entorno) == []


def test_un_conector_cuenta_como_acceso():
	entorno, baja, _salon, _cocina = piso_minimo()
	alta = ed.crear_planta(entorno, "Primera")
	ed.crear_habitacion_rectangular(entorno, alta, "Buhardilla", 0, 0, 5, 4)
	assert _codigos(validar(entorno)) == ["espacio_sin_acceso"]
	ed.crear_escalera(entorno, baja, alta, (1, 1), 0, 2, 10)
	assert validar(entorno) == []


def test_aberturas_que_no_caen_sobre_ninguna_pared():
	entorno, planta, salon, _cocina = piso_minimo()
	planta.aberturas.append(Abertura(id="abe-x", nombre="Puerta perdida", a=(2, 2), b=(2.8, 2)))
	planta.aberturas.append(Abertura(id="abe-y", nombre="Puerta sin ancho", a=(1, 0), b=(1, 0)))
	planta.aberturas.append(Abertura(id="abe-z", nombre="Gatera", a=(1, 0), b=(1.4, 0)))
	planta.aberturas.append(Abertura(id="abe-w", nombre="Rara", a=(3, 0), b=(4, 0), tipo="trampilla", estado="rota", hoja="doble"))
	avisos = validar(entorno)
	assert _codigos(avisos) == [
		"abertura_estrecha",
		"abertura_no_valida",
		"abertura_sin_pared",
		"valor_desconocido",
		"valor_desconocido",
		"valor_desconocido",
	]
	assert _el(avisos, "abertura_sin_pared").elemento_id == "abe-x"
	assert _el(avisos, "abertura_sin_pared").es_error
	assert _el(avisos, "abertura_no_valida").elemento_id == "abe-y"
	assert "0,40" in _el(avisos, "abertura_estrecha").mensaje
	assert salon.nombre == "Salón"


def test_aberturas_sobre_pared_suelta_y_sobre_edificio_macizo_valen():
	entorno = ed.crear_entorno("x")
	planta = ed.crear_planta(entorno, exterior=True)
	ed.crear_espacio_poligonal(entorno, planta, "Plaza", [(0, 0), (30, 0), (30, 20), (0, 20)], tipo="plaza")
	ed.crear_edificio(entorno, planta, "Bloque", 5, 10, 10, 8, portal_lado="sur")
	ed.anadir_pared(entorno, planta, (20, 2), (20, 8), nombre="Valla")
	planta.aberturas.append(Abertura(id="abe-v", nombre="Cancela", tipo="puerta", a=(20, 4), b=(20, 5)))
	ed.fijar_inicio(entorno, planta, 2, 2)
	assert validar(entorno) == []
	planta.paredes.append(Pared(id="par-0", nombre="Punto", a=(1, 1), b=(1, 1)))
	assert _codigos(validar(entorno)) == ["pared_no_valida"]


def test_valores_desconocidos_y_lados_abiertos_inexistentes():
	entorno, _planta, salon, cocina = piso_minimo()
	salon.suelo = "lava"
	salon.acustica = "catedral"
	cocina.tipo = "mazmorra"
	cocina.lados_abiertos = [7]
	avisos = validar(entorno)
	assert _codigos(avisos) == ["lado_abierto_inexistente", "valor_desconocido", "valor_desconocido", "valor_desconocido"]
	assert not hay_errores(avisos)


def test_espacios_con_paredes_que_se_pisan():
	entorno, planta, salon, _cocina = piso_minimo()
	encima = Espacio(id="esp-x", nombre="Encima", contorno=[(3, 2), (4.5, 2), (4.5, 3.5), (3, 3.5)], lados_abiertos=[0])
	planta.espacios.append(encima)
	avisos = validar(entorno)
	assert _codigos(avisos) == ["espacios_solapados"]
	assert "Salón" in avisos[0].mensaje
	assert "Encima" in avisos[0].mensaje
	# Las zonas sin paredes (un paso de peatones sobre la calzada) pueden solaparse.
	encima.cerrado = False
	assert validar(entorno) == []
	assert salon.cerrado


def test_conectores_hacia_plantas_inexistentes_o_fuera_de_un_espacio():
	entorno, baja, _salon, _cocina = piso_minimo()
	alta = ed.crear_planta(entorno, "Primera")
	rellano = ed.crear_habitacion_rectangular(entorno, alta, "Rellano", 0, 0, 5, 4)
	ed.anadir_puerta(entorno, alta, rellano, "sur")
	escalera = ed.crear_escalera(entorno, baja, alta, (1, 1), 0, 2, 10, nombre="Escalera")
	assert validar(entorno) == []
	escalera.tramos[0].hasta.planta = "pla-fantasma"
	avisos = validar(entorno)
	assert _codigos(avisos) == ["conector_planta_inexistente"]
	assert (avisos[0].elemento_id, avisos[0].gravedad) == (escalera.id, "error")
	assert "pla-fantasma" in avisos[0].mensaje
	assert "arriba" in avisos[0].mensaje
	escalera.tramos[0].hasta.planta = alta.id
	escalera.tramos[0].desde.x = 99
	avisos = validar(entorno)
	assert _codigos(avisos) == ["conector_fuera_de_espacio"]
	assert avisos[0].planta_id == baja.id
	assert "abajo" in avisos[0].mensaje
	escalera.tramos[0].desde.x = 1
	escalera.tramos[0].hasta.planta = baja.id
	escalera.tramos[0].longitud_m = 0
	escalera.tramos[0].peldanos = 0
	escalera.tipo = "escalera"
	assert _codigos(validar(entorno)) == ["conector_incompleto", "conector_misma_planta", "escalera_sin_peldanos"]


def test_conectores_incompletos_y_ascensores():
	entorno, baja, _salon, _cocina = piso_minimo()
	entorno.conectores.append(Conector(id="con-a", nombre="Escalera vacía", tipo="escalera"))
	entorno.conectores.append(
		Conector(id="con-b", nombre="Ascensor corto", tipo="ascensor", paradas=[Parada(baja.id, Posicion(baja.id, 1, 1, 0))])
	)
	entorno.conectores.append(
		Conector(
			id="con-c",
			nombre="Ascensor perdido",
			tipo="ascensor",
			paradas=[Parada(baja.id, Posicion(baja.id, 50, 50, 0)), Parada("pla-no", Posicion("pla-no", 1, 1, 0))],
		)
	)
	entorno.conectores.append(
		Conector(
			id="con-d",
			nombre="Teletransporte",
			tipo="teletransporte",
			tramos=[Tramo(Posicion(baja.id, 1, 1), Posicion(baja.id, 2, 2), 1.0, 0)],
		)
	)
	avisos = validar(entorno)
	assert _codigos(avisos) == [
		"conector_fuera_de_espacio",
		"conector_incompleto",
		"conector_incompleto",
		"conector_misma_planta",
		"conector_planta_inexistente",
		"valor_desconocido",
	]
	assert {a.elemento_id for a in avisos if a.codigo == "conector_incompleto"} == {"con-a", "con-b"}


def test_extremo_de_conector_dentro_de_un_macizo():
	entorno, baja, _salon, _cocina = piso_minimo()
	alta = ed.crear_planta(entorno, "Primera")
	ed.crear_manzana(entorno, alta, "Bloque", [(0, 0), (5, 0), (5, 4), (0, 4)])
	ed.crear_escalera(entorno, baja, alta, (1, 1), 0, 2, 10)
	assert "conector_fuera_de_espacio" in _codigos(validar(entorno))


def test_objetos_fuera_solapados_y_tapando_puertas(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	entorno, planta, _salon, _cocina = piso_minimo()
	fuera = catalogo.crear_objeto("prueba/mesa", 40, 40)
	fuera.id = "obj-fuera"
	atravesada = catalogo.crear_objeto("prueba/mesa", 0.2, 3.0)
	atravesada.id = "obj-pared"
	uno = catalogo.crear_objeto("prueba/mesa", 2.0, 1.0)
	uno.id = "obj-uno"
	dos = catalogo.crear_objeto("prueba/silla", 2.2, 1.1)
	dos.id = "obj-dos"
	tapon = catalogo.crear_objeto("prueba/armario", 4.7, 2.0, 270)
	tapon.id = "obj-tapon"
	planta.objetos.extend([fuera, atravesada, uno, dos, tapon])
	entorno.complementos.append("prueba")
	ed.fijar_inicio(entorno, planta, 6.5, 2.0)
	avisos = validar(entorno, catalogo)
	por_objeto = {
		identificador: {a.codigo for a in avisos if a.elemento_id == identificador}
		for identificador in ("obj-fuera", "obj-pared", "obj-uno", "obj-dos", "obj-tapon")
	}
	assert por_objeto["obj-fuera"] == {"fuera_de_espacio"}
	assert "no_cabe" in por_objeto["obj-pared"]
	assert "solapa_objeto" in por_objeto["obj-uno"]
	assert "solapa_objeto" in por_objeto["obj-dos"]
	assert "tapa_abertura" in por_objeto["obj-tapon"]
	assert all(a.planta_id == planta.id for a in avisos)
	assert _el(avisos, "tapa_abertura").gravedad == "aviso"
	assert _el(avisos, "fuera_de_espacio").gravedad == "error"


def test_paso_minimo_configurable_en_la_validacion(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	entorno, planta, _salon, _cocina = piso_minimo()
	co.colocar_en_punto(entorno, planta, "prueba/mesa", catalogo, 1.5, 2.0)
	co.colocar_en_punto(entorno, planta, "prueba/mesa", catalogo, 3.3, 2.0)
	ed.fijar_inicio(entorno, planta, 6.5, 2.0)
	# Entre las dos mesas quedan 0,60 m.
	assert _codigos(validar(entorno, catalogo)) == ["paso_estrecho", "paso_estrecho"]
	assert validar(entorno, catalogo, paso_minimo=0.6) == []
	assert len(validar(entorno, catalogo, paso_minimo=1.5)) >= 2


def test_tipos_no_instalados_se_avisan_y_se_tratan_como_cajas(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	entorno, planta, _salon, _cocina = piso_minimo()
	vitrina = Objeto(id="obj-v", nombre="Vitrina", tipo="museo/vitrina", x=2, y=3.75, ancho=2, fondo=0.5, alto=1.5)
	caja = Objeto(id="obj-c", nombre="Caja", tipo="caja", x=0.25, y=0.25, ancho=0.5, fondo=0.5)
	planta.objetos.extend([vitrina, caja])
	avisos = validar(entorno, catalogo)
	assert _codigos(avisos) == ["tipo_no_instalado"]
	assert avisos[0].elemento_id == "obj-v"
	assert "museo/vitrina" in avisos[0].mensaje
	assert not avisos[0].es_error
	# Sin catálogo no se sabe qué está instalado: no se avisa, pero la geometría se comprueba igual.
	assert validar(entorno) == []
	vitrina.y = 3.9
	assert "no_cabe" in _codigos(validar(entorno))


def test_inicio_no_valido():
	entorno, planta, _salon, _cocina = piso_minimo()
	entorno.inicio = Posicion("pla-no", 1, 1, 0)
	avisos = validar(entorno)
	assert _codigos(avisos) == ["inicio_no_valido"]
	assert avisos[0].es_error
	ed.fijar_inicio(entorno, planta, 40, 40)
	avisos = validar(entorno)
	assert _codigos(avisos) == ["inicio_fuera"]
	assert (avisos[0].planta_id, avisos[0].gravedad) == (planta.id, "error")


def test_inicio_dentro_de_un_muro_o_de_un_objeto(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	entorno, planta, _salon, _cocina = piso_minimo()
	# Sobre la pared que separa salón y cocina (fuera del hueco de la puerta).
	ed.fijar_inicio(entorno, planta, 5.0, 0.8)
	avisos = validar(entorno)
	assert _codigos(avisos) == ["inicio_en_muro"]
	assert avisos[0].es_error
	ed.fijar_inicio(entorno, planta, 0.1, 2.0)
	assert _codigos(validar(entorno)) == ["inicio_en_muro"]
	# En el hueco de la puerta abierta sí se puede empezar.
	ed.fijar_inicio(entorno, planta, 5.0, 2.0)
	assert validar(entorno) == []
	# Si la puerta está cerrada, es empezar dentro de la hoja.
	planta.aberturas[0].estado = "cerrada"
	assert _codigos(validar(entorno)) == ["inicio_en_muro"]
	planta.aberturas[0].estado = "abierta"
	ed.crear_manzana(entorno, planta, "Columna", [(20, 0), (22, 0), (22, 2), (20, 2)])
	ed.fijar_inicio(entorno, planta, 21, 1)
	avisos = validar(entorno)
	assert _codigos(avisos) == ["inicio_en_muro"]
	assert "Columna" in avisos[0].mensaje
	ed.fijar_inicio(entorno, planta, 2.5, 2.0)
	co.colocar_en_punto(entorno, planta, "prueba/mesa", catalogo, 2.5, 2.0)
	avisos = validar(entorno, catalogo)
	assert _codigos(avisos) == ["inicio_en_objeto"]
	assert "Mesa" in avisos[0].mensaje
	# Sobre una alfombra, que no corta el paso, se puede empezar.
	planta.objetos.clear()
	co.colocar_en_punto(entorno, planta, "prueba/alfombra", catalogo, 2.5, 2.0)
	assert validar(entorno, catalogo) == []


def test_fuentes_de_sonido():
	entorno, planta, _salon, _cocina = piso_minimo()
	planta.fuentes.append(FuenteSonido(id="fue-a", nombre="Muda", x=1, y=1, sonido="  "))
	planta.fuentes.append(FuenteSonido(id="fue-b", nombre="Lejana", x=60, y=60, sonido="campana"))
	planta.fuentes.append(FuenteSonido(id="fue-c", nombre="Sin radio", x=2, y=1, sonido="reloj", radio=0))
	# El validador solo mira que haya nombre de sonido: que el fichero exista lo comprueba el banco de sonidos.
	planta.fuentes.append(FuenteSonido(id="fue-d", nombre="Inventada", x=3, y=1, sonido="sonido_que_no_existe"))
	avisos = validar(entorno)
	assert _codigos(avisos) == ["fuente_fuera", "radio_no_valido", "sonido_vacio"]
	assert _el(avisos, "sonido_vacio").es_error
	assert _el(avisos, "sonido_vacio").elemento_id == "fue-a"
	assert not _el(avisos, "fuente_fuera").es_error


def test_vias_no_validas():
	entorno, planta, _salon, _cocina = piso_minimo()
	planta.vias.append(Via(id="via-a", nombre="Punto", eje=[(0, 0)]))
	planta.vias.append(Via(id="via-b", nombre="Sin ancho", eje=[(0, 0), (10, 0)], ancho=0))
	planta.vias.append(Via(id="via-c", nombre="Buena", eje=[(0, 0), (10, 0)]))
	avisos = validar(entorno)
	assert _codigos(avisos) == ["via_no_valida", "via_no_valida"]
	assert {a.elemento_id for a in avisos} == {"via-a", "via-b"}


def test_validar_no_modifica_el_entorno(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	entorno, planta, _salon, _cocina = piso_minimo()
	planta.objetos.append(Objeto(id="obj-x", nombre="Fuera", x=90, y=90))
	planta.aberturas.append(Abertura(id="abe-x", a=(2, 2), b=(3, 2)))
	antes = entorno.a_dict()
	validar(entorno, catalogo)
	assert entorno.a_dict() == antes


def test_resumen():
	error = Aviso("error", "x", "Mal.")
	leve = Aviso("aviso", "y", "Regular.")
	assert resumen([error]) == "1 error y 0 avisos."
	assert resumen([error, error, leve]) == "2 errores y 1 aviso."
