"""Paquetes de sonidos: estructura, herencia, igualado, cambio en caliente y los dos paquetes que viajan con el programa.

Nada suena: los motores son el nulo y OpenAL en memoria, y los paquetes de prueba se escriben en
carpetas temporales. Las pruebas del paquete «Natural» miden los ficheros que hay en
``data/sounds/natural`` (se saltan si no está generado).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pytest

from app.audio import niveles, paquetes, sintesis
from app.audio.banco import NOMBRE_FICHA, PAQUETE_POR_DEFECTO, PREFIJO_MUESTRA, Banco, leer_ficha
from app.audio.base import FRECUENCIA
from app.audio.motor_nulo import MotorNulo
from app.audio.presentador import Presentador
from app.core import paths
from app.core.configuracion import Configuracion

SONIDOS_DE_SERIE = paths.ruta_base() / "data" / "sounds"
NATURAL = SONIDOS_DE_SERIE / "natural"
# Parte mínima de la energía por encima de 3 kHz en un sonido que hay que situar (la misma que en la síntesis).
MINIMO_AGUDOS = 0.02


def _tono(frecuencia: float, segundos: float = 0.5, nivel: float = 0.3) -> np.ndarray:
	"""Un tono con un número entero de ciclos: sirve de bucle sin costura."""
	ciclos = max(1, round(frecuencia * segundos))
	muestras = int(round(ciclos * FRECUENCIA / frecuencia))
	t = np.arange(muestras) / FRECUENCIA
	return (np.sin(2 * np.pi * frecuencia * t) * nivel).astype(np.float32)


def _escribir(ruta, datos: np.ndarray) -> None:
	ruta.parent.mkdir(parents=True, exist_ok=True)
	sintesis.escribir_audio(ruta, datos)


def _ficha(carpeta, **datos) -> None:
	carpeta.mkdir(parents=True, exist_ok=True)
	(carpeta / NOMBRE_FICHA).write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def sonidos(tmp_path):
	"""Una carpeta de sonidos con el paquete por defecto (dos sonidos) y un paquete parcial que cambia uno."""
	raiz = tmp_path / "sounds"
	_escribir(raiz / "por_defecto" / "fuente" / "frigorifico.wav", _tono(400, 1.0, 0.2))
	_escribir(raiz / "por_defecto" / "puerta" / "abrir.wav", _tono(500, 0.2, 0.3))
	_ficha(raiz / "por_defecto", id="por_defecto", nombre="De serie")
	# El paquete «fuerte» trae el frigorífico a otra nota y cuatro veces más alto.
	_escribir(raiz / "fuerte" / "fuente" / "frigorifico.wav", _tono(1600, 1.0, 0.8))
	_ficha(raiz / "fuerte", id="fuerte", nombre="Fuerte", descripcion="Para las pruebas", autor="Pruebas", licencia="CC0", version="2")
	return raiz


def _banco(raiz, **opciones) -> Banco:
	return Banco(carpetas_sonidos=[raiz], carpetas_complementos=[], **opciones)


def _nota(datos: np.ndarray) -> float:
	return niveles.pico_espectral(datos, FRECUENCIA, 100.0, 5000.0)


# ── Estructura y listado ─────────────────────────────────────────────────────


def test_listado_de_paquetes_con_el_de_por_defecto_primero(sonidos):
	banco = _banco(sonidos)
	lista = banco.paquetes_disponibles()
	assert [paquete["id"] for paquete in lista] == ["por_defecto", "fuerte"]
	defecto, fuerte = lista
	assert defecto["defecto"] and defecto["actual"] and defecto["nombre"] == "De serie"
	assert (fuerte["nombre"], fuerte["descripcion"], fuerte["autor"], fuerte["licencia"], fuerte["version"]) == (
		"Fuerte",
		"Para las pruebas",
		"Pruebas",
		"CC0",
		"2",
	)
	assert fuerte["sonidos"] == 1 and fuerte["total"] == len(sintesis.nombres())
	assert fuerte["parcial"] and not fuerte["completo"] and not fuerte["actual"]
	assert set(fuerte) >= {
		"id",
		"nombre",
		"descripcion",
		"sonidos",
		"total",
		"completo",
		"parcial",
		"defecto",
		"actual",
		"carpeta",
		"generado",
	}
	assert paquetes.listar(banco) == lista
	frase = paquetes.describir(fuerte)
	assert "Fuerte" in frase and "1" in frase


def test_una_carpeta_cualquiera_no_es_un_paquete(sonidos):
	(sonidos / "notas").mkdir()
	(sonidos / "notas" / "leeme.txt").write_text("nada", encoding="utf-8")
	_escribir(sonidos / "Con Espacios" / "puerta" / "abrir.wav", _tono(300, 0.1))
	_escribir(sonidos / "otros" / "no_es_del_catalogo.wav", _tono(300, 0.1))
	assert [paquete["id"] for paquete in _banco(sonidos).paquetes_disponibles()] == ["por_defecto", "fuerte"]


def test_el_paquete_por_defecto_existe_aunque_falte_su_carpeta(tmp_path):
	"""Sin ningún fichero, el de por defecto sigue en la lista (sus sonidos se sintetizan) y los sueltos de antes siguen valiendo."""
	_escribir(tmp_path / "puerta" / "abrir.wav", _tono(321, 0.2))  # instalación anterior a los paquetes
	banco = _banco(tmp_path)
	lista = banco.paquetes_disponibles()
	assert [(paquete["id"], paquete["sonidos"], paquete["defecto"], paquete["actual"]) for paquete in lista] == [
		("por_defecto", 0, True, True)
	]
	assert lista[0]["nombre"]
	assert banco.origen("puerta/abrir") == "serie" and _nota(banco.sonido("puerta/abrir").datos) == pytest.approx(321, abs=5)
	assert banco.origen("baliza/pulso") == "sintetizado"


def test_los_paquetes_que_viajan_con_el_programa():
	"""``data/sounds``: catálogo común en la raíz y una carpeta por paquete, con su ficha y sus créditos."""
	if not (SONIDOS_DE_SERIE / "catalogo.json").is_file():
		pytest.skip("los sonidos de serie no están generados (tools/sintetizar_sonidos.py)")
	defecto = SONIDOS_DE_SERIE / PAQUETE_POR_DEFECTO
	assert (defecto / NOMBRE_FICHA).is_file() and (defecto / "CREDITOS.txt").is_file() and (defecto / niveles.NOMBRE_NIVELES).is_file()
	assert (SONIDOS_DE_SERIE / "LEEME.md").is_file()
	# Ningún sonido queda suelto en la raíz: todos están dentro de un paquete.
	assert not [ruta for ruta in SONIDOS_DE_SERIE.iterdir() if ruta.suffix.lower() in (".flac", ".ogg", ".wav")]
	lista = paquetes.listar(Banco(carpetas_complementos=[]))
	assert lista[0]["id"] == PAQUETE_POR_DEFECTO and lista[0]["completo"] and lista[0]["sonidos"] == len(sintesis.nombres())
	for paquete in lista:
		carpeta = SONIDOS_DE_SERIE / paquete["id"]
		if not carpeta.is_dir():
			continue  # un paquete del usuario, de la carpeta de datos
		ficha = leer_ficha(carpeta)
		for clave in ("id", "nombre", "descripcion", "autor", "licencia", "version", "generado"):
			assert ficha.get(clave), f"A la ficha de {paquete['id']} le falta «{clave}»"
		assert ficha["id"] == paquete["id"]
		assert (carpeta / "CREDITOS.txt").is_file(), paquete["id"]
	referencias = niveles.leer_niveles(defecto)
	assert set(referencias) == set(sintesis.nombres())
	muestra = sintesis.leer_audio(defecto / "baliza" / "pulso.flac")[0]
	assert referencias["baliza/pulso"][0] == pytest.approx(niveles.nivel(muestra), rel=1e-3)


def test_todos_los_sonidos_del_catalogo_resuelven_en_cada_paquete():
	if not (SONIDOS_DE_SERIE / "catalogo.json").is_file():
		pytest.skip("los sonidos de serie no están generados (tools/sintetizar_sonidos.py)")
	disponibles = [paquete["id"] for paquete in Banco(carpetas_sonidos=[SONIDOS_DE_SERIE], carpetas_complementos=[]).paquetes_disponibles()]
	assert PAQUETE_POR_DEFECTO in disponibles
	for identificador in disponibles:
		banco = Banco(carpetas_sonidos=[SONIDOS_DE_SERIE], carpetas_complementos=[], paquete=identificador)
		assert banco.paquete_actual() == identificador
		heredados = set(leer_ficha(SONIDOS_DE_SERIE / identificador).get("heredados") or [])
		for nombre in sintesis.nombres():
			encontrado = banco.sonido(nombre)
			assert encontrado.origen in ("serie", "paquete"), f"{identificador}: {nombre} sale de «{encontrado.origen}»"
			if identificador != PAQUETE_POR_DEFECTO and nombre not in heredados:
				assert encontrado.origen == "paquete" and encontrado.paquete == identificador, f"{identificador} no trae {nombre}"
			assert len(encontrado.datos) > 100 and encontrado.frecuencia == FRECUENCIA
		assert banco.sonido("pasos/baldosa").origen in ("serie", "paquete")  # los nombres genéricos también


# ── Herencia ─────────────────────────────────────────────────────────────────


def test_lo_que_el_paquete_no_trae_se_hereda_del_de_por_defecto(sonidos):
	banco = _banco(sonidos, paquete="fuerte")
	suyo = banco.sonido("fuente/frigorifico")
	assert (suyo.origen, suyo.paquete) == ("paquete", "fuerte")
	assert suyo.ruta == sonidos / "fuerte" / "fuente" / "frigorifico.wav"
	assert _nota(suyo.datos) == pytest.approx(1600, abs=5)
	heredado = banco.sonido("puerta/abrir")
	assert (heredado.origen, heredado.paquete) == ("serie", "por_defecto")
	assert _nota(heredado.datos) == pytest.approx(500, abs=5)
	# Ni en uno ni en otro, pero es de serie: se sintetiza. Y lo que no existe, reserva.
	assert banco.origen("baliza/pulso") == "sintetizado"
	assert banco.origen("no/existe") == "reserva"
	assert banco.existe("fuente/frigorifico") and not banco.existe("no/existe")


def test_el_entorno_y_los_complementos_mandan_sobre_el_paquete(sonidos, tmp_path):
	import io

	import soundfile

	memoria = io.BytesIO()
	soundfile.write(memoria, _tono(2000, 0.2), FRECUENCIA, format="WAV")
	_escribir(tmp_path / "plugins" / "cocina" / "sonidos" / "microondas.wav", _tono(700, 0.2))
	banco = Banco(
		lambda nombre: memoria.getvalue() if nombre == "sonidos/fuente/frigorifico.wav" else None,
		carpetas_sonidos=[sonidos],
		carpetas_complementos=[tmp_path / "plugins"],
		paquete="fuerte",
	)
	assert banco.origen("fuente/frigorifico") == "entorno"
	assert banco.origen("cocina/microondas") == "complemento"
	banco.poner_entorno(None)
	assert banco.origen("fuente/frigorifico") == "paquete"


def test_paquete_inexistente_deja_el_de_por_defecto(sonidos, caplog):
	banco = _banco(sonidos, paquete="fuerte")
	with caplog.at_level("WARNING"):
		assert banco.poner_paquete("no_esta") is False
	assert banco.paquete_actual() == PAQUETE_POR_DEFECTO
	assert "no_esta" in caplog.text
	assert banco.poner_paquete("../fuera") is False and banco.paquete_actual() == PAQUETE_POR_DEFECTO
	assert banco.poner_paquete("") is True  # vacío es el de por defecto
	assert banco.poner_paquete("fuerte") is True and banco.paquete_actual() == "fuerte"


def test_ficha_danada_no_rompe_nada(sonidos, caplog):
	(sonidos / "fuerte" / NOMBRE_FICHA).write_text("{esto no es json", encoding="utf-8")
	_escribir(sonidos / "lista" / "puerta" / "abrir.wav", _tono(900, 0.2))
	(sonidos / "lista" / NOMBRE_FICHA).write_text("[1, 2, 3]", encoding="utf-8")
	_escribir(sonidos / "raro" / "puerta" / "abrir.wav", _tono(900, 0.2, 0.3))
	_ficha(sonidos / "raro", nombre=7, igualar="quizá", volumenes={"puerta/abrir": "mucho"})
	(sonidos / "vacio").mkdir()
	(sonidos / "vacio" / NOMBRE_FICHA).write_bytes(b"\xff\xfe\x00")
	with caplog.at_level("WARNING"):
		banco = _banco(sonidos)
		lista = {paquete["id"]: paquete for paquete in banco.paquetes_disponibles()}
	assert set(lista) == {"por_defecto", "fuerte", "lista", "raro", "vacio"}
	assert lista["fuerte"]["nombre"] == "fuerte" and lista["lista"]["nombre"] == "lista"
	assert lista["raro"]["nombre"] == "7" and lista["vacio"]["sonidos"] == 0
	assert "pack.json" in caplog.text
	for identificador in ("fuerte", "lista", "raro", "vacio"):
		assert banco.poner_paquete(identificador) is True
		assert banco.sonido("puerta/abrir").origen in ("paquete", "serie")
		assert banco.sonido("fuente/frigorifico").origen in ("paquete", "serie")
	banco.poner_paquete("raro")
	assert banco.sonido("puerta/abrir").origen == "paquete"
	assert np.isfinite(banco.sonido("puerta/abrir").datos).all()


# ── Igualado y volumen por sonido ────────────────────────────────────────────


def test_igualado_lleva_el_paquete_al_nivel_del_de_serie(sonidos):
	de_serie = niveles.nivel(_banco(sonidos).sonido("fuente/frigorifico").datos)
	banco = _banco(sonidos, paquete="fuerte")
	igualado = banco.sonido("fuente/frigorifico")
	assert niveles.nivel(igualado.datos) == pytest.approx(de_serie, rel=0.02)
	assert igualado.ganancia == pytest.approx(0.25, rel=0.03)
	assert banco.referencia("fuente/frigorifico") == pytest.approx(de_serie, rel=0.01)
	# Sin igualado, el paquete suena como viene: cuatro veces más alto.
	crudo = _banco(sonidos, paquete="fuerte", igualar=False).sonido("fuente/frigorifico")
	assert niveles.nivel(crudo.datos) == pytest.approx(4 * de_serie, rel=0.02) and crudo.ganancia == 1.0
	# En caliente.
	banco.poner_igualado(False)
	assert niveles.nivel(banco.sonido("fuente/frigorifico").datos) == pytest.approx(4 * de_serie, rel=0.02)
	banco.poner_igualado(True)
	assert niveles.nivel(banco.sonido("fuente/frigorifico").datos) == pytest.approx(de_serie, rel=0.02)


def test_igualado_usa_niveles_json_y_respeta_la_ficha(sonidos):
	(sonidos / "por_defecto" / niveles.NOMBRE_NIVELES).write_text(
		json.dumps({"formato": 1, "niveles": {"fuente/frigorifico": [0.1, 0.2], "roto": "x"}}), encoding="utf-8"
	)
	banco = _banco(sonidos, paquete="fuerte")
	assert niveles.nivel(banco.sonido("fuente/frigorifico").datos) == pytest.approx(0.1, rel=0.02)
	# El autor del paquete puede pedir que no se iguale, o retocar un sonido suyo.
	_ficha(sonidos / "fuerte", nombre="Fuerte", igualar=False, volumenes={"fuente/frigorifico": 0.5})
	banco.vaciar()
	assert niveles.pico(banco.sonido("fuente/frigorifico").datos) == pytest.approx(0.4, abs=0.01)


def test_el_igualado_no_deja_recortar(sonidos):
	# Un sonido muy picudo: igualarlo por nivel lo llevaría por encima del techo.
	picudo = np.zeros(FRECUENCIA, dtype=np.float32)
	picudo[::4410] = 0.5
	_escribir(sonidos / "fuerte" / "fuente" / "frigorifico.wav", picudo)
	datos = _banco(sonidos, paquete="fuerte").sonido("fuente/frigorifico").datos
	assert niveles.pico(datos) <= niveles.TECHO_PICO + 1e-3


def test_volumen_por_sonido(sonidos):
	banco = _banco(sonidos)
	normal = niveles.nivel(banco.sonido("puerta/abrir").datos)
	avisos: list[str] = []
	banco.suscribir(avisos.append)
	assert banco.poner_volumen_sonido("puerta/abrir", 0.5) == 0.5
	assert avisos == ["volumenes"]
	assert niveles.nivel(banco.sonido("puerta/abrir").datos) == pytest.approx(0.5 * normal, rel=0.02)
	assert niveles.nivel(banco.sonido("fuente/frigorifico").datos) == pytest.approx(niveles.nivel(_tono(400, 1.0, 0.2)), rel=0.02)
	# Fuera de límites se acota; subir no deja recortar; volver a 1 quita el ajuste.
	assert banco.poner_volumen_sonido("puerta/abrir", 9) == niveles.AJUSTE_MAXIMO
	assert niveles.pico(banco.sonido("puerta/abrir").datos) <= 0.98 + 1e-3
	assert banco.poner_volumen_sonido("puerta/abrir", 0.0) == niveles.AJUSTE_MINIMO
	assert banco.poner_volumen_sonido("puerta/abrir", 1.0) == 1.0 and banco.volumenes == {}
	assert niveles.nivel(banco.sonido("puerta/abrir").datos) == pytest.approx(normal, rel=0.02)
	# Lo guardado puede venir estropeado: no cuenta.
	banco.poner_volumenes({"puerta/abrir": "alto", "fuente/frigorifico": True})
	assert banco.volumen_sonido("puerta/abrir") == 1.0 and banco.volumen_sonido("fuente/frigorifico") == 1.0


def test_medidas_de_niveles():
	tono = _tono(1000, 1.0, 0.5)
	assert niveles.nivel(tono) == pytest.approx(0.5 / np.sqrt(2), rel=0.01)
	# Un golpe con silencio alrededor mide lo mismo que el golpe solo: cuenta su tramo más fuerte.
	con_silencio = np.concatenate([np.zeros(FRECUENCIA, np.float32), tono[: int(0.3 * FRECUENCIA)], np.zeros(FRECUENCIA, np.float32)])
	assert niveles.nivel(con_silencio) == pytest.approx(niveles.nivel(tono), rel=0.05)
	assert niveles.nivel(np.zeros(0, np.float32)) == 0.0
	assert niveles.nivel(np.stack([tono, tono], axis=1)) == pytest.approx(niveles.nivel(tono), rel=0.01)
	assert niveles.igualar(np.zeros(100, np.float32), 0.3).max() == 0.0  # el silencio no se toca
	assert niveles.costura(tono) < 1.5  # un número entero de ciclos empalma
	assert niveles.costura(tono[: len(tono) - 11]) > 3.0  # cortado a destiempo, salta
	assert niveles.pico_espectral(tono) == pytest.approx(1000, abs=3)
	assert niveles.energia_en(tono, 1000) > 0.95 and niveles.energia_en(tono, 2000) < 0.01
	tres = np.zeros(int(0.4 * FRECUENCIA), np.float32)
	for k in range(3):
		inicio = int((0.02 + 0.09 * k) * FRECUENCIA)
		tres[inicio : inicio + 2205] += _tono(1400, 0.05, 0.5)[:2205] * np.exp(-np.arange(2205) / 600.0).astype(np.float32)
	assert niveles.golpes(tres) == 3
	assert (
		niveles.ajuste_valido("x") == 1.0
		and niveles.ajuste_valido(float("nan")) == 1.0
		and niveles.ajuste_valido(5) == niveles.AJUSTE_MAXIMO
	)
	ficha = niveles.medir(tono)
	assert ficha["duracion"] == pytest.approx(1.0, abs=0.01) and ficha["canales"] == 1 and ficha["pico"] == pytest.approx(0.5, abs=0.01)


# ── Cambio en caliente ───────────────────────────────────────────────────────


@dataclass
class FuenteActiva:
	id: str
	sonido: str
	pos: tuple
	volumen: float = 1.0
	tono: float = 1.0
	filtro: float = 0.0
	bucle: bool = True


class SesionFalsa:
	def __init__(self) -> None:
		self.lista: list[FuenteActiva] = []

	def oyente(self):
		return (0.0, 0.0, 1.6, 0.0)

	def fuentes(self):
		return list(self.lista)


def _con_motor(raiz) -> tuple[Banco, MotorNulo]:
	banco = _banco(raiz)
	motor = MotorNulo()
	motor.iniciar(None, {})
	motor.resolver = banco.datos
	return banco, motor


def test_cambio_en_caliente_recarga_solo_lo_que_cambia(sonidos):
	banco, motor = _con_motor(sonidos)
	assert banco.precargar(motor, ["fuente/frigorifico"]) == 1
	assert motor.reproducir("puerta/abrir") > 0  # este lo trae el banco al pedirlo
	assert set(motor.sonidos_cargados()) == {"fuente/frigorifico", "puerta/abrir"}
	assert _nota(motor._sonidos["fuente/frigorifico"]) == pytest.approx(400, abs=5)
	avisos: list[str] = []
	cancelar = banco.suscribir(avisos.append)
	motor.vaciar()
	assert banco.poner_paquete("fuerte") is True
	assert avisos == ["paquete"]
	assert banco.recargar_en(motor) == 1  # la puerta es la misma en los dos paquetes: no se toca
	assert [llamada["nombre"] for llamada in motor.de("cargar")] == ["fuente/frigorifico"]
	assert _nota(motor._sonidos["fuente/frigorifico"]) == pytest.approx(1600, abs=5)
	assert _nota(motor._sonidos["puerta/abrir"]) == pytest.approx(500, abs=5)
	assert banco.recargar_en(motor) == 0  # ya está al día
	# De vuelta al de por defecto, y sin aviso si se pide el que ya está.
	assert banco.poner_paquete("fuerte") is True and avisos == ["paquete"]
	banco.poner_paquete(PAQUETE_POR_DEFECTO)
	assert banco.recargar_en(motor) == 1
	assert _nota(motor._sonidos["fuente/frigorifico"]) == pytest.approx(400, abs=5)
	assert banco.recargar_en(motor, forzar=True) == 2
	cancelar()
	banco.poner_paquete("fuerte")
	assert avisos == ["paquete", "paquete"]  # ya no estaba suscrito


def test_cambio_en_caliente_con_bucles_sonando_en_el_presentador(sonidos):
	"""El bucle pasa al sonido nuevo con un fundido y el juego sigue manejándolo por el mismo canal."""
	banco, motor = _con_motor(sonidos)
	presentador = Presentador(motor, banco=banco)
	sesion = SesionFalsa()
	sesion.lista = [FuenteActiva("nevera", "fuente/frigorifico", (3.0, 4.0, 1.0), volumen=0.7, filtro=0.4)]
	suelto = motor.reproducir("puerta/abrir", bus="ambiente", bucle=True, volumen=0.5)  # un bucle que no lleva el presentador
	presentador.aplicar([], sesion, 0.05)
	publico = presentador.fuentes_sonando()["nevera"]
	assert motor.suena(publico)
	antiguo = next(canal for canal in motor.canales_activos() if canal.id == publico)
	assert _nota(motor._sonidos["fuente/frigorifico"]) == pytest.approx(400, abs=5)

	banco.poner_paquete("fuerte")  # como si llegara de otro hilo: solo queda apuntado
	assert _nota(motor._sonidos["fuente/frigorifico"]) == pytest.approx(400, abs=5)
	presentador.aplicar([], sesion, 0.02)  # aquí se recarga, en el hilo del juego
	assert _nota(motor._sonidos["fuente/frigorifico"]) == pytest.approx(1600, abs=5)

	# Durante el fundido suenan los dos: el antiguo apagándose y el nuevo, en el mismo sitio y con lo mismo.
	del_frigorifico = [canal for canal in motor.canales_activos() if canal.nombre == "fuente/frigorifico"]
	assert len(del_frigorifico) == 2
	nuevo = next(canal for canal in del_frigorifico if canal.id != publico)
	assert antiguo.parando and not nuevo.parando
	assert (nuevo.pos, nuevo.volumen, nuevo.filtro, nuevo.bus, nuevo.bucle) == ((3.0, 4.0, 1.0), 0.7, 0.4, "ambiente", True)
	assert nuevo.ganancia < antiguo.ganancia  # entra desde el silencio
	# El presentador no ha vuelto a pedir la fuente: sigue con su número de canal, que ahora maneja el nuevo.
	assert presentador.fuentes_sonando()["nevera"] == publico and motor.suena(publico)
	assert len(motor.de("reproducir")) == 2  # la nevera y el bucle suelto, de antes del cambio
	# El bucle que no cambiaba de sonido ni se ha tocado.
	assert [canal.id for canal in motor.canales_activos() if canal.nombre == "puerta/abrir"] == [suelto]

	for _i in range(12):
		sesion.lista[0].pos = (5.0, 4.0, 1.0)
		sesion.lista[0].filtro = 0.9
		presentador.aplicar([], sesion, 0.05)
	activos = [canal for canal in motor.canales_activos() if canal.nombre == "fuente/frigorifico"]
	assert [canal.id for canal in activos] == [nuevo.id]  # el antiguo ya se apagó
	assert nuevo.pos == (5.0, 4.0, 1.0) and nuevo.filtro == 0.9 and nuevo.ganancia > 0.3  # se sigue moviendo por el canal de siempre
	assert presentador.fuentes_sonando()["nevera"] == publico

	# Un segundo cambio encadena el relevo, y parar por el número de siempre para el canal que suena ahora.
	banco.poner_paquete(PAQUETE_POR_DEFECTO)
	presentador.aplicar([], sesion, 0.05)
	assert motor.suena(publico)
	sesion.lista = []
	for _i in range(12):
		presentador.aplicar([], sesion, 0.05)
	assert not motor.suena(publico)
	assert not [canal for canal in motor.canales_activos() if canal.nombre == "fuente/frigorifico"]
	assert motor._relevos == {}
	presentador.cerrar()
	banco.poner_paquete("fuerte")
	assert presentador._recarga_pendiente is False  # al cerrar deja de escuchar al banco


def test_recargar_un_bucle_sin_fundido_y_sin_iniciar(sonidos):
	banco, motor = _con_motor(sonidos)
	canal = motor.reproducir("fuente/frigorifico", bucle=True, bus="ambiente")
	corto = motor.reproducir("fuente/frigorifico")  # el mismo sonido, sin bucle: termina con el antiguo
	assert motor.recargar_sonido("fuente/frigorifico", _tono(800, 0.5), FRECUENCIA, 0.0) == 1
	activos = [c for c in motor.canales_activos() if c.nombre == "fuente/frigorifico"]
	assert len(activos) == 2 and motor.suena(canal) and motor.suena(corto)
	motor.parar(canal)
	assert not motor.suena(canal) and motor.suena(corto)
	apagado = MotorNulo()
	assert apagado.recargar_sonido("x", _tono(800, 0.1)) == 0 and apagado.sonidos_cargados() == ["x"]


def test_cambio_en_caliente_con_openal_en_memoria(sonidos):
	"""Con el motor de verdad: el bucle pasa de una nota a la otra sin silencio en medio y sin cambiar de volumen."""
	from app.audio.motor_openal import MotorOpenAL

	hay, motivo = MotorOpenAL.disponible()
	if not hay:
		pytest.skip(f"OpenAL no está disponible: {motivo}")
	banco = _banco(sonidos)
	motor = MotorOpenAL()
	motor.iniciar(
		None, {"memoria": True, "proteccion": {"subida_maestro": 4.0, "techo_mezcla": 1.0}, "volumenes": {"maestro": 1.0, "ambiente": 1.0}}
	)
	motor.resolver = banco.datos
	presentador = Presentador(motor, banco=banco)
	paso = 0.02
	bloque = int(paso * FRECUENCIA)

	def avanzar(segundos: float) -> np.ndarray:
		trozos = []
		for _i in range(int(round(segundos / paso))):
			presentador.aplicar([], None, paso)
			trozos.append(motor.renderizar(bloque))
		return np.concatenate(trozos)[:, 0]

	try:
		canal = motor.reproducir("fuente/frigorifico", bus="ambiente", bucle=True, eco=False)
		assert canal > 0
		avanzar(1.0)  # que suban la ganancia maestra y la de la fuente
		antes = avanzar(0.5)
		assert _nota(antes) == pytest.approx(400, abs=10)
		nivel_antes = float(np.sqrt(np.mean(antes**2)))
		assert nivel_antes > 0.02

		banco.poner_paquete("fuerte")
		durante = avanzar(0.5)  # el fundido dura un cuarto de segundo
		bloques = [float(np.sqrt(np.mean(durante[i : i + bloque * 2] ** 2))) for i in range(0, len(durante) - bloque * 2, bloque * 2)]
		assert min(bloques) > 0.35 * nivel_antes, "hay un hueco de silencio en el cambio"
		assert max(np.abs(np.diff(durante))) < 0.25, "hay un chasquido en el cambio"

		despues = avanzar(0.5)
		assert _nota(despues) == pytest.approx(1600, abs=10)
		assert float(np.sqrt(np.mean(despues**2))) == pytest.approx(nivel_antes, rel=0.15)  # igualado: mismo volumen
		assert motor.suena(canal)
		motor.parar(canal)
		avanzar(0.1)
		assert not motor.suena(canal)
		assert float(np.sqrt(np.mean(avanzar(0.2) ** 2))) < 1e-3
	finally:
		presentador.cerrar()
		motor.cerrar()


# ── Paquete del usuario, configuración y muestra ─────────────────────────────


def test_paquete_del_usuario_en_la_carpeta_de_datos(data_temporal):
	"""Copiar una carpeta a ``data/sounds`` del usuario basta para tener un paquete nuevo."""
	if not (SONIDOS_DE_SERIE / PAQUETE_POR_DEFECTO).is_dir():
		pytest.skip("los sonidos de serie no están generados (tools/sintetizar_sonidos.py)")
	propio = paths.ruta_datos() / "sounds" / "mi_casa"
	assert SONIDOS_DE_SERIE not in propio.parents  # es la carpeta temporal de las pruebas, no la del programa
	_escribir(propio / "puerta" / "abrir.wav", _tono(1234, 0.3, 0.9))
	_ficha(propio, nombre="Mi casa", descripcion="La puerta de verdad", autor="Yo", licencia="CC0")
	banco = Banco(carpetas_complementos=[])
	lista = {paquete["id"]: paquete for paquete in banco.paquetes_disponibles()}
	assert lista["mi_casa"]["nombre"] == "Mi casa" and lista["mi_casa"]["sonidos"] == 1 and lista["mi_casa"]["parcial"]
	assert lista[PAQUETE_POR_DEFECTO]["completo"]
	assert banco.poner_paquete("mi_casa") is True
	puerta = banco.sonido("puerta/abrir")
	assert (puerta.origen, puerta.paquete) == ("paquete", "mi_casa") and _nota(puerta.datos) == pytest.approx(1234, abs=5)
	# Igualado con la referencia del programa, y el resto, heredado del paquete por defecto del programa.
	referencia = niveles.leer_niveles(SONIDOS_DE_SERIE / PAQUETE_POR_DEFECTO)["puerta/abrir"][0]
	assert niveles.nivel(puerta.datos) == pytest.approx(referencia, rel=0.03)
	assert banco.sonido("baliza/pulso").origen == "serie"


def test_la_configuracion_trae_el_paquete_y_se_valida(tmp_path):
	config = Configuracion(tmp_path / "config.json")
	assert config.obtener("sonido.paquete") == "por_defecto"
	assert config.obtener("sonido.igualar_paquetes") is True
	assert config.obtener("sonido.volumen_sonidos") == {}
	from app.core.configuracion import ErrorValidacion

	for clave, valor in (
		("sonido.paquete", 3),
		("sonido.paquete", "x" * 65),
		("sonido.igualar_paquetes", "sí"),
		("sonido.volumen_sonidos", []),
	):
		with pytest.raises(ErrorValidacion):
			config.establecer(clave, valor)
	config.establecer("sonido.paquete", "natural")
	assert Configuracion(tmp_path / "config.json").obtener("sonido.paquete") == "natural"


def test_elegir_en_la_configuracion_cambia_el_banco_en_caliente(sonidos, tmp_path):
	config = Configuracion(tmp_path / "config.json")
	config.establecer("sonido.paquete", "fuerte")
	config.establecer("sonido.volumen_sonidos", {"puerta/abrir": 0.5})
	banco, motor = _con_motor(sonidos)
	presentador = Presentador(motor, banco=banco)
	cancelar = paquetes.conectar(banco, config)
	# Al conectar se aplica lo guardado.
	assert banco.paquete_actual() == "fuerte" and banco.volumen_sonido("puerta/abrir") == 0.5
	assert paquetes.actual(config) == "fuerte"
	motor.reproducir("fuente/frigorifico", bucle=True, bus="ambiente")
	presentador.aplicar([], None, 0.05)
	assert _nota(motor._sonidos["fuente/frigorifico"]) == pytest.approx(1600, abs=5)

	# Elegir otro: se guarda, el banco cambia y el presentador recarga en su siguiente fotograma.
	assert paquetes.elegir("por_defecto", config, banco) is True
	assert config.obtener("sonido.paquete") == "por_defecto" and banco.paquete_actual() == "por_defecto"
	presentador.aplicar([], None, 0.05)
	assert _nota(motor._sonidos["fuente/frigorifico"]) == pytest.approx(400, abs=5)
	assert [paquete["id"] for paquete in paquetes.listar(banco) if paquete["actual"]] == ["por_defecto"]

	# Uno que no está: no se guarda ni se cambia.
	assert paquetes.elegir("no_esta", config, banco) is False
	assert config.obtener("sonido.paquete") == "por_defecto"
	# Si la configuración trae uno que ya no existe (otro equipo), queda el de por defecto sin fallar.
	config.establecer("sonido.paquete", "desinstalado")
	assert banco.paquete_actual() == "por_defecto"

	# Igualado y volumen por sonido, también en caliente.
	config.establecer("sonido.paquete", "fuerte")
	config.establecer("sonido.igualar_paquetes", False)
	assert banco.igualar is False
	assert paquetes.poner_volumen("puerta/abrir", 1.5, config) == 1.5
	assert banco.volumen_sonido("puerta/abrir") == 1.5 and config.obtener("sonido.volumen_sonidos") == {"puerta/abrir": 1.5}
	assert paquetes.poner_volumen("puerta/abrir", 1.0, config) == 1.0 and config.obtener("sonido.volumen_sonidos") == {}

	cancelar()
	config.establecer("sonido.paquete", "por_defecto")
	assert banco.paquete_actual() == "fuerte"  # desconectado: ya no sigue a la configuración


def test_escuchar_una_muestra_no_cambia_de_paquete(sonidos):
	banco, motor = _con_motor(sonidos)
	nombres = ("fuente/frigorifico", "puerta/abrir")
	de_serie, frecuencia = paquetes.muestra("por_defecto", banco, nombres)
	del_otro, _frecuencia = paquetes.muestra("fuerte", banco, nombres)
	assert frecuencia == FRECUENCIA and de_serie.ndim == 1 and del_otro.ndim == 1
	largo = len(_tono(400, 1.0))
	assert _nota(de_serie[:largo]) == pytest.approx(400, abs=5) and _nota(del_otro[:largo]) == pytest.approx(1600, abs=5)
	assert niveles.nivel(del_otro[:largo]) == pytest.approx(niveles.nivel(de_serie[:largo]), rel=0.05)  # la muestra va igualada
	# La puerta, que el paquete no trae, es la misma en las dos muestras.
	assert np.allclose(de_serie[-2000:], del_otro[-2000:], atol=1e-4)

	canal = paquetes.escuchar("fuerte", motor, banco, nombres)
	assert canal > 0 and motor.suena(canal)
	assert banco.paquete_actual() == PAQUETE_POR_DEFECTO
	pedido = motor.de("reproducir")[-1]
	assert (
		pedido["nombre"] == PREFIJO_MUESTRA + "fuerte" and pedido["bus"] == "interfaz" and pedido["pos"] is None and pedido["eco"] is False
	)
	# Pedir otra corta la anterior; y la muestra no se recarga al cambiar de paquete.
	otro = paquetes.escuchar("por_defecto", motor, banco, nombres)
	motor.tic(0.1)
	assert otro != canal and not motor.suena(canal) and motor.suena(otro)
	banco.poner_paquete("fuerte")
	assert banco.recargar_en(motor) == 0
	# Con la muestra de serie y un paquete que no existe: suena el de por defecto, no falla.
	assert len(paquetes.muestra("no_esta", banco)[0]) > FRECUENCIA // 2


# ── El paquete «Natural» ─────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def natural():
	"""Los sonidos del paquete Natural tal como están en disco (sin igualar): nombre → muestras."""
	if not (NATURAL / NOMBRE_FICHA).is_file():
		pytest.skip("el paquete Natural no está generado (tools/generar_paquete_sonidos.py)")
	leidos = {}
	for nombre in sintesis.nombres():
		ruta = sintesis.fichero_de(NATURAL, nombre)
		if ruta is not None:
			datos, frecuencia = sintesis.leer_audio(ruta)
			assert frecuencia == FRECUENCIA, nombre
			leidos[nombre] = datos
	return leidos


def test_natural_es_coherente_con_su_ficha_y_su_receta(natural):
	ficha = leer_ficha(NATURAL)
	heredados = set(ficha["heredados"])
	assert set(natural) | heredados == set(sintesis.nombres()) and not set(natural) & heredados
	assert ficha["sonidos"] == len(natural)
	assert len(natural) >= 0.9 * len(sintesis.nombres()), "el paquete Natural debería traer casi todos los sonidos"
	receta = json.loads((NATURAL / "receta.json").read_text(encoding="utf-8"))
	assert set(natural) <= set(receta["sonidos"])

	# Sin inteligencia artificial ni voces: solo capas del motor procedural del generador.
	def tipos(capas: list) -> set[str]:
		encontrados: set[str] = set()
		for capa in capas:
			encontrados.add(capa["tipo"])
			encontrados |= tipos(capa.get("capas", []))
		return encontrados

	for nombre, entrada in receta["sonidos"].items():
		usados = tipos(entrada["especificacion"]["capas"])
		assert usados <= {"sonido", "nota", "secuencia"}, f"{nombre} usa capas {usados}"
	medidas = json.loads((NATURAL / "medidas.json").read_text(encoding="utf-8"))["sonidos"]
	for nombre in natural:
		assert medidas[nombre]["en_el_paquete"], nombre
	creditos = (NATURAL / "CREDITOS.txt").read_text(encoding="utf-8")
	assert "inteligencia artificial" in creditos and "receta.json" in creditos


def test_natural_tiene_la_misma_forma_que_el_de_serie(natural):
	"""Canales, duración aproximada, picos prudentes y silencio en los bordes, como los sonidos de serie."""
	defecto = SONIDOS_DE_SERIE / PAQUETE_POR_DEFECTO
	for nombre, datos in natural.items():
		definicion = sintesis.CATALOGO[nombre]
		de_serie, _frecuencia = sintesis.leer_audio(sintesis.fichero_de(defecto, nombre))
		assert datos.ndim == de_serie.ndim, f"{nombre}: canales distintos de los de serie"
		assert np.isfinite(datos).all() and len(datos) > 100, nombre
		proporcion = len(datos) / len(de_serie)
		assert 0.5 <= proporcion <= 1.75, f"{nombre} dura {proporcion:.2f} veces lo que el de serie"
		assert niveles.pico(datos) <= 0.8 + 1e-3, nombre
		assert float(np.sqrt(np.mean(np.square(datos)))) > 0.005, f"{nombre} es casi silencio"
		assert abs(float(np.mean(datos))) < 0.01, f"{nombre} tiene componente continua"
		if definicion.bucle:
			assert len(datos) == pytest.approx(len(de_serie), abs=0.01 * FRECUENCIA), f"{nombre}: el bucle no dura lo mismo"
			assert niveles.costura(datos) <= 2.0, f"{nombre}: salto en la costura del bucle"
		else:
			assert float(np.max(np.abs(datos[0]))) < 0.01 and float(np.max(np.abs(datos[-1]))) < 0.01, (
				f"{nombre} no empieza o no acaba en silencio"
			)


def test_natural_lo_que_se_situa_es_mono_y_tiene_agudos(natural):
	pocos = {}
	for nombre, datos in natural.items():
		if not sintesis.CATALOGO[nombre].posicionable:
			continue
		assert datos.ndim == 1, f"{nombre} se sitúa en el espacio y no es mono"
		fraccion = sintesis.fraccion_agudos(datos)
		if fraccion < MINIMO_AGUDOS:
			pocos[nombre] = round(fraccion, 4)
	assert not pocos, f"Sin agudos por encima de 3 kHz no se distinguen delante y detrás: {pocos}"


def test_natural_esta_igualado_con_el_de_serie(natural):
	"""Al cargarlo, el banco apenas tiene que corregir nada: el paquete ya viene al nivel del de serie."""
	banco = Banco(carpetas_sonidos=[SONIDOS_DE_SERIE], carpetas_complementos=[], paquete="natural")
	referencias = niveles.leer_niveles(SONIDOS_DE_SERIE / PAQUETE_POR_DEFECTO)
	for nombre in natural:
		encontrado = banco.sonido(nombre)
		assert 0.7 <= encontrado.ganancia <= 1.3, f"{nombre}: el igualado lo cambia {encontrado.ganancia:.2f} veces"
		assert 0.7 * referencias[nombre][0] <= niveles.nivel(encontrado.datos) <= 1.05 * referencias[nombre][0], nombre


def test_natural_conserva_lo_que_los_avisos_codifican(natural):
	"""Mismas notas y mismo número de toques que de serie en los avisos que cuentan algo."""

	def nota_de(nombre: str) -> float:
		return niveles.pico_espectral(natural[nombre], FRECUENCIA, 150.0, 2500.0)

	def toques(nombre: str) -> int:
		return niveles.golpes(natural[nombre])

	presentes = set(natural)
	# Distancia del bastón: cuanto más cerca, más aguda y más veces.
	if {"sonda/cerca", "sonda/media", "sonda/lejos"} <= presentes:
		assert [toques(f"sonda/{clave}") for clave in ("cerca", "media", "lejos")] == [3, 2, 1]
		assert nota_de("sonda/cerca") == pytest.approx(1397, rel=0.02)
		assert nota_de("sonda/media") == pytest.approx(932, rel=0.02)
		assert nota_de("sonda/lejos") == pytest.approx(554, rel=0.02)
	# Brújula: norte agudo y solo, este dos, sur grave y solo, oeste tres.
	if {"brujula/norte", "brujula/este", "brujula/sur", "brujula/oeste"} <= presentes:
		assert [toques(f"brujula/{clave}") for clave in ("norte", "este", "sur", "oeste")] == [1, 2, 1, 3]
		assert nota_de("brujula/norte") == pytest.approx(1568, rel=0.02) and nota_de("brujula/sur") == pytest.approx(784, rel=0.02)
		assert nota_de("brujula/este") == pytest.approx(1174.7, rel=0.02) and nota_de("brujula/oeste") == pytest.approx(987.8, rel=0.02)
	# Plantas del ascensor: cada una, más aguda que la anterior, y en su nota.
	plantas = [f"ascensor/planta_{planta}" for planta in range(10)]
	if set(plantas) <= presentes:
		notas = [nota_de(nombre) for nombre in plantas]
		assert notas == sorted(notas) and len(set(notas)) == 10
		assert notas[0] == pytest.approx(523.25, rel=0.02) and notas[7] == pytest.approx(1046.5, rel=0.02)
	# Balizas: el pulso, el alineado más agudo, «cerca» dos pulsos y «llegada» cuatro notas.
	if {"baliza/pulso", "baliza/alineado", "baliza/cerca", "baliza/llegada", "baliza/detras"} <= presentes:
		assert nota_de("baliza/pulso") == pytest.approx(660, rel=0.02)
		assert nota_de("baliza/alineado") == pytest.approx(990, rel=0.02)
		assert toques("baliza/cerca") == 2 and toques("baliza/llegada") == 4 and toques("baliza/detras") == 2
	# Semáforo: cuatro píos por vuelta en verde y en intermitente (que dura la mitad), uno en rojo.
	if {"semaforo/verde", "semaforo/intermitente", "semaforo/rojo"} <= presentes:
		assert toques("semaforo/verde") == 4 and toques("semaforo/intermitente") == 4 and toques("semaforo/rojo") == 1
		assert len(natural["semaforo/intermitente"]) == pytest.approx(len(natural["semaforo/verde"]) / 2, rel=0.02)
	# Escalera y menús: la segunda nota sube o baja como de serie.
	for sube, baja in (("escalera/subir", "escalera/bajar"), ("interfaz/elegir", "interfaz/atras")):
		if {sube, baja} <= presentes:
			mitad_sube = len(natural[sube]) // 3
			mitad_baja = len(natural[baja]) // 3
			assert niveles.pico_espectral(natural[sube][mitad_sube:], minimo=300, maximo=2500) > niveles.pico_espectral(
				natural[sube][:mitad_sube], minimo=300, maximo=2500
			), sube
			assert niveles.pico_espectral(natural[baja][mitad_baja:], minimo=300, maximo=2500) < niveles.pico_espectral(
				natural[baja][:mitad_baja], minimo=300, maximo=2500
			), baja


def test_natural_no_es_una_copia_del_de_serie(natural):
	"""Tiene que sonar distinto: ningún sonido es el mismo fichero, y el conjunto es menos brillante (más cálido)."""
	defecto = SONIDOS_DE_SERIE / PAQUETE_POR_DEFECTO
	mas_calidos = 0
	for nombre, datos in natural.items():
		de_serie, _frecuencia = sintesis.leer_audio(sintesis.fichero_de(defecto, nombre))
		assert datos.shape != de_serie.shape or not np.allclose(datos, de_serie, atol=1e-3), f"{nombre} es igual que el de serie"
		if niveles.centroide(datos) < niveles.centroide(de_serie):
			mas_calidos += 1
	assert mas_calidos > 0.6 * len(natural)


def test_natural_los_pasos_y_los_golpes_se_distinguen(natural):
	"""Cada suelo y cada material tiene su propio reparto de energía por bandas, bien separado de los demás."""

	def bandas(datos: np.ndarray) -> np.ndarray:
		largo = max(8192, len(datos))
		energia = np.abs(np.fft.rfft(datos, largo)) ** 2
		frecuencias = np.fft.rfftfreq(largo, 1.0 / FRECUENCIA)
		cortes = (0, 150, 300, 600, 1200, 2400, 4800, 9600, 22051)
		partes = (
			np.array([energia[(frecuencias >= a) & (frecuencias < b)].sum() for a, b in zip(cortes[:-1], cortes[1:], strict=True)]) + 1e-12
		)
		return np.clip(10.0 * np.log10(partes / partes.sum()), -40.0, 0.0)

	suelos = {}
	for suelo in sintesis.SUELOS:
		nombres = [f"pasos/{suelo}_{pie}_{variante}" for pie in sintesis.PIES for variante in range(1, sintesis.VARIANTES_PASO + 1)]
		if all(nombre in natural for nombre in nombres):
			suelos[suelo] = np.array([bandas(natural[nombre]) for nombre in nombres])
	if len(suelos) >= 2:
		dentro = float(np.mean([perfiles.std(axis=0).mean() for perfiles in suelos.values()]))
		claves = list(suelos)
		for i, uno in enumerate(claves):
			for otro in claves[i + 1 :]:
				separacion = float(np.abs(suelos[uno].mean(axis=0) - suelos[otro].mean(axis=0)).mean())
				assert separacion > dentro, (
					f"Los pasos sobre {uno} y sobre {otro} se parecen demasiado ({separacion:.2f} dB frente a {dentro:.2f} dB)"
				)
		# Las variantes de un mismo paso no son el mismo sonido repetido.
		assert not np.array_equal(natural["pasos/baldosa_izq_1"], natural["pasos/baldosa_izq_2"]) if "baldosa" in suelos else True
	for familia in ("golpe", "roce"):
		perfiles = {
			material: bandas(natural[f"{familia}/{material}"]) for material in sintesis.MATERIALES if f"{familia}/{material}" in natural
		}
		claves = list(perfiles)
		for i, uno in enumerate(claves):
			for otro in claves[i + 1 :]:
				separacion = float(np.abs(perfiles[uno] - perfiles[otro]).mean())
				assert separacion > 2.0, f"{familia}: {uno} y {otro} se parecen demasiado ({separacion:.2f} dB)"


# ── Herramientas ─────────────────────────────────────────────────────────────


def test_sintetizar_escribe_el_paquete_por_defecto_y_el_catalogo_fuera(tmp_path):
	from tools import sintetizar_sonidos

	assert sintetizar_sonidos.main(["--carpeta", str(tmp_path), "--solo", "interfaz/mover", "--formato", "wav"]) == 0
	paquete = tmp_path / "por_defecto"
	assert (paquete / "interfaz" / "mover.wav").is_file()
	assert (tmp_path / "catalogo.json").is_file() and not (paquete / "catalogo.json").exists()
	ficha = leer_ficha(paquete)
	assert ficha["id"] == "por_defecto" and ficha["nombre"] and ficha["generado"]
	assert "numpy" in (paquete / "CREDITOS.txt").read_text(encoding="utf-8")
	referencias = niveles.leer_niveles(paquete)
	assert set(referencias) == set(sintesis.nombres())
	assert referencias["interfaz/mover"][0] == pytest.approx(niveles.nivel(sintesis.generar("interfaz/mover")), rel=0.01)
	# Un banco sobre esa carpeta lo ve como un paquete completo... de un solo fichero escrito.
	lista = Banco(carpetas_sonidos=[tmp_path], carpetas_complementos=[]).paquetes_disponibles()
	assert [(paquete["id"], paquete["sonidos"]) for paquete in lista] == [("por_defecto", 1)]


def test_la_receta_del_paquete_natural_cubre_el_catalogo_sin_ia():
	from tools import generar_paquete_sonidos as herramienta
	from tools import receta_natural

	recetas = receta_natural.recetas()
	assert set(recetas) == set(sintesis.nombres())
	assert receta_natural.FICHA["id"] == receta_natural.ID == "natural"
	for nombre, receta in recetas.items():
		definicion = sintesis.CATALOGO[nombre]
		canales = 2 if definicion.bucle and not definicion.posicionable and nombre.startswith(("ambiente/", "trafico/ambiente")) else 1
		datos = herramienta.especificacion(nombre, receta, definicion, canales, 1.0, subida=8.0)
		texto = json.dumps(datos)
		assert '"_' not in texto, f"{nombre}: quedan marcas de la receta en la especificación"
		assert {capa["tipo"] for capa in datos["capas"]} <= {"sonido", "nota", "secuencia"}, nombre
		assert datos["sr_salida"] == FRECUENCIA and datos["salida"] == f"{nombre}.wav"
		assert ("mono" in datos) != ("estereo" in datos)
		if definicion.bucle:
			assert datos["bucle"] in (True, "nativo"), nombre
		else:
			assert "bucle" not in datos and datos["efectos"][-1]["nombre"] == "fundido", nombre
		if definicion.posicionable and "bucle" not in datos:
			# Lo que se sitúa tiene con qué subir los agudos, o ya los trae de sobra (se mide al generar).
			assert isinstance(herramienta.tiene_ajuste(receta), bool)
	# La subida de agudos se aplica solo a lo marcado.
	pulso = recetas["baliza/pulso"]
	sin_subir = herramienta.especificacion("baliza/pulso", pulso, sintesis.CATALOGO["baliza/pulso"], 1, 0.35)
	subido = herramienta.especificacion("baliza/pulso", pulso, sintesis.CATALOGO["baliza/pulso"], 1, 0.35, subida=12.0)
	assert subido["capas"][1]["volumen_db"] == pytest.approx(sin_subir["capas"][1]["volumen_db"] + 12.0)
	assert subido["capas"][0] == sin_subir["capas"][0] and sin_subir["semilla"] == subido["semilla"]
	assert (
		herramienta.especificacion(
			"pasos/baldosa_izq_1", recetas["pasos/baldosa_izq_1"], sintesis.CATALOGO["pasos/baldosa_izq_1"], 1, 0.14
		)["semilla"]
		!= herramienta.especificacion(
			"pasos/baldosa_izq_2", recetas["pasos/baldosa_izq_2"], sintesis.CATALOGO["pasos/baldosa_izq_2"], 1, 0.14
		)["semilla"]
	)


def test_la_herramienta_descarta_lo_que_no_sirve_para_orientarse():
	from tools import generar_paquete_sonidos as herramienta

	baliza = sintesis.CATALOGO["baliza/pulso"]
	bueno = sintesis.generar("baliza/pulso")
	receta = {"capas": [], "comprobar": {"notas": [660], "golpes": 1}}
	assert herramienta.comprobar("baliza/pulso", bueno, FRECUENCIA, receta, baliza, 1, 0.35, 0.35) == []
	# Un tono puro, sin agudos: no se podría situar.
	grave = (_tono(660, 0.35, 0.5) * np.hanning(len(_tono(660, 0.35, 0.5)))).astype(np.float32)
	motivos = herramienta.comprobar("baliza/pulso", grave, FRECUENCIA, receta, baliza, 1, 0.35, 0.35)
	assert any("3 kHz" in motivo for motivo in motivos)
	# Otra nota: ya no codifica lo mismo.
	otra = {"capas": [], "comprobar": {"notas": [990]}}
	assert any("990" in motivo for motivo in herramienta.comprobar("baliza/pulso", bueno, FRECUENCIA, otra, baliza, 1, 0.35, 0.35))
	# Estéreo donde debe ser mono, demasiado largo, sin silencio al final.
	assert any(
		"canales" in motivo
		for motivo in herramienta.comprobar("baliza/pulso", np.stack([bueno, bueno], axis=1), FRECUENCIA, receta, baliza, 1, 0.35, 0.35)
	)
	largo = np.concatenate([bueno, bueno, bueno])
	assert any("veces" in motivo for motivo in herramienta.comprobar("baliza/pulso", largo, FRECUENCIA, receta, baliza, 1, 0.35, 0.35))
	cortado = bueno[: len(bueno) // 20]
	assert any(
		"silencio" in motivo for motivo in herramienta.comprobar("baliza/pulso", cortado, FRECUENCIA, {"capas": []}, baliza, 1, 0.35, 0.35)
	)
	# Un bucle con salto en la costura.
	frigorifico = sintesis.CATALOGO["fuente/frigorifico"]
	bucle = sintesis.generar("fuente/frigorifico")
	assert herramienta.comprobar("fuente/frigorifico", bucle, FRECUENCIA, {"capas": []}, frigorifico, 1, 4.0, len(bucle) / FRECUENCIA) == []
	roto = bucle.copy()
	roto[-1] = 0.6
	assert any(
		"costura" in motivo
		for motivo in herramienta.comprobar(
			"fuente/frigorifico", roto, FRECUENCIA, {"capas": []}, frigorifico, 1, 4.0, len(bucle) / FRECUENCIA
		)
	)
	# Sin el ejecutable, la herramienta lo dice claro y no inventa nada.
	with pytest.raises(herramienta.ErrorGenerador, match="No se encuentra"):
		herramienta.buscar_exe(paths.ruta_base() / "no_existe" / "sonido.exe")
