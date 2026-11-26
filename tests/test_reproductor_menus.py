"""Pruebas de los menús hablados del reproductor: se recorren todos, con teclado, acciones y mando."""

# ruff: noqa: F811 - los parámetros de las pruebas se llaman como las fixtures importadas
from __future__ import annotations

import pygame

from app.entrada import acciones
from app.reproductor import alumno
from app.reproductor.menus import EntradaTexto, Mensaje, Menu, Opcion
from app.reproductor.pantallas.aprender import MenuSonidos, PracticaControles

from .test_reproductor_comun import Robot, app, crear_app, robot, sin_navegador  # noqa: F401 - fixtures

# Opciones del menú principal que abren otra pantalla sobre él (las demás empiezan una partida o salen).
SUBMENUS_DEL_PRINCIPAL = (
	"Elegir entorno",
	"Mis premios",
	"Aprender los sonidos",
	"Opciones",
	"Conectar con mi profesor",
	"Cambiar de jugador",
	"Ayuda",
	"Acerca de",
)
# Opciones que el recorrido general no acepta ni ajusta: salen, cambian de motor o de idioma, o buscan en la red.
NO_TOCAR = (
	"Volver",
	"Restablecer",
	"Motor de sonido",
	"Idioma",
	"Buscar salas",
	"Desconectar",
	"Jugar como invitado",
	"Exploración libre",
	"Luna",
)


class MandoFalso:
	"""Un mando de mentira: basta con el nombre y, si vibra, ``rumble``."""

	def __init__(self, nombre: str = "Xbox Wireless Controller") -> None:
		self.name = nombre
		self.vibraciones: list[tuple[float, float, int]] = []

	def rumble(self, grave: float, agudo: float, ms: int) -> bool:
		self.vibraciones.append((grave, agudo, ms))
		return True


def _recorrer(robot: Robot, profundidad: int = 0, visitados: set[str] | None = None) -> int:
	"""Recorre el menú de arriba entero: pide la ayuda de cada opción, la ajusta y entra en los submenús.

	Devuelve cuántas opciones ha visto.
	"""
	visitados = visitados if visitados is not None else set()
	menu = robot.cima
	assert isinstance(menu, Menu)
	vistas = 0
	for indice in range(len(menu.opciones)):
		if indice >= len(menu.opciones):
			break
		menu.i = indice
		opcion = menu.opciones[indice]
		texto = opcion.texto
		assert texto.strip(), "ninguna opción puede estar vacía"
		marca = robot.marca()
		robot.accion("ayuda")
		assert robot.dicho(marca).strip(), f"la ayuda de «{texto}» no dice nada"
		vistas += 1
		clave = f"{menu.titulo}/{texto.split(':')[0]}"
		if texto.startswith(NO_TOCAR) or clave in visitados:
			continue
		visitados.add(clave)
		if opcion.ajuste is not None and opcion.accion is None:
			robot.accion("menu_derecha")
			robot.accion("menu_izquierda")
			continue
		# En la lista de actividades de un entorno, aceptar empieza una partida: eso lo prueban otras pruebas.
		if opcion.accion is None or profundidad >= 3 or any(o.texto == "Exploración libre" for o in menu.opciones):
			continue
		antes = len(robot.app.pila)
		robot.accion("menu_aceptar")
		if len(robot.app.pila) > antes:
			if isinstance(robot.cima, Menu):
				vistas += _recorrer(robot, profundidad + 1, visitados)
			while len(robot.app.pila) > antes:
				if isinstance(robot.cima, EntradaTexto):
					robot.tecla(pygame.K_ESCAPE)
				else:
					robot.atras()
		assert robot.cima is menu, f"tras «{texto}» no se ha vuelto al menú «{menu.titulo}»"
	return vistas


def test_se_recorren_todos_los_menus_sin_fallos(robot: Robot):
	principal = robot.cima
	total = 0
	for texto in SUBMENUS_DEL_PRINCIPAL:
		assert principal.elegir(texto), texto
		marca = robot.marca()
		robot.accion("menu_aceptar", 2)
		assert robot.cima is not principal, f"«{texto}» no ha abierto nada"
		assert robot.dicho(marca).strip(), f"al abrir «{texto}» no se dice nada"
		robot.app.dibujar()
		total += _recorrer(robot)
		robot.atras()
		assert robot.cima is principal
	assert total > 120, f"se esperaban muchas más opciones entre todos los menús, y hay {total}"
	assert robot.app.fallos == 0


def test_moverse_por_un_menu_posicion_bordes_inicio_fin_e_inicial(robot: Robot):
	menu = robot.cima
	marca = robot.marca()
	robot.accion("menu_abajo")
	assert robot.ultimo() == "Elegir entorno. 2 de 12."
	assert "interfaz/mover" in robot.sonidos()
	robot.accion("menu_arriba")
	robot.accion("menu_arriba")
	assert robot.ultimo() == "Salir. 12 de 12.", "al pasarse del principio se da la vuelta"
	assert "interfaz/borde" in robot.sonidos()
	robot.tecla(pygame.K_HOME)
	assert menu.i == 0
	robot.tecla(pygame.K_END)
	assert menu.i == len(menu.opciones) - 1
	robot.tecla(pygame.K_m, unicode="m")
	assert robot.ultimo().startswith("Mis premios")
	robot.tecla(pygame.K_a, unicode="á")
	assert robot.ultimo().startswith("Aprender los sonidos"), "la inicial no distingue tildes"
	robot.tecla(pygame.K_a, unicode="a")
	assert robot.ultimo().startswith("Ayuda"), "la misma letra salta a la siguiente opción que empieza por ella"
	robot.tecla(pygame.K_DOWN)
	assert robot.ultimo().startswith("Acerca de"), "las flechas pasan por el mapa de teclado real"
	robot.accion("menu_atras")
	assert robot.cima is menu, "del menú principal no se sale con atrás"
	assert all(interrumpe for _texto, _canal, interrumpe in robot.app.voz.registro[marca:]), "en un menú cada frase corta la anterior"
	robot.app.establecer("juego.posicion_menu", False)
	robot.accion("menu_abajo")
	assert robot.ultimo() == "Salir.", "sin posición no se dice «12 de 12»"


def test_repetir_historial_y_callar_valen_en_los_menus(robot: Robot):
	robot.accion("menu_abajo")
	robot.accion("menu_abajo")
	robot.tecla(pygame.K_F2)
	assert robot.app.voz.registro[-1][:2] == ("Mis premios. 3 de 12.", "historial")
	robot.tecla(pygame.K_F3)
	assert robot.app.voz.registro[-1][0] == "Elegir entorno. 2 de 12."
	robot.tecla(pygame.K_F3, mod=pygame.KMOD_LSHIFT)
	assert robot.app.voz.registro[-1][0].endswith("Mis premios. 3 de 12.")
	robot.tecla(pygame.K_LCTRL)
	assert robot.app.voz.callada >= 1


def test_un_ajuste_se_cambia_con_izquierda_y_derecha_y_se_guarda(robot: Robot):
	robot.elegir("Opciones")
	robot.elegir("Sonido")
	texto = robot.ajustar("Volumen general", -1)
	assert texto == "Volumen general: 95 por ciento"
	assert robot.ultimo() == texto
	assert robot.app.config.obtener("sonido.volumen_maestro") == 0.95
	assert robot.app.motor.de("volumen_bus")[-1] == {"bus": "maestro", "valor": 0.95}
	assert "interfaz/ajuste" in robot.sonidos()
	for _i in range(4):
		robot.accion("menu_derecha")
	assert robot.app.config.obtener("sonido.volumen_maestro") == 1.0, "no se pasa del máximo"
	assert robot.sonidos()[-1] == "interfaz/borde", "en el tope suena el borde"


def test_quien_juega_alias_nuevo_con_teclado_y_perfil_sin_datos_personales(data_temporal, sin_navegador):
	aplicacion = crear_app()
	try:
		robot = Robot(aplicacion)
		assert robot.pantallas() == ["Menu", "Menu"]
		assert robot.cima.titulo == "¿Quién juega?"
		robot.accion("menu_atras")
		assert robot.cima.titulo == "¿Quién juega?", "sin alias elegido no se puede saltar la pregunta"
		robot.elegir("Soy nuevo")
		assert isinstance(robot.cima, EntradaTexto)
		assert "Escribe tu alias" in robot.ultimo()
		robot.tecla(pygame.K_m, unicode="M")
		assert robot.ultimo() == "M mayúscula"
		robot.tecla(pygame.K_x, unicode="x")
		robot.tecla(pygame.K_BACKSPACE)
		assert robot.ultimo() == "Borrado x"
		robot.tecla(pygame.K_SPACE, unicode=" ")
		assert robot.ultimo() == "espacio", "al escribir, Espacio no es «aceptar»"
		robot.tecla(pygame.K_BACKSPACE)
		robot.escribir("ar")
		assert aplicacion.alias == "Mar"
		assert robot.pantallas() == ["Menu"]
		assert "Hola, Mar" in robot.ultimo()
		assert alumno.listar_alias() == ["Mar"]
		perfil = (data_temporal / "config" / "alumnos" / "mar.json").read_text(encoding="utf-8")
		assert '"alias": "Mar"' in perfil and "nombre" not in perfil
		assert aplicacion.config.obtener("juego.alias") == "Mar"
	finally:
		aplicacion.cerrar_todo()
	otra = crear_app()
	try:
		assert otra.alias == "Mar", "la próxima vez se entra con el último alias"
		assert Robot(otra).pantallas() == ["Menu"]
	finally:
		otra.cerrar_todo()


def test_alias_con_el_mando_rueda_de_letras(robot: Robot):
	robot.app.entrada.mandos.conectar(MandoFalso(), 1)
	robot.esperar(2)
	assert "Mando conectado: Xbox Wireless Controller." in robot.dicho()
	robot.elegir("Cambiar de jugador")
	robot.elegir("Soy nuevo")
	assert "cruceta" in robot.ultimo() and "botón A" in robot.ultimo(), "con mando se explica la rueda con sus botones"
	robot.accion("menu_abajo")
	assert robot.ultimo() == "b"
	robot.accion("menu_derecha")
	assert robot.cima.texto == "b"
	robot.accion("historial_siguiente")
	assert robot.ultimo().startswith("Mayúsculas")
	robot.accion("menu_derecha")
	robot.accion("historial_anterior")
	assert robot.cima.texto == "bA "
	robot.accion("menu_izquierda")
	robot.accion("repetir")
	assert robot.ultimo() == "bA"
	robot.accion("menu_aceptar", 2)
	assert robot.app.alias == "bA"


def test_mis_premios_vacio_y_con_premios(robot: Robot):
	robot.elegir("Mis premios")
	assert "Todavía no hay premios" in robot.opciones()[0]
	robot.atras()
	ganado = [
		{"tipo": "estrella", "nombre": "Estrella sin choques"},
		{"tipo": "medalla", "nombre": "Medalla de explorador"},
		{"tipo": "objeto", "nombre": "Llave"},
	]
	robot.app.perfil.anadir_premios(ganado, "Casa", "Busca")
	robot.app.perfil.apuntar_actividad("casa/busca", 1, True)
	robot.elegir("Mis premios")
	assert robot.opciones()[0] == "Tienes 1 estrella, 1 medalla, 1 objeto."
	assert "Objeto: Llave" in robot.opciones() and "Medalla: Medalla de explorador" in robot.opciones()


def test_acerca_de_con_la_invitacion_al_cafe(robot: Robot, sin_navegador):
	from app.core import version

	robot.elegir("Acerca de")
	textos = " | ".join(robot.opciones())
	assert version.AUTOR in textos and version.LICENCIA in textos and version.APP_VERSION in textos
	assert "OpenAL Soft" in textos and "BASS" in textos and "uso no comercial" in textos
	robot.elegir("Invítame a un café si te gusta mi trabajo")
	assert sin_navegador == [version.CAFE]
	assert "Abriendo la página de donaciones" in robot.ultimo()
	robot.elegir("Avisar de un fallo")
	robot.elegir("Página del proyecto")
	robot.elegir("Mastodon")
	assert sin_navegador[1:] == [version.FALLOS, version.WEB, version.MASTODON]


def test_aprender_los_sonidos_por_grupos_con_explicacion(robot: Robot):
	robot.elegir("Aprender los sonidos")
	assert len(robot.opciones()) >= 8, "los grupos del catálogo de sonidos"
	robot.elegir("Orientación")
	menu = robot.cima
	assert isinstance(menu, MenuSonidos) and len(menu.opciones) > 10
	antes = len(robot.app.motor.de("reproducir"))
	robot.accion("menu_aceptar")
	sonado = robot.app.motor.de("reproducir")[antes:]
	assert len(sonado) == 1 and sonado[0]["nombre"].startswith("baliza/") and sonado[0]["bus"] == "interfaz"
	marca = robot.marca()
	robot.accion("ayuda")
	assert len(robot.dicho(marca)) > 20, "la ayuda dice la explicación del sonido"
	robot.atras()
	robot.elegir("Ambientes")
	robot.accion("menu_aceptar")
	assert robot.cima._canal and robot.app.motor.de("reproducir")[-1]["bucle"] is True
	robot.segundos(4.5)
	assert robot.cima._canal == 0, "un bucle se apaga solo a los pocos segundos"


def test_practicar_los_controles_dice_y_no_ejecuta(robot: Robot):
	robot.elegir("Practicar los controles")
	assert isinstance(robot.cima, PracticaControles)
	assert "dos veces" in robot.ultimo()
	robot.tecla(pygame.K_UP)
	assert robot.ultimo().startswith("Flecha arriba: Avanzar.")
	robot.tecla(pygame.K_c, unicode="c")
	assert robot.ultimo().startswith("C: Dónde estoy.")
	robot.tecla(pygame.K_LEFT, mod=pygame.KMOD_LSHIFT)
	assert "Paso lateral a la izquierda" in robot.ultimo()
	robot.tecla(pygame.K_z, unicode="z")
	assert robot.ultimo() == "Z: no hace nada mientras juegas."
	robot.tecla(pygame.K_ESCAPE)
	assert isinstance(robot.cima, PracticaControles), "una sola pulsación de pausa no sale: dice para qué sirve"
	assert "Pausa y menú" in robot.ultimo()
	robot.tecla(pygame.K_F1)
	robot.tecla(pygame.K_ESCAPE)
	assert isinstance(robot.cima, PracticaControles), "tienen que ser dos seguidas"
	robot.tecla(pygame.K_ESCAPE)
	assert robot.pantallas() == ["Menu"]
	assert robot.app.partida is None


def test_practicar_los_controles_con_mando(robot: Robot):
	from app.entrada.mando import SDL_DE_BOTON

	robot.app.entrada.mandos.conectar(MandoFalso("DualSense Wireless Controller"), 7)
	robot.elegir("Practicar los controles")

	def boton(nombre: str) -> None:
		robot.app.evento(pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, instance_id=7, button=SDL_DE_BOTON[nombre]))
		robot.app.evento(pygame.event.Event(pygame.CONTROLLERBUTTONUP, instance_id=7, button=SDL_DE_BOTON[nombre]))
		robot.esperar()

	boton("x")
	assert robot.ultimo().startswith("Cuadrado: Dónde estoy."), "se dice el nombre del botón de ESE mando"
	boton("a")
	assert robot.ultimo().startswith("Equis: Interactuar.")
	boton("panel")
	assert "no hace nada" in robot.ultimo()


def test_ayuda_con_teclas_y_con_los_botones_del_mando(robot: Robot):
	robot.elegir("Ayuda")
	lineas = robot.opciones()
	assert "Flecha arriba: avanzar." in lineas and "C: dónde estoy." in lineas and "Escape: pausa y menú." in lineas
	assert len(lineas) >= len(acciones.acciones_de(acciones.JUEGO))
	robot.atras()
	robot.app.entrada.mandos.conectar(MandoFalso(), 1)
	robot.elegir("Ayuda")
	lineas = robot.opciones()
	assert any("X" in linea and "dónde estoy" in linea for linea in lineas), lineas[:12]
	assert "Xbox Wireless Controller" in robot.dicho()
	robot.atras()
	robot.app.entrada.mandos.desconectar(1)
	robot.esperar(2)
	assert "Mando desconectado. Puedes seguir con el teclado." in robot.dicho()


def test_la_ayuda_de_un_menu_sin_ayuda_propia_explica_como_se_maneja(robot: Robot):
	menu = Menu(robot.app, "Prueba", [Opcion("Una"), Opcion("Dos")])
	robot.app.abrir(menu)
	robot.tecla(pygame.K_F1)
	assert "flecha arriba y flecha abajo para moverte" in robot.ultimo()
	robot.accion("menu_abajo")
	robot.accion("menu_abajo")
	assert robot.ultimo().startswith("Volver"), "todo menú del que se sale con Escape tiene también su opción de volver"
	robot.accion("menu_aceptar")
	assert robot.pantallas() == ["Menu"]


def test_mensaje_por_pasos(robot: Robot):
	terminado: list[bool] = []
	robot.app.abrir(Mensaje(robot.app, "Aviso", ["Primera frase.", "Segunda frase."], al_terminar=lambda: terminado.append(True)))
	assert "Aviso. Primera frase." in robot.ultimo() and "1 de 2" in robot.ultimo()
	robot.accion("menu_aceptar")
	assert robot.ultimo().startswith("Segunda frase.")
	robot.accion("menu_izquierda")
	assert robot.ultimo().startswith("Primera frase.")
	robot.accion("menu_aceptar")
	robot.accion("menu_aceptar")
	assert terminado == [True] and robot.pantallas() == ["Menu"]


def test_se_dibuja_cada_pantalla_tambien_en_alto_contraste_y_en_negro(robot: Robot):
	for clave, valor in (("general.alto_contraste", True), ("general.tamano_texto", 200), ("juego.pantalla_negra", True)):
		robot.app.dibujar()
		robot.elegir("Opciones")
		robot.app.dibujar()
		robot.atras()
		robot.app.establecer(clave, valor)
	robot.app.dibujar()
	assert robot.app.lienzo.get_at((480, 300))[:3] == (0, 0, 0), "en negro no se dibuja nada"
