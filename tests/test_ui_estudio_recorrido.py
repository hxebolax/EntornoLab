"""Pruebas del modo recorrido: la lógica sin wx, la sesión con un doble del reproductor y el controlador.

El doble del reproductor es un ``ClienteSupervision`` real conectado a la
sala local: habla el mismo protocolo que hablará el reproductor de verdad,
pero no arranca ningún proceso.
"""

from __future__ import annotations

import pytest

from app.dominio import edicion as ed
from app.dominio.formato import cargar_paquete
from app.dominio.modelo import Posicion
from app.supervision.cliente import ClienteSupervision
from app.ui import recorrido
from app.ui.contexto import ContextoEstudio
from app.ui.recorrido import ErrorRecorrido, SesionRecorrido
from tests._supervision_util import esperar
from tests.test_dominio_comun import catalogo_de_prueba, piso_minimo


class ProcesoFalso:
	"""Lo que el Estudio usa de un ``Proceso``, sin proceso."""

	def __init__(self) -> None:
		self.terminado = False

	def vivo(self) -> bool:
		return not self.terminado

	def terminar(self, espera: float = 3.0) -> int:
		self.terminado = True
		return 0

	def esperar(self, tiempo: float | None = None) -> int | None:
		return 0 if self.terminado else None


class DobleReproductor:
	"""Lanzador falso: en vez de un proceso, un cliente de supervisión en modo recorrido."""

	def __init__(self, tmp_path) -> None:
		self.tmp_path = tmp_path
		self.argumentos: list[str] = []
		self.cliente: ClienteSupervision | None = None
		self.proceso = ProcesoFalso()
		self.respuestas: list[dict] = []
		self.ordenes: list[tuple[str, dict]] = []

	def __call__(self, argumentos: list[str]) -> ProcesoFalso:
		self.argumentos = list(argumentos)
		host, _sep, puerto = argumentos[argumentos.index("--sala") + 1].partition(":")
		codigo = argumentos[argumentos.index("--codigo") + 1]
		self.cliente = ClienteSupervision(
			host,
			int(puerto),
			codigo,
			"Profe",
			entorno="Piso",
			modo="practica",
			recorrido=True,
			carpeta_config=self.tmp_path / "cfg_cliente",
			intervalo_estado=0.05,
		)
		self.cliente.iniciar()
		return self.proceso

	def leer(self) -> None:
		"""Pasa a las listas lo que haya llegado del Estudio."""
		for tipo, datos in self.cliente.ordenes_pendientes():
			self.ordenes.append((tipo, datos))
			if tipo == "respuesta":
				self.respuestas.append(datos)

	def cerrar(self) -> None:
		if self.cliente is not None:
			self.cliente.detener()


@pytest.fixture
def catalogo(tmp_path):
	return catalogo_de_prueba(tmp_path)


@pytest.fixture
def contexto(catalogo):
	entorno, _planta, _salon, _cocina = piso_minimo()
	ctx = ContextoEstudio(catalogo=catalogo)
	ctx.abrir_documento(entorno)
	return ctx


@pytest.fixture
def sesion(contexto):
	return SesionRecorrido(contexto)


def _planta(contexto):
	return contexto.entorno.plantas[0]


def _bombear(sesion: SesionRecorrido, condicion, segundos: float = 5.0) -> list[str]:
	"""Llama a ``atender`` (como haría el temporizador) hasta que se cumple la condición."""
	frases: list[str] = []

	def paso() -> bool:
		frases.extend(sesion.atender())
		return bool(condicion())

	assert esperar(paso, segundos), "no se cumplió la condición bombeando la sesión"
	return frases


# ── resolver: la lógica pura ─────────────────────────────────────────────────


def test_acciones_y_sinonimos():
	assert recorrido.normalizar_accion("colocar_aqui") == recorrido.COLOCAR
	assert recorrido.normalizar_accion("Poner aquí el inicio") == recorrido.INICIO
	assert recorrido.normalizar_accion("marcar_punto", {"tipo": "inicio"}) == recorrido.INICIO
	assert recorrido.normalizar_accion("marcar_punto", {"nombre": "Timbre"}) == recorrido.MARCAR
	assert recorrido.normalizar_accion("medir") == recorrido.MEDIR
	assert recorrido.normalizar_accion("bailar") == ""
	# La convención del reproductor real: ``colocar_aqui`` con ``clase``.
	assert recorrido.normalizar_accion("colocar_aqui", {"clase": "objeto", "objeto": "prueba/mesa"}) == recorrido.COLOCAR
	assert recorrido.normalizar_accion("colocar_aqui", {"clase": "premio", "nombre": "Llave"}) == recorrido.PREMIO
	assert recorrido.normalizar_accion("colocar_aqui", {"clase": "inicio"}) == recorrido.INICIO
	assert recorrido.normalizar_accion("colocar_aqui", {"clase": "nave espacial"}) == ""
	# Sin ``clase`` se deduce como antes.
	assert recorrido.normalizar_accion("colocar_aqui", {"objeto": "prueba/mesa"}) == recorrido.COLOCAR
	assert recorrido.normalizar_accion("colocar_aqui", {"tipo": "inicio"}) == recorrido.INICIO


def test_colocar_un_objeto_que_cabe(sesion, contexto):
	planta = _planta(contexto)
	respuesta = sesion.resolver("colocar_aqui", planta.id, 2.0, 2.0, 90.0, {"objeto": "prueba/mesa"})
	assert respuesta.aceptada, respuesta.texto
	objetos = _planta(contexto).objetos
	assert len(objetos) == 1 and objetos[0].tipo == "prueba/mesa"
	assert objetos[0].x == pytest.approx(2.0) and objetos[0].rumbo == pytest.approx(90.0)
	assert respuesta.datos["objeto_id"] == objetos[0].id
	assert respuesta.datos["recargar"] is True
	assert cargar_paquete(respuesta.datos["paquete"]).entorno.plantas[0].objetos[0].id == objetos[0].id
	assert "colocado" in respuesta.texto
	assert contexto.seleccion == objetos[0].id
	# Entra en el historial con su nombre y se puede deshacer.
	assert "recorriendo" in contexto.historial.texto_deshacer()
	contexto.deshacer()
	assert _planta(contexto).objetos == []


def test_objeto_que_no_cabe_no_se_coloca(sesion, contexto):
	planta = _planta(contexto)
	antes = contexto.entorno.a_dict()
	# Fuera de todo espacio.
	respuesta = sesion.resolver("colocar_aqui", planta.id, 50.0, 50.0, 0.0, {"objeto": "prueba/mesa"})
	assert not respuesta.aceptada and respuesta.texto
	# En un cuarto diminuto, donde no cabe ni encogida.
	contexto.ejecutar(
		"crear trastero", lambda: ed.crear_habitacion_rectangular(contexto.entorno, _planta(contexto), "Trastero", 20, 20, 0.3, 0.3)
	)
	con_trastero = contexto.entorno.a_dict()
	niveles = len(contexto.historial.operaciones())
	respuesta = sesion.resolver("colocar_aqui", planta.id, 20.15, 20.15, 0.0, {"objeto": "prueba/mesa"})
	assert not respuesta.aceptada
	assert "recargar" not in respuesta.datos
	assert contexto.entorno.a_dict() == con_trastero != antes
	assert len(contexto.historial.operaciones()) == niveles, "un intento fallido no deja nada que deshacer"
	# Un objeto que no existe en el catálogo tampoco.
	assert not sesion.resolver("colocar_aqui", planta.id, 2.0, 2.0, 0.0, {"objeto": "prueba/no_existe"}).aceptada
	assert _planta(contexto).objetos == []


def test_colocar_sin_decir_objeto_abre_el_catalogo(contexto):
	pedidos = []

	def pedir_objeto(planta_id, x, y, rumbo):
		pedidos.append((planta_id, x, y, rumbo))
		referencia = ed.anadir_referencia(contexto.entorno, contexto.entorno.planta(planta_id), "Sustituto", x, y)
		return referencia.id

	sesion = SesionRecorrido(contexto, pedir_objeto=pedir_objeto)
	planta = _planta(contexto)
	respuesta = sesion.resolver("colocar_aqui", planta.id, 1.0, 1.5, 180.0, {})
	assert pedidos == [(planta.id, 1.0, 1.5, 180.0)]
	assert respuesta.aceptada and respuesta.datos["recargar"] is True
	# Si en el catálogo se cancela, no se coloca nada.
	cancelada = SesionRecorrido(contexto, pedir_objeto=lambda *a: None).resolver("colocar_aqui", planta.id, 1.0, 1.5, 0.0, {})
	assert not cancelada.aceptada
	# Sin interfaz que pregunte, falta el dato.
	assert not SesionRecorrido(contexto).resolver("colocar_aqui", planta.id, 1.0, 1.5, 0.0, {}).aceptada


def test_poner_aqui_el_inicio(sesion, contexto):
	planta = _planta(contexto)
	respuesta = sesion.resolver("marcar_punto", planta.id, 6.0, 1.0, 270.0, {"tipo": "inicio"})
	assert respuesta.aceptada and respuesta.datos["recargar"] is True
	inicio = contexto.entorno.inicio
	assert (inicio.planta, inicio.x, inicio.y, inicio.rumbo) == (planta.id, 6.0, 1.0, 270.0)
	assert sesion.resolver("poner_inicio", planta.id, 1.0, 1.0, 0.0, {}).aceptada
	assert contexto.entorno.inicio.x == 1.0


def test_marcar_este_punto(contexto):
	sesion = SesionRecorrido(contexto, pedir_nombre=lambda propuesta: "Timbre de " + propuesta)
	planta = _planta(contexto)
	respuesta = sesion.resolver("marcar_punto", planta.id, 3.0, 3.0, 0.0, {"nombre": "Enchufe"})
	assert respuesta.aceptada and "Enchufe" in respuesta.texto
	preguntada = sesion.resolver("marcar_punto", planta.id, 4.0, 3.0, 0.0, {})
	assert preguntada.aceptada
	nombres = [referencia.nombre for referencia in _planta(contexto).referencias]
	assert nombres[0] == "Enchufe" and nombres[1].startswith("Timbre de ")
	assert preguntada.datos["referencia_id"] == _planta(contexto).referencias[1].id
	cancelada = SesionRecorrido(contexto, pedir_nombre=lambda propuesta: None).resolver("marcar_punto", planta.id, 4.0, 3.0, 0.0, {})
	assert not cancelada.aceptada and len(_planta(contexto).referencias) == 2


def test_medir_en_dos_pasos(sesion, contexto):
	planta = _planta(contexto)
	primera = sesion.resolver("medir_desde_aqui", planta.id, 1.0, 1.0, 0.0, {})
	assert primera.aceptada and primera.datos == {"origen": True}
	segunda = sesion.resolver("medir_desde_aqui", planta.id, 4.0, 5.0, 0.0, {})
	assert segunda.aceptada
	assert segunda.datos["distancia_m"] == pytest.approx(5.0)
	assert "5 metros" in segunda.texto and "noreste" in segunda.texto
	assert "recargar" not in segunda.datos, "medir no cambia el entorno"
	assert not contexto.historial.puede_deshacer
	# Tras medir se empieza de nuevo: la siguiente vuelve a fijar el origen.
	assert sesion.resolver("medir_desde_aqui", planta.id, 0.0, 0.0, 0.0, {}).datos == {"origen": True}


def test_medir_hasta_un_elemento(sesion, contexto):
	planta = _planta(contexto)
	cocina = planta.espacios[1]
	respuesta = sesion.resolver("medir_desde_aqui", planta.id, 2.5, 2.0, 0.0, {"hasta": cocina.id})
	assert respuesta.aceptada and cocina.nombre in respuesta.texto
	assert respuesta.datos["distancia_m"] == pytest.approx(4.0)
	assert not sesion.resolver("medir_desde_aqui", planta.id, 2.5, 2.0, 0.0, {"hasta": "no-existe"}).aceptada


# ── La convención del reproductor real: ``clase`` y ``fase`` ─────────────────


def test_clase_objeto_coloca_el_objeto_con_su_nombre(sesion, contexto):
	planta = _planta(contexto)
	respuesta = sesion.resolver(
		"colocar_aqui", planta.id, 2.0, 2.0, 0.0, {"clase": "objeto", "objeto": "prueba/mesa", "nombre": "Mesa del salón"}
	)
	assert respuesta.aceptada and respuesta.datos["recargar"] is True
	assert [objeto.nombre for objeto in _planta(contexto).objetos] == ["Mesa del salón"]
	assert "Mesa del salón" in respuesta.texto


def test_clase_inicio_pone_el_inicio(sesion, contexto):
	planta = _planta(contexto)
	respuesta = sesion.resolver("colocar_aqui", planta.id, 6.5, 2.5, 135.0, {"clase": "inicio"})
	assert respuesta.aceptada and respuesta.datos["recargar"] is True
	inicio = contexto.entorno.inicio
	assert (inicio.x, inicio.y, inicio.rumbo) == (6.5, 2.5, 135.0)
	assert _planta(contexto).objetos == [] and _planta(contexto).referencias == []


def test_clase_desconocida_no_hace_nada(sesion, contexto):
	planta = _planta(contexto)
	antes = contexto.entorno.a_dict()
	assert not sesion.resolver("colocar_aqui", planta.id, 2.0, 2.0, 0.0, {"clase": "dragon"}).aceptada
	assert contexto.entorno.a_dict() == antes


def test_clase_premio_con_actividad_abierta(sesion, contexto, tmp_path):
	planta = _planta(contexto)
	actividad = {
		"formato": 1,
		"id": "busca",
		"nombre": "Busca la llave",
		"tipo": "busqueda",
		"premios": [{"id": "premio-1", "nombre": "Moneda"}],
	}
	contexto.actividades.append(actividad)
	contexto.actividad_actual = actividad
	avisos: list[str] = []
	contexto.suscribir("actividades_cambiadas", lambda: avisos.append("cambio"))
	assert contexto.guardar(tmp_path / "piso.elab")
	respuesta = sesion.resolver("colocar_aqui", planta.id, 1.5, 3.0, 0.0, {"clase": "premio", "nombre": "Llave"})
	assert respuesta.aceptada, respuesta.texto
	assert "Llave" in respuesta.texto and "Busca la llave" in respuesta.texto
	premio = actividad["premios"][1]
	assert premio["nombre"] == "Llave" and premio["planta"] == planta.id and (premio["x"], premio["y"]) == (1.5, 3.0)
	assert premio["visibilidad"] == "cerca" and premio["dentro_de"] is None and premio["sonido"] == "" and premio["mensaje"] == ""
	assert premio["id"] not in ("", "premio-1") and respuesta.datos["premio_id"] == premio["id"]
	assert respuesta.datos["recargar"] is True and avisos
	# Queda guardado en el paquete, con su actividad, y el entorno no ha cambiado.
	guardado = cargar_paquete(tmp_path / "piso.elab")
	assert [p["nombre"] for p in guardado.actividad("busca")["premios"]] == ["Moneda", "Llave"]
	assert not contexto.historial.puede_deshacer and contexto.modificado is False
	# La forma es la que entiende el paquete de actividades.
	from app.actividades.formato import normalizar_premio

	assert normalizar_premio(premio, 2, set()) == premio


def test_clase_premio_sin_actividad_abierta(sesion, contexto):
	planta = _planta(contexto)
	respuesta = sesion.resolver("colocar_aqui", planta.id, 1.5, 3.0, 0.0, {"clase": "premio", "nombre": "Llave"})
	assert not respuesta.aceptada and "Actividades" in respuesta.texto
	assert "recargar" not in respuesta.datos
	# Una actividad que no es del paquete abierto tampoco vale.
	contexto.actividad_actual = {"id": "ajena", "nombre": "Ajena", "premios": []}
	assert not sesion.resolver("colocar_aqui", planta.id, 1.5, 3.0, 0.0, {"clase": "premio", "nombre": "Llave"}).aceptada
	assert contexto.actividad_actual["premios"] == [] and contexto.modificado is False


def test_medir_con_fase(sesion, contexto):
	planta = _planta(contexto)
	desde = sesion.resolver("medir_desde_aqui", planta.id, 1.0, 1.0, 0.0, {"fase": "desde"})
	assert desde.aceptada and desde.datos == {"origen": True}
	# Otro «desde» mueve el origen en lugar de medir.
	assert sesion.resolver("medir_desde_aqui", planta.id, 1.0, 2.0, 0.0, {"fase": "desde"}).datos == {"origen": True}
	# «hasta» repite la distancia que el reproductor ya ha dicho y añade el punto cardinal.
	hasta = sesion.resolver("medir_desde_aqui", planta.id, 4.0, 2.0, 0.0, {"fase": "hasta", "distancia_m": 3.0})
	assert hasta.aceptada and hasta.datos["distancia_m"] == pytest.approx(3.0)
	assert "3 metros" in hasta.texto and "este" in hasta.texto
	assert "recargar" not in hasta.datos and not contexto.historial.puede_deshacer
	# Sin distancia (el reproductor no la calculó) la calcula el Estudio.
	sesion.resolver("medir_desde_aqui", planta.id, 0.0, 0.0, 0.0, {"fase": "desde"})
	calculada = sesion.resolver("medir_desde_aqui", planta.id, 0.0, 2.5, 0.0, {"fase": "hasta"})
	assert calculada.datos["distancia_m"] == pytest.approx(2.5) and "norte" in calculada.texto
	# «hasta» sin origen: no se puede, salvo que el reproductor traiga ya la distancia.
	assert not sesion.resolver("medir_desde_aqui", planta.id, 0.0, 2.5, 0.0, {"fase": "hasta"}).aceptada
	sin_origen = sesion.resolver("medir_desde_aqui", planta.id, 0.0, 2.5, 0.0, {"fase": "hasta", "distancia_m": 7.25})
	assert sin_origen.aceptada and "7,25 metros" in sin_origen.texto


def test_medir_con_el_origen_en_otra_planta(sesion, contexto):
	contexto.ejecutar("crear planta", lambda: ed.crear_planta(contexto.entorno, "Primera"))
	baja, primera = contexto.entorno.plantas
	sesion.resolver("medir_desde_aqui", baja.id, 1.0, 1.0, 0.0, {"fase": "desde"})
	respuesta = sesion.resolver("medir_desde_aqui", primera.id, 1.0, 1.0, 0.0, {"fase": "hasta"})
	assert respuesta.aceptada and "otra planta" in respuesta.texto
	assert respuesta.datos["misma_planta"] is False and respuesta.datos["desnivel_m"] == pytest.approx(3.0)


def test_peticiones_que_no_se_pueden_atender(sesion, contexto):
	planta = _planta(contexto)
	assert not sesion.resolver("bailar", planta.id, 1.0, 1.0, 0.0, {}).aceptada
	assert not sesion.resolver("marcar_punto", "planta-que-no-existe", 1.0, 1.0, 0.0, {"nombre": "X"}).aceptada
	assert not sesion.resolver("marcar_punto", planta.id, float("nan"), 1.0, 0.0, {"nombre": "X"}).aceptada
	assert _planta(contexto).referencias == []
	contexto.cerrar_documento()
	assert not sesion.resolver("marcar_punto", planta.id, 1.0, 1.0, 0.0, {"nombre": "X"}).aceptada


def test_argumentos_del_reproductor(tmp_path):
	ruta = tmp_path / "casa.elab"
	assert recorrido.argumentos_reproductor(ruta, 5123, "ABCD") == [
		"--recorrido",
		str(ruta),
		"--sala",
		"127.0.0.1:5123",
		"--codigo",
		"ABCD",
	]
	con_inicio = recorrido.argumentos_reproductor(ruta, 5123, "ABCD", Posicion("pla-1", 1.5, 2.0, 90.0))
	assert con_inicio[-2:] == ["--inicio", "pla-1,1.500,2.000,90.0"]


# ── Sesión completa con un doble del reproductor ─────────────────────────────


@pytest.fixture
def doble(tmp_path):
	reproductor = DobleReproductor(tmp_path)
	yield reproductor
	reproductor.cerrar()


def test_sesion_completa_con_doble_del_reproductor(catalogo, tmp_path, doble):
	entorno, planta, _salon, _cocina = piso_minimo()
	contexto = ContextoEstudio(catalogo=catalogo, lanzador=doble)
	ruta = tmp_path / "entornos" / "piso.elab"
	contexto.abrir_documento(entorno)
	assert contexto.guardar(ruta)
	sesion = SesionRecorrido(contexto)
	try:
		sesion.iniciar()
		assert sesion.activa
		sala = sesion.sala
		assert doble.argumentos == [
			"--recorrido",
			str(ruta),
			"--sala",
			f"127.0.0.1:{sala.puerto_local or sala.puerto}",
			"--codigo",
			sala.codigo,
		]
		frases = _bombear(sesion, lambda: doble.cliente.conectado)
		_bombear(sesion, lambda: any(a["conectado"] and a["recorrido"] for a in sala.foto()["alumnos"]))

		# El profesional pide colocar una mesa donde está.
		ident = doble.cliente.peticion("colocar_aqui", planta=planta.id, x=2.0, y=2.0, rumbo=0.0, objeto="prueba/mesa")
		frases += _bombear(sesion, lambda: contexto.entorno.plantas[0].objetos)
		assert any("colocado" in frase for frase in frases)
		assert esperar(lambda: (doble.leer(), doble.respuestas)[1])
		respuesta = doble.respuestas[0]
		assert respuesta["id"] == ident and respuesta["aceptada"] is True and "colocado" in respuesta["texto"]
		assert respuesta["datos"]["recargar"] is True and respuesta["datos"]["paquete"] == str(ruta)
		guardado = cargar_paquete(ruta).entorno
		assert [objeto.tipo for objeto in guardado.plantas[0].objetos] == ["prueba/mesa"]
		assert contexto.modificado is False, "tras la petición el paquete queda guardado"

		# Una petición que no se puede atender también recibe respuesta, y no cambia nada.
		otra = doble.cliente.peticion("colocar_aqui", planta=planta.id, x=80.0, y=80.0, rumbo=0.0, objeto="prueba/mesa")
		assert esperar(lambda: (sesion.atender(), doble.leer(), len(doble.respuestas) == 2)[2])
		assert doble.respuestas[1]["id"] == otra and doble.respuestas[1]["aceptada"] is False
		assert len(contexto.entorno.plantas[0].objetos) == 1

		# Un cambio hecho en el Estudio durante el recorrido se guarda y se avisa.
		contexto.ejecutar("marcar", lambda: ed.anadir_referencia(contexto.entorno, contexto.entorno.plantas[0], "Reloj", 1.0, 1.0))
		assert sesion.guardar_y_avisar() is True
		assert recorrido.ORDEN_RECARGA == "reiniciar"
		assert esperar(lambda: (doble.leer(), any(tipo == "reiniciar" for tipo, _datos in doble.ordenes))[1])
		assert [r.nombre for r in cargar_paquete(ruta).entorno.plantas[0].referencias] == ["Reloj"]

		# Detener pide terminar, termina el proceso y cierra la sala.
		sesion.detener()
		assert not sesion.activa and doble.proceso.terminado and not sala.activa
		assert sesion.atender() == []
	finally:
		sesion.detener()


def test_el_recorrido_termina_solo_cuando_el_reproductor_se_cierra(catalogo, tmp_path, doble):
	entorno, _planta_, _salon, _cocina = piso_minimo()
	contexto = ContextoEstudio(catalogo=catalogo, lanzador=doble)
	contexto.abrir_documento(entorno)
	sesion = SesionRecorrido(contexto)
	try:
		sesion.iniciar(Posicion(entorno.plantas[0].id, 1.0, 1.0, 45.0))
		# Un entorno sin guardar se recorre desde una copia temporal, sin ponerle ruta ni darlo por guardado.
		assert contexto.ruta_paquete is None
		assert "temp" in str(sesion.paquete) and sesion.paquete.is_file()
		assert doble.argumentos[-2] == "--inicio"
		sala = sesion.sala
		doble.proceso.terminado = True
		frases = _bombear(sesion, lambda: not sesion.activa)
		assert any("terminado" in frase.lower() for frase in frases)
		assert not sala.activa
	finally:
		sesion.detener()


def test_no_se_recorre_sin_entorno_ni_un_entorno_vacio(catalogo):
	contexto = ContextoEstudio(catalogo=catalogo, lanzador=lambda argumentos: pytest.fail("no debe lanzarse"))
	with pytest.raises(ErrorRecorrido):
		SesionRecorrido(contexto).iniciar()
	contexto.abrir_documento(ed.crear_entorno("Vacío"))
	sesion = SesionRecorrido(contexto)
	with pytest.raises(ErrorRecorrido):
		sesion.iniciar()
	assert not sesion.activa and sesion.sala is None


def test_si_el_reproductor_no_arranca_no_queda_la_sala_abierta(catalogo):
	from app.core.procesos import ErrorProceso
	from app.supervision.sala import Sala

	def lanzador(argumentos):
		raise ErrorProceso("No está el ejecutable del reproductor.")

	entorno, *_resto = piso_minimo()
	contexto = ContextoEstudio(catalogo=catalogo, lanzador=lanzador)
	contexto.abrir_documento(entorno)
	sala = Sala(nombre="Prueba")
	sesion = SesionRecorrido(contexto, sala=sala)
	with pytest.raises(ErrorProceso):
		sesion.iniciar()
	assert not sesion.activa and not sala.activa


# ── Controlador con wx ───────────────────────────────────────────────────────


def test_controlador_arranca_y_para_el_temporizador(marco, catalogo, tmp_path, doble, dialogo_modal, monkeypatch):
	import wx

	from app.ui import recorrido_wx

	entorno, planta, _salon, _cocina = piso_minimo()
	anuncios: list[str] = []
	contexto = ContextoEstudio(ventana=marco, catalogo=catalogo, lanzador=doble)
	monkeypatch.setattr(contexto, "anunciar", lambda texto, interrumpir=False: anuncios.append(texto))
	contexto.abrir_documento(entorno)
	controlador = recorrido_wx.ControladorRecorrido(contexto)
	try:
		assert controlador.iniciar() is True
		assert controlador.activo and controlador.temporizador_en_marcha
		assert esperar(lambda: doble.cliente.conectado)
		# Marcar un punto sin nombre abre el diálogo accesible (aquí, simulado) con la propuesta.
		dialogo_modal.responder(lambda d: (d.campo.SetValue("Timbre"), wx.ID_OK)[1])
		doble.cliente.peticion("marcar_punto", planta=planta.id, x=1.0, y=1.0, rumbo=0.0)
		assert esperar(lambda: (controlador.atender(), contexto.entorno.plantas[0].referencias)[1])
		assert contexto.entorno.plantas[0].referencias[0].nombre == "Timbre"
		assert dialogo_modal.ultimo.titulo == "Marcar este punto"
		assert any("Timbre" in texto for texto in anuncios)
		controlador.detener()
		assert not controlador.activo and not controlador.temporizador_en_marcha
		assert doble.proceso.terminado
	finally:
		controlador.detener()


def test_controlador_explica_por_que_no_arranca(marco, catalogo, dialogo_modal):
	from app.ui import recorrido_wx

	contexto = ContextoEstudio(ventana=marco, catalogo=catalogo, lanzador=lambda argumentos: pytest.fail("no debe lanzarse"))
	controlador = recorrido_wx.ControladorRecorrido(contexto)
	assert controlador.iniciar() is False
	assert not controlador.activo and not controlador.temporizador_en_marcha
	assert "entorno" in " ".join(dialogo_modal.ultimo.textos).lower()


# ── Contra el reproductor real (en este mismo proceso, sin ventana ni sonido) ─


def test_con_el_reproductor_real(catalogo, data_temporal, monkeypatch):
	"""El reproductor de verdad (``Aplicacion`` en modo de pruebas) pide con su menú de edición y el Estudio resuelve.

	No se lanza otro proceso: el lanzador crea la aplicación pygame aquí, con
	los mismos argumentos que recibiría ``main.py``, y la prueba la hace
	avanzar fotograma a fotograma mientras bombea la sesión del Estudio.
	"""
	pygame = pytest.importorskip("pygame")
	comun = pytest.importorskip("tests.test_reproductor_comun")
	import webbrowser

	monkeypatch.setattr(webbrowser, "open", lambda *a, **k: True)
	creadas = []

	class ProcesoEnCasa(ProcesoFalso):
		def terminar(self, espera: float = 3.0) -> int:
			self.terminado = True
			return 0

	proceso = ProcesoEnCasa()

	def lanzador(argumentos: list[str]) -> ProcesoFalso:
		creadas.append((list(argumentos), comun.crear_app(*argumentos, "--alumno", "Profe")))
		return proceso

	original = cargar_paquete(comun.VIVIENDA)
	contexto = ContextoEstudio(catalogo=catalogo, lanzador=lanzador)
	ruta = data_temporal / "entornos" / "mi-vivienda.elab"
	contexto.abrir_documento(original.entorno)
	actividad = {"formato": 1, "id": "tesoro", "nombre": "El tesoro", "tipo": "busqueda", "premios": []}
	contexto.actividades.append(actividad)
	assert contexto.guardar(ruta)
	sesion = SesionRecorrido(contexto)
	aplicacion = None
	try:
		sesion.iniciar()
		argumentos, aplicacion = creadas[0]
		assert argumentos[0] == "--recorrido" and argumentos[1] == str(ruta)
		robot = comun.Robot(aplicacion)
		frases: list[str] = []

		def hasta(condicion, segundos: float = 8.0) -> bool:
			def paso() -> bool:
				robot.esperar(1)
				frases.extend(sesion.atender())
				return bool(condicion())

			return esperar(paso, segundos)

		assert hasta(lambda: aplicacion.enlace is not None and aplicacion.enlace.conectado), (
			"el reproductor real no se conectó a la sala del Estudio"
		)
		partida = robot.partida
		assert partida.recorrido

		# «Poner aquí el inicio» desde el menú de edición del reproductor.
		donde = (round(robot.jugador.x, 3), round(robot.jugador.y, 3))
		robot.tecla(pygame.K_F4)
		robot.elegir("Poner aquí el inicio")
		assert hasta(lambda: contexto.historial.puede_deshacer), "el Estudio no recibió la petición"
		assert (contexto.entorno.inicio.x, contexto.entorno.inicio.y) == donde
		assert hasta(lambda: "Inicio puesto aquí." in robot.dicho()), "el reproductor no dijo la respuesta del Estudio"
		assert hasta(lambda: "Entorno actualizado." in robot.dicho()), "el reproductor no recargó el paquete"
		assert cargar_paquete(ruta).entorno.inicio.x == donde[0]

		# «Marcar este punto», con el nombre que se escribe en el reproductor.
		robot.tecla(pygame.K_F4)
		robot.elegir("Marcar este punto")
		robot.tecla(pygame.K_RETURN)
		assert hasta(lambda: any(r.nombre == "Punto" for planta in contexto.entorno.plantas for r in planta.referencias))
		assert hasta(lambda: "Punto: punto marcado." in robot.dicho())

		# «Poner un premio aquí»: sin actividad abierta en el Estudio se explica; con ella, se añade.
		robot.tecla(pygame.K_F4)
		robot.elegir("Poner un premio aquí")
		robot.tecla(pygame.K_RETURN)
		assert hasta(lambda: "pestaña Actividades" in robot.dicho())
		assert actividad["premios"] == []
		contexto.actividad_actual = actividad
		robot.tecla(pygame.K_F4)
		robot.elegir("Poner un premio aquí")
		robot.tecla(pygame.K_RETURN)
		assert hasta(lambda: actividad["premios"])
		assert actividad["premios"][0]["nombre"] == "Premio" and actividad["premios"][0]["planta"] == robot.jugador.planta
		assert hasta(lambda: len(cargar_paquete(ruta).actividad("tesoro")["premios"]) == 1)

		# Medir desde aquí y hasta aquí.
		robot.tecla(pygame.K_F4)
		robot.elegir("Medir desde aquí")
		assert hasta(lambda: sesion.origen_medida is not None)
		robot.tecla(pygame.K_F4)
		robot.elegir("Medir hasta aquí")
		assert hasta(lambda: sesion.origen_medida is None)

		# Un cambio hecho en el Estudio: se guarda, se envía «reiniciar» y el reproductor recarga sin moverse.
		planta_id = robot.jugador.planta
		contexto.ejecutar(
			"marcar", lambda: ed.anadir_referencia(contexto.entorno, contexto.entorno.planta(planta_id), "Reloj del Estudio", 1.0, 1.0)
		)
		sesion_motor = robot.sesion
		posicion = (robot.jugador.planta, robot.jugador.x, robot.jugador.y)
		assert sesion.guardar_y_avisar() is True
		assert hasta(lambda: robot.sesion is not sesion_motor), "el reproductor no recargó al recibir «reiniciar»"
		assert (robot.jugador.planta, robot.jugador.x, robot.jugador.y) == posicion
		assert aplicacion.fallos == 0
	finally:
		sesion.detener()
		if aplicacion is not None:
			aplicacion.cerrar_todo()
