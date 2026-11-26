"""Pruebas de la sala y el cliente de supervisión conectándose de verdad por 127.0.0.1."""

from __future__ import annotations

import socket
import threading
import time

import pytest

from app.supervision import protocolo, seguridad
from app.supervision.cliente import RECHAZADO, ClienteSupervision
from app.supervision.protocolo import A_ESTUDIO, A_JUGAR, ErrorProtocolo, LectorLineas
from app.supervision.sala import ORDENES_DE_SERVICIO, ErrorSala, Sala
from tests._supervision_util import ConexionCruda, alumno_de, esperar

CODIGO = "246810"


@pytest.fixture
def sala():
	abierta = Sala(nombre="Sala de pruebas", intervalo_latido=0.2, tiempo_muerto=1.0)
	abierta.iniciar(0, CODIGO)
	yield abierta
	abierta.detener()


@pytest.fixture
def clientes():
	creados: list[ClienteSupervision] = []
	yield creados
	for cliente in creados:
		cliente.detener(espera=1.0)


def _cliente(clientes, puerto: int, alias: str = "Luna", codigo: str = CODIGO, **opciones) -> ClienteSupervision:
	opciones.setdefault("intervalo_estado", 0.05)
	opciones.setdefault("intervalo_latido", 0.2)
	opciones.setdefault("tiempo_muerto", 1.0)
	opciones.setdefault("reintento_min", 0.05)
	opciones.setdefault("reintento_max", 0.2)
	opciones.setdefault("entorno", "Casa de ejemplo")
	opciones.setdefault("actividad", "Buscar la llave")
	cliente = ClienteSupervision("127.0.0.1", puerto, codigo, alias, **opciones)
	clientes.append(cliente)
	cliente.iniciar()
	return cliente


def _tipos(sala_abierta: Sala, acumulados: list[dict]) -> list[str]:
	acumulados.extend(sala_abierta.eventos_pendientes())
	return [suceso["tipo"] for suceso in acumulados]


# ── Conexión, estado, eventos y voz ──────────────────────────────────────────


def test_un_alumno_se_conecta_y_la_foto_lo_refleja(sala, clientes):
	cliente = _cliente(clientes, sala.puerto, modo="practica")
	assert esperar(lambda: cliente.conectado)
	assert cliente.alumno_en_sala == "Luna"
	assert cliente.nombre_sala == "Sala de pruebas"
	assert not cliente.tls
	cliente.estado(
		planta="p0",
		x=3.5,
		y=2.0,
		rumbo=90.0,
		espacio="Cocina",
		descripcion="Cocina, planta baja, mirando al este",
		delante="Una mesa a dos metros",
		pausado=False,
		tiempo_activo=12.5,
		contadores={"distancia_m": 8.2, "choques": 1, "ayudas": 2},
		campo_que_no_existe=True,
	)
	assert esperar(lambda: (alumno_de(sala, "Luna") or {}).get("espacio") == "Cocina")
	foto = sala.foto()
	assert foto["activa"] and not foto["red"]
	assert foto["codigo"] == CODIGO
	assert foto["puerto"] == sala.puerto == foto["puerto_local"]
	alumno = foto["alumnos"][0]
	assert alumno["alias"] == "Luna"
	assert alumno["conectado"] and not alumno["cifrada"] and not alumno["recorrido"]
	assert alumno["entorno"] == "Casa de ejemplo"
	assert alumno["actividad"] == "Buscar la llave"
	assert alumno["modo"] == "practica"
	assert (alumno["planta"], alumno["x"], alumno["y"], alumno["rumbo"]) == ("p0", 3.5, 2.0, 90.0)
	assert alumno["posicion"] == "Cocina, planta baja, mirando al este"
	assert alumno["delante"] == "Una mesa a dos metros"
	assert alumno["contadores"] == {"distancia_m": 8.2, "choques": 1, "ayudas": 2}
	assert alumno["tiempo_activo"] == 12.5
	assert alumno["pausado"] is False
	assert alumno["segundos_sin_contacto"] < 1.0
	# La foto es una copia: tocarla no cambia lo que guarda la sala.
	alumno["contadores"]["choques"] = 99
	assert alumno_de(sala, "Luna")["contadores"]["choques"] == 1


def test_eventos_voz_y_fin_llegan_a_la_cola_de_la_interfaz(sala, clientes):
	cliente = _cliente(clientes, sala.puerto)
	assert esperar(lambda: cliente.conectado)
	cliente.estado(tiempo_activo=4.0, pausado=False)
	assert esperar(lambda: (alumno_de(sala, "Luna") or {}).get("tiempo_activo") == 4.0)
	cliente.evento("choque", {"con": "mesa", "x": 1.0, "y": 2.0})
	cliente.evento("ayuda", {"ayuda": "donde_estoy"})
	cliente.voz("Estás en la cocina.", canal="ayuda")
	cliente.voz("Pared a un metro.")
	cliente.fin(completada=True, resultado={"estrellas": 3})
	sucesos: list[dict] = []
	assert esperar(lambda: "fin" in _tipos(sala, sucesos))
	assert [s["tipo"] for s in sucesos] == ["conectado", "evento", "evento", "voz", "voz", "fin"]
	assert all(s["alumno"] == "Luna" and s["alias"] == "Luna" for s in sucesos)
	assert sucesos[1]["datos"] == {"t": 4.0, "tipo": "choque", "datos": {"con": "mesa", "x": 1.0, "y": 2.0}}
	assert sucesos[3]["datos"]["texto"] == "Estás en la cocina."
	assert sucesos[3]["datos"]["canal"] == "ayuda"
	assert sucesos[5]["datos"] == {"completada": True, "resultado": {"estrellas": 3}}
	assert sala.eventos_pendientes() == []  # la cola se vacía al leerla
	alumno = alumno_de(sala, "Luna")
	assert alumno["ultimo_texto"] == "Pared a un metro."
	assert [v["texto"] for v in alumno["voces"]] == ["Estás en la cocina.", "Pared a un metro."]
	assert [e["tipo"] for e in alumno["eventos"]] == ["choque", "ayuda"]
	assert alumno["terminado"] and alumno["resultado"] == {"estrellas": 3}


def test_todas_las_ordenes_llegan_al_juego_en_orden(sala, clientes):
	cliente = _cliente(clientes, sala.puerto)
	assert esperar(lambda: cliente.conectado)
	assert esperar(lambda: alumno_de(sala, "Luna") is not None)
	assert sala.pedir("Luna", "pausa")
	assert sala.pedir("Luna", "reanudar")
	assert sala.pedir("Luna", "recolocar", planta="p0", x=1.5, y=2.5, rumbo=180)
	assert sala.pedir("Luna", "mensaje", texto="Muy bien, sigue por la pared")
	assert sala.pedir("Luna", "pista", texto="Escucha la nevera", baliza_s=10)
	assert sala.pedir("Luna", "ayudas", ayudas={"baliza": {"permitida": False, "limite": None}})
	assert sala.pedir("Luna", "premio", nombre="Estrella sorpresa", planta="p0", x=4, y=4)
	assert sala.pedir("Luna", "marca", texto="Aquí duda")
	assert sala.pedir("Luna", "reiniciar")
	assert sala.pedir("Luna", "terminar")
	assert sala.pedir("Luna", "alumno", ajustes={}, lista=[], niveles={})
	assert sala.pedir("Luna", "releer_configuracion")
	recibidas: list[tuple[str, dict]] = []
	assert esperar(lambda: recibidas.extend(cliente.ordenes_pendientes()) or len(recibidas) >= len(protocolo.ORDENES))
	assert [tipo for tipo, _datos in recibidas] == list(protocolo.ORDENES)
	assert recibidas[2][1] == {"planta": "p0", "x": 1.5, "y": 2.5, "rumbo": 180}
	assert recibidas[3][1] == {"texto": "Muy bien, sigue por la pared"}
	assert recibidas[5][1] == {"ayudas": {"baliza": {"permitida": False, "limite": None}}}
	assert cliente.ordenes_pendientes() == []
	# Las intervenciones quedan en los últimos eventos del alumno; las órdenes de servicio, no.
	intervenciones = [orden for orden in protocolo.ORDENES if orden not in ORDENES_DE_SERVICIO]
	assert [e["datos"]["orden"] for e in alumno_de(sala, "Luna")["eventos"]] == intervenciones


def test_pedir_valida_y_no_envia_a_quien_no_esta(sala, clientes):
	cliente = _cliente(clientes, sala.puerto)
	assert esperar(lambda: cliente.conectado)
	assert sala.pedir("Nadie", "pausa") is False
	with pytest.raises(ValueError):
		sala.pedir("Luna", "autodestruir")
	with pytest.raises(ErrorProtocolo):
		sala.pedir("Luna", "recolocar", planta="p0", x="uno", y=2)
	with pytest.raises(ErrorProtocolo):
		sala.pedir("Luna", "mensaje")
	assert sala.pedir("Luna", "pausa")
	assert esperar(lambda: cliente.ordenes_pendientes() == [("pausa", {})])


def test_modo_recorrido_peticion_y_respuesta(sala, clientes):
	cliente = _cliente(clientes, sala.puerto, alias="Profe", recorrido=True)
	assert esperar(lambda: cliente.conectado)
	primera = cliente.peticion("colocar_aqui", planta="p0", x=3.0, y=4.0, rumbo=90.0, objeto="mobiliario/mesa")
	segunda = cliente.peticion("medir_desde_aqui", planta="p0", x=6.0, y=4.0)
	tercera = cliente.peticion("marcar_punto", planta="p0", x=1.0, y=1.0, nombre="Fuente")
	assert (primera, segunda, tercera) == (1, 2, 3)
	with pytest.raises(ValueError):
		cliente.peticion("borrar_todo")
	sucesos: list[dict] = []
	assert esperar(lambda: _tipos(sala, sucesos).count("peticion") == 3)
	peticiones = [s["datos"] for s in sucesos if s["tipo"] == "peticion"]
	assert peticiones[0] == {
		"id": 1,
		"accion": "colocar_aqui",
		"planta": "p0",
		"x": 3.0,
		"y": 4.0,
		"rumbo": 90.0,
		"datos": {"objeto": "mobiliario/mesa"},
	}
	assert peticiones[2]["datos"] == {"nombre": "Fuente"}
	assert alumno_de(sala, "Profe")["recorrido"]
	assert sala.responder("Profe", 1, True, "Mesa colocada", objeto_id="mesa_7")
	assert sala.responder("Profe", 2, True, "3,0 metros", distancia_m=3.0)
	assert sala.responder("Profe", 3, False, "Ese punto está fuera del plano")
	recibidas: list[tuple[str, dict]] = []
	assert esperar(lambda: recibidas.extend(cliente.ordenes_pendientes()) or len(recibidas) >= 3)
	assert recibidas[0] == ("respuesta", {"id": 1, "aceptada": True, "texto": "Mesa colocada", "datos": {"objeto_id": "mesa_7"}})
	assert recibidas[1][1]["datos"] == {"distancia_m": 3.0}
	assert recibidas[2][1]["aceptada"] is False


# ── Varios alumnos ───────────────────────────────────────────────────────────


def test_varios_alumnos_a_la_vez(sala, clientes):
	luna = _cliente(clientes, sala.puerto, "Luna")
	sol = _cliente(clientes, sala.puerto, "Sol")
	mar = _cliente(clientes, sala.puerto, "Mar")
	assert esperar(lambda: luna.conectado and sol.conectado and mar.conectado)
	luna.estado(espacio="Cocina", tiempo_activo=1.0)
	sol.estado(espacio="Pasillo", tiempo_activo=2.0)
	mar.estado(espacio="Patio", tiempo_activo=3.0)
	assert esperar(lambda: {a["id"]: a["espacio"] for a in sala.foto()["alumnos"]} == {"Luna": "Cocina", "Sol": "Pasillo", "Mar": "Patio"})
	assert sala.pedir("Sol", "mensaje", texto="Solo para Sol")
	assert esperar(lambda: sol.ordenes_pendientes() == [("mensaje", {"texto": "Solo para Sol"})])
	sol.evento("premio", {"nombre": "Llave"})
	sucesos: list[dict] = []
	assert esperar(lambda: "evento" in _tipos(sala, sucesos))
	assert [s["alumno"] for s in sucesos if s["tipo"] == "evento"] == ["Sol"]
	assert luna.ordenes_pendientes() == [] and mar.ordenes_pendientes() == []
	# Uno se va: los otros siguen.
	mar.detener()
	assert esperar(lambda: alumno_de(sala, "Mar")["conectado"] is False)
	assert alumno_de(sala, "Luna")["conectado"] and alumno_de(sala, "Sol")["conectado"]
	assert sala.pedir("Mar", "pausa") is False
	assert sala.olvidar("Mar")
	assert not sala.olvidar("Luna")  # a un conectado no se le olvida
	assert alumno_de(sala, "Mar") is None


def test_dos_reproductores_con_el_mismo_alias_no_se_mezclan(sala, clientes):
	uno = _cliente(clientes, sala.puerto, "Luna")
	assert esperar(lambda: uno.conectado)
	dos = _cliente(clientes, sala.puerto, "luna")
	assert esperar(lambda: dos.conectado)
	assert uno.alumno_en_sala == "Luna"
	assert dos.alumno_en_sala == "luna (2)" or dos.alumno_en_sala == "luna"
	assert len(sala.foto()["alumnos"]) == 2
	assert sala.pedir(dos.alumno_en_sala, "pausa")
	assert esperar(lambda: dos.ordenes_pendientes() == [("pausa", {})])
	assert uno.ordenes_pendientes() == []


def test_limite_de_alumnos(clientes):
	pequena = Sala(max_alumnos=1, intervalo_latido=0.2, tiempo_muerto=1.0)
	pequena.iniciar(0, CODIGO)
	try:
		primero = _cliente(clientes, pequena.puerto, "Uno")
		assert esperar(lambda: primero.conectado)
		cruda = ConexionCruda(pequena.puerto)
		rechazo = cruda.leer()
		assert (rechazo.tipo, rechazo.datos["motivo"]) == ("rechazo", "lleno")
		cruda.cerrar()
	finally:
		pequena.detener()


# ── Código de emparejamiento ─────────────────────────────────────────────────


def test_codigo_incorrecto_y_correccion(sala, clientes):
	cliente = _cliente(clientes, sala.puerto, codigo="000000")
	assert esperar(lambda: cliente.estado_conexion == RECHAZADO)
	assert cliente.motivo_rechazo == "codigo"
	assert not cliente.conectado
	assert sala.foto()["alumnos"] == []
	sucesos = sala.eventos_pendientes()
	assert [s["tipo"] for s in sucesos] == ["codigo_incorrecto"]
	assert sucesos[0]["datos"]["intentos_restantes"] == 4
	assert sucesos[0]["alias"] == ""  # de quien no ha entrado no se guarda ni el alias
	avisos = cliente.avisos_pendientes()
	assert avisos[0][0] == "rechazado" and avisos[0][1]["motivo"] == "codigo"
	# No insiste por su cuenta: no hay más intentos fallidos.
	assert not esperar(lambda: sala.eventos_pendientes() != [], 0.4)
	cliente.cambiar_codigo("24 68 10")
	assert esperar(lambda: cliente.conectado)
	assert cliente.avisos_pendientes()[-1][0] == "conectado"


def test_limite_de_intentos_bloquea_la_direccion(clientes):
	estricta = Sala(max_intentos=2, bloqueo_s=0.8, intervalo_latido=0.2, tiempo_muerto=1.0)
	estricta.iniciar(0, CODIGO)
	try:
		for restantes in (1, 0):
			cruda = ConexionCruda(estricta.puerto)
			respuesta = cruda.saludar("111111")
			assert (respuesta.tipo, respuesta.datos["motivo"]) == ("rechazo", "codigo")
			assert cruda.cerrada_por_la_sala()
			cruda.cerrar()
			assert estricta.eventos_pendientes()[0]["datos"]["intentos_restantes"] == restantes
		# Bloqueada: ni siquiera con el código bueno, y sin llegar a recibir un reto.
		cruda = ConexionCruda(estricta.puerto)
		rechazo = cruda.leer()
		assert (rechazo.tipo, rechazo.datos["motivo"]) == ("rechazo", "bloqueado")
		assert 0 < rechazo.datos["espera_s"] <= 0.8
		cruda.cerrar()
		assert estricta.foto()["bloqueados"] == 1
		# Un cliente legítimo espera lo que dice la sala y entra solo cuando pasa el bloqueo.
		cliente = _cliente(clientes, estricta.puerto)
		assert esperar(lambda: cliente.estado_conexion == RECHAZADO and cliente.motivo_rechazo == "bloqueado", 2.0)
		assert esperar(lambda: cliente.conectado, 5.0)
		assert estricta.foto()["bloqueados"] == 0
	finally:
		estricta.detener()


def test_la_sala_tambien_demuestra_que_conoce_el_codigo(clientes):
	"""Una sala falsa (que no conoce el código) no engaña al cliente aunque le dé la bienvenida."""
	servidor = socket.create_server(("127.0.0.1", 0))
	puerto = servidor.getsockname()[1]
	recibido: list[protocolo.Mensaje] = []

	def impostora() -> None:
		conexion, _origen = servidor.accept()
		conexion.settimeout(3.0)
		conexion.sendall(protocolo.codificar("reto", {"nonce": "ab" * 16}, sentido=A_JUGAR))
		troceador = LectorLineas()
		lineas: list[bytes | None] = []
		while not lineas:
			lineas = troceador.alimentar(conexion.recv(4096))
		recibido.append(protocolo.decodificar(lineas[0], A_ESTUDIO))
		conexion.sendall(protocolo.codificar("bienvenida", {"prueba": "00" * 32, "alumno": "Luna"}, sentido=A_JUGAR))
		time.sleep(0.3)
		conexion.close()

	hilo = threading.Thread(target=impostora, daemon=True)
	hilo.start()
	cliente = _cliente(clientes, puerto)
	assert esperar(lambda: cliente.estado_conexion == RECHAZADO)
	assert cliente.motivo_rechazo == "sala"
	assert not cliente.conectado
	hilo.join(timeout=3)
	servidor.close()
	# El código no ha viajado: solo una prueba que no sirve para otra conexión.
	assert CODIGO not in str(recibido[0].datos)


# ── Mensajes mal formados ────────────────────────────────────────────────────


def test_mensajes_mal_formados_no_rompen_la_conexion(sala):
	cruda = ConexionCruda(sala.puerto)
	assert cruda.saludar(CODIGO, "Cruda").tipo == "bienvenida"
	cruda.enviar("estado", {"espacio": "Antes", "tiempo_activo": 1.0})
	assert esperar(lambda: (alumno_de(sala, "Cruda") or {}).get("espacio") == "Antes")
	cruda.enviar_crudo(b"esto no es json\n")
	cruda.enviar_crudo(b"\xff\xfe\xfd\n")
	cruda.enviar_crudo(b"x" * 100_000 + b"\n")  # línea enorme
	cruda.enviar_sobre({"v": 1, "tipo": "formatear_disco", "seq": 1, "t": 0, "datos": {}})
	cruda.enviar_sobre({"v": 1, "tipo": "estado", "seq": 1, "t": 0, "datos": {"x": "muchos", "espacio": "Mal"}})
	cruda.enviar_sobre({"v": 99, "tipo": "estado", "seq": 1, "t": 0, "datos": {"espacio": "Otra versión"}})
	cruda.enviar_sobre({"v": 1, "tipo": "pausa", "seq": 1, "t": 0, "datos": {}})  # tipo del otro sentido
	cruda.enviar_sobre([1, 2, 3])
	cruda.enviar("estado", {"espacio": "Después", "tiempo_activo": 2.0})
	assert esperar(lambda: alumno_de(sala, "Cruda")["espacio"] == "Después")
	alumno = alumno_de(sala, "Cruda")
	assert alumno["conectado"]
	assert alumno["errores_protocolo"] == 8
	assert alumno["tiempo_activo"] == 2.0
	# Y la sala sigue pudiendo mandarle órdenes.
	assert sala.pedir("Cruda", "pausa")
	assert cruda.leer_tipo("pausa").datos == {}
	cruda.cerrar()
	assert esperar(lambda: alumno_de(sala, "Cruda")["conectado"] is False)


def test_demasiados_errores_seguidos_cortan_la_conexion(sala):
	cruda = ConexionCruda(sala.puerto)
	assert cruda.saludar(CODIGO, "Pesada").tipo == "bienvenida"
	cruda.enviar_crudo(b"basura\n" * 30)
	assert cruda.leer_tipo("rechazo").datos["motivo"] == "protocolo"
	assert cruda.cerrada_por_la_sala()
	assert esperar(lambda: alumno_de(sala, "Pesada")["conectado"] is False)
	sucesos = [s for s in sala.eventos_pendientes() if s["tipo"] == "desconectado"]
	assert sucesos[0]["datos"]["motivo"] == "protocolo"
	cruda.cerrar()


@pytest.mark.parametrize(
	("primera_linea", "motivo"),
	[
		(b"GET / HTTP/1.1\r\n", "protocolo"),
		(b'{"v": 1, "tipo": "estado", "seq": 0, "t": 0, "datos": {}}\n', "protocolo"),
		(b'{"v": 7, "tipo": "hola", "seq": 0, "t": 0, "datos": {}}\n', "version"),
		(b'{"v": 1, "tipo": "hola", "seq": 0, "t": 0, "datos": {"alias": "X"}}\n', "protocolo"),
		(b"y" * 80_000 + b"\n", "protocolo"),
	],
)
def test_saludo_no_valido_se_rechaza_sin_contar_como_intento(sala, primera_linea, motivo):
	cruda = ConexionCruda(sala.puerto)
	assert cruda.leer().tipo == "reto"
	cruda.enviar_crudo(primera_linea)
	rechazo = cruda.leer()
	assert (rechazo.tipo, rechazo.datos["motivo"]) == ("rechazo", motivo)
	assert cruda.cerrada_por_la_sala()
	cruda.cerrar()
	assert sala.foto()["alumnos"] == []
	assert sala.foto()["bloqueados"] == 0
	assert sala.eventos_pendientes() == []


def test_quien_no_saluda_a_tiempo_es_desconectado():
	impaciente = Sala(espera_hola=0.3)
	impaciente.iniciar(0, CODIGO)
	try:
		cruda = ConexionCruda(impaciente.puerto)
		assert cruda.leer().tipo == "reto"
		assert cruda.cerrada_por_la_sala(3.0, avisar=False)
		cruda.cerrar()
	finally:
		impaciente.detener()


# ── Latido, desconexión y reconexión ─────────────────────────────────────────


def test_la_sala_detecta_por_latido_a_un_reproductor_colgado(sala):
	cruda = ConexionCruda(sala.puerto)
	assert cruda.saludar(CODIGO, "Colgada").tipo == "bienvenida"
	assert esperar(lambda: (alumno_de(sala, "Colgada") or {}).get("conectado") is True)
	# No envía nada más (ni latidos) pero tampoco cierra: como un programa colgado.
	assert cruda.leer_tipo("latido").tipo == "latido"  # la sala sí envía los suyos
	assert esperar(lambda: alumno_de(sala, "Colgada")["conectado"] is False, 4.0)
	sucesos = [s for s in sala.eventos_pendientes() if s["tipo"] == "desconectado"]
	assert sucesos[0]["datos"]["motivo"] == "sin_latido"
	cruda.cerrar()


def test_el_cliente_detecta_por_latido_a_una_sala_colgada(clientes):
	servidor = socket.create_server(("127.0.0.1", 0))
	puerto = servidor.getsockname()[1]
	conexiones: list[socket.socket] = []

	def sala_muda() -> None:
		# Empareja bien y después calla sin cerrar.
		conexion, _origen = servidor.accept()
		conexiones.append(conexion)
		conexion.settimeout(3.0)
		reto = "cd" * 16
		conexion.sendall(protocolo.codificar("reto", {"nonce": reto}, sentido=A_JUGAR))
		troceador = LectorLineas()
		lineas: list[bytes | None] = []
		while not lineas:
			lineas = troceador.alimentar(conexion.recv(4096))
		saludo = protocolo.decodificar(lineas[0], A_ESTUDIO)
		prueba = seguridad.prueba_sala(CODIGO, reto, saludo.datos["nonce"], "")
		conexion.sendall(protocolo.codificar("bienvenida", {"prueba": prueba, "alumno": "Luna"}, sentido=A_JUGAR))

	hilo = threading.Thread(target=sala_muda, daemon=True)
	hilo.start()
	cliente = _cliente(clientes, puerto, tiempo_muerto=0.5, reintento_min=5.0, reintento_max=5.0)
	assert esperar(lambda: cliente.conectado)
	assert esperar(lambda: not cliente.conectado, 4.0)
	avisos = cliente.avisos_pendientes()
	assert ("desconectado", {"motivo": "sin_latido"}) in avisos
	hilo.join(timeout=3)
	for conexion in conexiones:
		conexion.close()
	servidor.close()


def test_reconexion_automatica_cuando_la_sala_vuelve(clientes):
	primera = Sala(intervalo_latido=0.2, tiempo_muerto=1.0)
	primera.iniciar(0, CODIGO)
	puerto = primera.puerto
	cliente = _cliente(clientes, puerto)
	assert esperar(lambda: cliente.conectado)
	cliente.estado(espacio="Cocina", tiempo_activo=5.0)
	assert esperar(lambda: (alumno_de(primera, "Luna") or {}).get("espacio") == "Cocina")
	primera.detener()
	assert esperar(lambda: not cliente.conectado)
	assert primera.foto()["alumnos"][0]["conectado"] is False
	# El juego sigue mientras tanto: lo que pasa se guarda para cuando vuelva la sala.
	cliente.evento("choque", {"con": "silla"})
	cliente.evento("objetivo", {"nombre": "Llegar al baño"})
	cliente.voz("Esto se pierde: la voz atrasada no interesa")
	cliente.estado(espacio="Baño", tiempo_activo=9.0)
	segunda = Sala(intervalo_latido=0.2, tiempo_muerto=1.0)
	segunda.iniciar(puerto, CODIGO)
	try:
		assert esperar(lambda: cliente.conectado, 5.0)
		assert cliente.conexiones == 2
		sucesos: list[dict] = []
		assert esperar(lambda: _tipos(segunda, sucesos).count("evento") == 2)
		assert [s["datos"]["tipo"] for s in sucesos if s["tipo"] == "evento"] == ["choque", "objetivo"]
		assert "voz" not in [s["tipo"] for s in sucesos]
		assert esperar(lambda: alumno_de(segunda, "Luna")["espacio"] == "Baño")
		tipos_aviso = [tipo for tipo, _datos in cliente.avisos_pendientes()]
		assert tipos_aviso == ["conectado", "desconectado", "conectado"]
	finally:
		segunda.detener()


def test_un_corte_y_vuelta_conserva_la_ficha_del_alumno(sala, clientes):
	cliente = _cliente(clientes, sala.puerto)
	assert esperar(lambda: cliente.conectado)
	cliente.voz("Primera frase.")
	assert esperar(lambda: (alumno_de(sala, "Luna") or {}).get("ultimo_texto") == "Primera frase.")
	assert sala.expulsar("Luna")
	assert esperar(lambda: cliente.estado_conexion == RECHAZADO and cliente.motivo_rechazo == "expulsado")
	assert esperar(lambda: alumno_de(sala, "Luna")["conectado"] is False)
	cliente.reintentar()
	assert esperar(lambda: cliente.conectado)
	alumno = alumno_de(sala, "Luna")
	assert len(sala.foto()["alumnos"]) == 1  # es el mismo, no «Luna (2)»
	assert alumno["reconexiones"] == 1
	assert alumno["ultimo_texto"] == "Primera frase."
	assert "reconectado" in [s["tipo"] for s in sala.eventos_pendientes()]


def test_el_cliente_nunca_bloquea_al_juego(clientes):
	# Un puerto donde no escucha nadie.
	libre = socket.create_server(("127.0.0.1", 0))
	puerto = libre.getsockname()[1]
	libre.close()
	cliente = _cliente(clientes, puerto, espera_conexion=2.0)
	inicio = time.perf_counter()
	for fotograma in range(2000):
		cliente.estado(planta="p0", x=float(fotograma), y=0.0, rumbo=0.0, tiempo_activo=fotograma / 60.0)
		cliente.evento("paso", {"n": fotograma})
		cliente.voz("texto")
		cliente.ordenes_pendientes()
		cliente.avisos_pendientes()
	transcurrido = time.perf_counter() - inicio
	assert transcurrido < 1.0, f"2000 fotogramas tardaron {transcurrido:.2f} s"
	assert not cliente.conectado
	# La cola de salida está acotada: una sala ausente no llena la memoria.
	assert len(cliente._salida) <= 500
	inicio = time.perf_counter()
	cliente.detener(espera=3.0)
	assert time.perf_counter() - inicio < 3.5
	assert cliente.estado_conexion == "parado"


def test_el_fin_sale_antes_de_parar(sala, clientes):
	cliente = _cliente(clientes, sala.puerto)
	assert esperar(lambda: cliente.conectado)
	cliente.fin(completada=False, resultado={"motivo": "salir"})
	cliente.detener()
	sucesos: list[dict] = []
	assert esperar(lambda: "desconectado" in _tipos(sala, sucesos))
	assert "fin" in [s["tipo"] for s in sucesos]
	assert alumno_de(sala, "Luna")["terminado"]


def test_sesion_de_menos_de_un_segundo_sigue_terminada_tras_el_fin(sala, clientes):
	"""El cliente no reenvía el último estado tras el ``fin``: la sala no la confunde con una sesión nueva.

	Con menos de un segundo de juego, el estado repetido (cinco veces por
	segundo) parecía el primero de una sesión reiniciada y la sala volvía a
	marcar al alumno como no terminado.
	"""
	cliente = _cliente(clientes, sala.puerto, intervalo_estado=0.02)
	assert esperar(lambda: cliente.conectado)
	cliente.estado(espacio="Salón", tiempo_activo=0.3, pausado=False)
	assert esperar(lambda: (alumno_de(sala, "Luna") or {}).get("espacio") == "Salón")
	cliente.fin(completada=True, resultado={"estrellas": 3})
	assert esperar(lambda: alumno_de(sala, "Luna")["terminado"])
	# Medio segundo son unos veinticinco estados reenviados con el fallo: ninguno debe abrirla otra vez.
	assert not esperar(lambda: not alumno_de(sala, "Luna")["terminado"], 0.5)
	assert alumno_de(sala, "Luna")["resultado"] == {"estrellas": 3}
	# Otra partida (tras «reiniciar» o «repetir») sí envía estados nuevos y empieza sin terminar.
	cliente.estado(espacio="Salón", tiempo_activo=0.0, pausado=False)
	assert esperar(lambda: not alumno_de(sala, "Luna")["terminado"])
	assert alumno_de(sala, "Luna")["resultado"] is None


# ── Arranque y parada de la sala ─────────────────────────────────────────────


def test_puerto_ocupado_da_un_error_legible(sala):
	otra = Sala()
	with pytest.raises(ErrorSala) as error:
		otra.iniciar(sala.puerto, CODIGO)
	assert str(sala.puerto) in str(error.value)
	assert not otra.activa
	# Tras el fallo se puede volver a intentar en otro puerto.
	otra.iniciar(0, CODIGO)
	assert otra.activa
	otra.detener()
	assert not otra.activa


def test_iniciar_dos_veces_y_codigo_generado():
	sala_nueva = Sala()
	sala_nueva.iniciar(0)
	try:
		assert len(sala_nueva.codigo) == 6 and sala_nueva.codigo.isdecimal()
		assert sala_nueva.foto()["direcciones"] == ["127.0.0.1"]
		with pytest.raises(ErrorSala):
			sala_nueva.iniciar(0)
	finally:
		sala_nueva.detener()
	assert sala_nueva.foto()["activa"] is False
	assert sala_nueva.pedir("Nadie", "pausa") is False


def test_sin_red_solo_escucha_en_este_ordenador(sala):
	import asyncio

	assert all(enchufe.getsockname()[0] == "127.0.0.1" for servidor in sala._servidores for enchufe in servidor.sockets)
	assert isinstance(sala._bucle, asyncio.AbstractEventLoop)


# ── Red local con TLS ────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def carpeta_certificado(tmp_path_factory):
	carpeta = tmp_path_factory.mktemp("config_sala")
	seguridad.asegurar_certificado(carpeta)
	return carpeta


@pytest.fixture
def sala_tls(carpeta_certificado):
	abierta = Sala(carpeta_config=carpeta_certificado, intervalo_latido=0.2, tiempo_muerto=1.0)
	abierta.iniciar(0, CODIGO, red=True, host="127.0.0.1", anunciar=False)
	yield abierta
	abierta.detener()


def test_conexion_cifrada_y_huella_recordada(sala_tls, clientes, tmp_path):
	almacen = seguridad.AlmacenHuellas(tmp_path / "salas.json")
	cliente = _cliente(clientes, sala_tls.puerto, tls=True, almacen=almacen)
	assert esperar(lambda: cliente.conectado)
	assert cliente.tls
	assert cliente.huella_sala == sala_tls.huella
	assert len(sala_tls.huella) == 64
	assert almacen.obtener("127.0.0.1", sala_tls.puerto) == sala_tls.huella
	cliente.estado(espacio="Cocina")
	cliente.voz("Texto que debe viajar cifrado")
	assert esperar(lambda: (alumno_de(sala_tls, "Luna") or {}).get("ultimo_texto") == "Texto que debe viajar cifrado")
	alumno = alumno_de(sala_tls, "Luna")
	assert alumno["cifrada"]
	assert sala_tls.pedir("Luna", "mensaje", texto="También cifrado")
	assert esperar(lambda: cliente.ordenes_pendientes() == [("mensaje", {"texto": "También cifrado"})])
	foto = sala_tls.foto()
	assert foto["red"] and foto["huella"] == sala_tls.huella
	assert foto["huella_legible"] == seguridad.huella_legible(sala_tls.huella)
	assert foto["puerto_local"] != foto["puerto"]


def test_el_puerto_de_red_no_acepta_conexiones_sin_cifrar(sala_tls, clientes):
	sin_cifrar = _cliente(clientes, sala_tls.puerto, tls=False, espera_conexion=1.0)
	assert not esperar(lambda: sin_cifrar.conectado, 1.5)
	assert sala_tls.foto()["alumnos"] == []
	# El puerto local sin TLS sí, para el reproductor del mismo ordenador.
	local = _cliente(clientes, sala_tls.puerto_local, alias="Local")
	assert esperar(lambda: local.conectado)
	assert not local.tls
	assert alumno_de(sala_tls, "Local")["cifrada"] is False


def test_el_trafico_cifrado_no_se_lee_en_claro(sala_tls, tmp_path):
	"""Un intermediario que reenvía los octetos tal cual no ve ni el alias ni los textos."""
	visto = bytearray()
	puente = socket.create_server(("127.0.0.1", 0))
	puerto_puente = puente.getsockname()[1]

	def reenviar(origen: socket.socket, destino: socket.socket) -> None:
		try:
			while True:
				datos = origen.recv(4096)
				if not datos:
					break
				visto.extend(datos)
				destino.sendall(datos)
		except OSError:
			return

	def intermediario() -> None:
		lado_cliente, _origen = puente.accept()
		lado_sala = socket.create_connection(("127.0.0.1", sala_tls.puerto))
		threading.Thread(target=reenviar, args=(lado_cliente, lado_sala), daemon=True).start()
		reenviar(lado_sala, lado_cliente)

	threading.Thread(target=intermediario, daemon=True).start()
	cliente = ClienteSupervision(
		"127.0.0.1",
		puerto_puente,
		CODIGO,
		"AliasSecreto",
		tls=True,
		almacen=seguridad.AlmacenHuellas(tmp_path / "s.json"),
		intervalo_estado=0.05,
	)
	cliente.iniciar()
	try:
		assert esperar(lambda: cliente.conectado)
		cliente.voz("FraseQueNadieDebeLeer")
		assert esperar(lambda: (alumno_de(sala_tls, "AliasSecreto") or {}).get("ultimo_texto") == "FraseQueNadieDebeLeer")
	finally:
		cliente.detener()
		puente.close()
	assert len(visto) > 500
	assert b"AliasSecreto" not in visto
	assert b"FraseQueNadieDebeLeer" not in visto
	assert b'"tipo"' not in visto


def test_huella_cambiada_detiene_al_cliente_hasta_que_se_acepta(sala_tls, clientes, tmp_path):
	almacen = seguridad.AlmacenHuellas(tmp_path / "salas.json")
	almacen.recordar("127.0.0.1", sala_tls.puerto, "0" * 64)  # como si antes hubiera otra sala en esa dirección
	cliente = _cliente(clientes, sala_tls.puerto, tls=True, almacen=almacen)
	assert esperar(lambda: cliente.estado_conexion == RECHAZADO)
	assert cliente.motivo_rechazo == "huella"
	assert cliente.huella_sala == sala_tls.huella  # para enseñársela a la persona
	# No ha llegado a saludar: la sala no sabe ni su alias, y no cuenta como código incorrecto.
	assert sala_tls.foto()["alumnos"] == []
	assert [s["tipo"] for s in sala_tls.eventos_pendientes()] == []
	assert almacen.obtener("127.0.0.1", sala_tls.puerto) == "0" * 64
	cliente.aceptar_huella_nueva()
	assert esperar(lambda: cliente.conectado)
	assert almacen.obtener("127.0.0.1", sala_tls.puerto) == sala_tls.huella


def test_codigo_incorrecto_por_tls_no_recuerda_la_huella(sala_tls, clientes, tmp_path):
	almacen = seguridad.AlmacenHuellas(tmp_path / "salas.json")
	cliente = _cliente(clientes, sala_tls.puerto, codigo="999999", tls=True, almacen=almacen)
	assert esperar(lambda: cliente.estado_conexion == RECHAZADO)
	assert cliente.motivo_rechazo == "codigo"
	assert almacen.obtener("127.0.0.1", sala_tls.puerto) is None
