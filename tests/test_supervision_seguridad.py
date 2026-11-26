"""Pruebas de la seguridad de la supervisión: código, intentos, certificado y huellas."""

from __future__ import annotations

import socket
import ssl
import threading

import pytest

from app.supervision import seguridad


def test_codigo_generado_y_normalizado():
	codigos = {seguridad.generar_codigo() for _vuelta in range(50)}
	assert len(codigos) > 40
	for codigo in codigos:
		assert len(codigo) == 6 and codigo.isdecimal()
	assert seguridad.normalizar_codigo(" 12 34-56 ") == "123456"
	assert seguridad.normalizar_codigo("ab-12") == "AB12"


def test_las_pruebas_dependen_de_todo():
	base = seguridad.prueba_cliente("123456", "reto", "nonce", "huella")
	assert base == seguridad.prueba_cliente("12 34 56", "reto", "nonce", "huella")
	assert len(base) == 64
	distintas = {
		base,
		seguridad.prueba_cliente("123457", "reto", "nonce", "huella"),
		seguridad.prueba_cliente("123456", "otro", "nonce", "huella"),
		seguridad.prueba_cliente("123456", "reto", "otro", "huella"),
		# Atada a la huella: un intermediario con otro certificado no puede reenviarla.
		seguridad.prueba_cliente("123456", "reto", "nonce", "otra"),
		# La de la sala no es la del cliente: no vale devolverle al cliente su propia prueba.
		seguridad.prueba_sala("123456", "reto", "nonce", "huella"),
	}
	assert len(distintas) == 6
	assert seguridad.pruebas_iguales(base, base)
	assert not seguridad.pruebas_iguales(base, base[:-1] + "0" if base[-1] != "0" else base[:-1] + "1")
	assert seguridad.nuevo_nonce() != seguridad.nuevo_nonce()


def test_control_de_intentos_bloquea_y_desbloquea():
	ahora = [1000.0]
	control = seguridad.ControlIntentos(maximo=3, bloqueo_s=60.0, reloj=lambda: ahora[0])
	assert control.espera("10.0.0.5") == 0
	assert control.fallo("10.0.0.5") == 2
	assert control.fallo("10.0.0.5") == 1
	assert control.espera("10.0.0.5") == 0
	assert control.fallo("10.0.0.5") == 0
	assert control.espera("10.0.0.5") == pytest.approx(60.0)
	assert control.espera("10.0.0.6") == 0  # otra dirección no está bloqueada
	assert control.bloqueados() == 1
	ahora[0] += 59.0
	assert control.espera("10.0.0.5") == pytest.approx(1.0)
	ahora[0] += 2.0
	assert control.espera("10.0.0.5") == 0
	assert control.bloqueados() == 0


def test_control_de_intentos_olvida_los_fallos_antiguos_y_los_aciertos():
	ahora = [0.0]
	control = seguridad.ControlIntentos(maximo=3, bloqueo_s=60.0, reloj=lambda: ahora[0])
	control.fallo("a")
	control.fallo("a")
	ahora[0] += 61.0
	assert control.fallo("a") == 2  # los dos primeros ya no cuentan
	control.fallo("a")
	control.acierto("a")
	assert control.fallo("a") == 2


def test_control_de_intentos_tiene_tope_global():
	ahora = [0.0]
	control = seguridad.ControlIntentos(maximo=2, bloqueo_s=30.0, reloj=lambda: ahora[0])
	for i in range(20):
		control.fallo(f"10.0.{i}.1")  # un fallo desde cada dirección: ninguna llega a su tope
	assert control.espera("192.168.1.1") == pytest.approx(30.0)


@pytest.fixture(scope="module")
def certificado(tmp_path_factory):
	return seguridad.asegurar_certificado(tmp_path_factory.mktemp("config"))


def test_certificado_se_crea_una_vez_y_se_reutiliza(certificado):
	assert certificado.ruta_certificado.name == "sala_certificado.pem"
	assert certificado.ruta_llave.read_text(encoding="ascii").startswith("-----BEGIN RSA PRIVATE KEY-----")
	assert len(certificado.huella) == 64
	otra_vez = seguridad.asegurar_certificado(certificado.ruta_certificado.parent)
	assert otra_vez.huella == certificado.huella
	assert seguridad.huella_legible(certificado.huella) == " ".join(certificado.huella.upper()[i : i + 4] for i in range(0, 16, 4))


def test_certificado_estropeado_se_regenera(tmp_path, certificado):
	(tmp_path / seguridad.NOMBRE_CERTIFICADO).write_text("esto no es un certificado", encoding="ascii")
	(tmp_path / seguridad.NOMBRE_LLAVE).write_text("ni esto una llave", encoding="ascii")
	nuevo = seguridad.asegurar_certificado(tmp_path)
	assert len(nuevo.huella) == 64
	assert nuevo.huella != certificado.huella


def test_por_defecto_el_certificado_va_a_data_config(datos_temporales, monkeypatch, certificado):
	# Se reutiliza el par ya creado para no generar otro: lo que se prueba es la carpeta.
	pem = (certificado.ruta_certificado.read_text(encoding="ascii"), certificado.ruta_llave.read_text(encoding="ascii"))
	monkeypatch.setattr(seguridad, "crear_certificado", lambda **_opciones: pem)
	creado = seguridad.asegurar_certificado()
	assert creado.ruta_certificado.parent == datos_temporales.resolve() / "config"
	assert creado.huella == certificado.huella


def test_tls_real_con_el_certificado_propio(certificado):
	"""Un servidor y un cliente TLS de verdad se entienden y el cliente ve la huella correcta."""
	servidor = socket.create_server(("127.0.0.1", 0))
	puerto = servidor.getsockname()[1]
	contexto = seguridad.contexto_servidor(certificado.ruta_certificado, certificado.ruta_llave)
	recibido: list[bytes] = []

	def atender() -> None:
		conexion, _origen = servidor.accept()
		with contexto.wrap_socket(conexion, server_side=True) as cifrada:
			recibido.append(cifrada.recv(100))
			cifrada.sendall(b"adios\n")
			# Espera a que el cliente cierre: cerrar antes de que lea puede cortar la conexión en seco.
			try:
				cifrada.recv(100)
			except OSError:
				return

	hilo = threading.Thread(target=atender, daemon=True)
	hilo.start()
	with socket.create_connection(("127.0.0.1", puerto), timeout=5) as plano:
		with seguridad.contexto_cliente().wrap_socket(plano) as cifrado:
			assert cifrado.version() in ("TLSv1.2", "TLSv1.3")
			assert seguridad.huella_de_der(cifrado.getpeercert(binary_form=True)) == certificado.huella
			cifrado.sendall(b"hola\n")
			assert cifrado.recv(100) == b"adios\n"
	hilo.join(timeout=5)
	servidor.close()
	assert recibido == [b"hola\n"]
	assert seguridad.contexto_cliente().minimum_version == ssl.TLSVersion.TLSv1_2


def test_almacen_de_huellas(tmp_path):
	almacen = seguridad.AlmacenHuellas(tmp_path / "config" / "salas.json")
	assert almacen.obtener("192.168.1.20", 47900) is None
	almacen.recordar("192.168.1.20", 47900, "aa" * 32)
	almacen.recordar("Equipo-Profe", 47900, "bb" * 32)
	assert almacen.obtener("192.168.1.20", 47900) == "aa" * 32
	assert almacen.obtener("equipo-profe", 47900) == "bb" * 32
	assert almacen.obtener("192.168.1.20", 47901) is None
	# Otro objeto sobre el mismo fichero lo recuerda (persistencia).
	assert seguridad.AlmacenHuellas(almacen.ruta).obtener("192.168.1.20", 47900) == "aa" * 32
	assert almacen.olvidar("192.168.1.20", 47900)
	assert not almacen.olvidar("192.168.1.20", 47900)
	almacen.ruta.write_text("{roto", encoding="utf-8")
	assert almacen.obtener("equipo-profe", 47900) is None
