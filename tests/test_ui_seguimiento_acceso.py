"""Contraseña del profesional: crearla, equivocarse, cambiarla y bloquear."""

# ruff: noqa: F811 - las fixtures importadas de _ui_seguimiento_util se usan como parámetros
from __future__ import annotations

import json

import pytest

wx = pytest.importorskip("wx")

from app.core import cifrado  # noqa: E402
from app.seguimiento.alumnos import Fichas  # noqa: E402
from app.seguimiento.base import BaseSeguimiento, ErrorClave  # noqa: E402
from app.ui.seguimiento import acceso as mod_acceso  # noqa: E402
from app.ui.seguimiento import dialogos_acceso  # noqa: E402
from app.ui.seguimiento.acceso import AccesoDatos, ContrasenaIncorrecta, ErrorAcceso, validar_contrasena_nueva  # noqa: E402
from tests._seguimiento_util import documento_sesion  # noqa: E402
from tests._ui_seguimiento_util import CONTRASENA, equipo, responder_con, revisar, sin_voz  # noqa: E402, F401


class ConfiguracionFalsa:
	"""Configuración mínima con solo lo que lee ``AccesoDatos``."""

	def __init__(self, **valores) -> None:
		self.valores = valores

	def obtener(self, clave, defecto=None):
		return self.valores.get(clave, defecto)


def _acceso(tmp_path, **valores) -> AccesoDatos:
	return AccesoDatos(
		ConfiguracionFalsa(**valores),
		ruta_base=tmp_path / "db" / "base.db",
		ruta_acceso=tmp_path / "config" / "acceso.json",
		carpeta_sesiones=tmp_path / "sessions",
	)


# ── Lógica (sin ventanas) ────────────────────────────────────────────────────


def test_validar_contrasena_nueva():
	assert validar_contrasena_nueva("", "")
	assert validar_contrasena_nueva("corta", "corta")
	assert validar_contrasena_nueva("contraseña larga", "otra distinta")
	assert validar_contrasena_nueva("contraseña larga", "contraseña larga") == ""


def test_crear_guarda_sal_y_comprobante_pero_no_la_contrasena(tmp_path):
	acceso = _acceso(tmp_path)
	assert acceso.estado() == mod_acceso.SIN_CONTRASENA
	base = acceso.crear_contrasena(CONTRASENA)
	assert acceso.estado() == mod_acceso.ABIERTA
	assert base.cifrador.activo
	guardado = json.loads(acceso.ruta_acceso.read_text(encoding="utf-8"))
	assert set(guardado) == {"formato", "sal", "comprobante"}
	assert CONTRASENA not in acceso.ruta_acceso.read_text(encoding="utf-8")
	clave = cifrado.derivar_clave(CONTRASENA, bytes.fromhex(guardado["sal"]))
	assert cifrado.clave_correcta(clave, bytes.fromhex(guardado["comprobante"]))
	acceso.cerrar()


def test_los_campos_se_cifran_de_verdad_en_el_fichero(tmp_path):
	acceso = _acceso(tmp_path)
	base = acceso.crear_contrasena(CONTRASENA)
	Fichas(base).alta("Luna", nombre_real="Nombre Secretísimo", notas="Nota privada")
	acceso.bloquear()
	assert acceso.estado() == mod_acceso.BLOQUEADA
	crudo = (tmp_path / "db" / "base.db").read_bytes()
	assert b"Luna" in crudo
	assert "Nombre Secretísimo".encode() not in crudo
	assert b"Nota privada" not in crudo
	with pytest.raises(ErrorClave):
		BaseSeguimiento(tmp_path / "db" / "base.db")


def test_contrasena_equivocada_no_abre_y_la_buena_si(tmp_path):
	acceso = _acceso(tmp_path)
	base = acceso.crear_contrasena(CONTRASENA)
	Fichas(base).alta("Luna", nombre_real="Ana")
	acceso.bloquear()
	with pytest.raises(ContrasenaIncorrecta):
		acceso.desbloquear("otra contraseña")
	assert acceso.base is None
	base = acceso.desbloquear(CONTRASENA)
	assert Fichas(base).por_alias("luna").nombre_real == "Ana"
	acceso.cerrar()


def test_cambiar_contrasena_recifra_y_la_vieja_deja_de_valer(tmp_path):
	acceso = _acceso(tmp_path)
	base = acceso.crear_contrasena(CONTRASENA)
	Fichas(base).alta("Luna", nombre_real="Ana", notas="Usa bastón largo")
	with pytest.raises(ContrasenaIncorrecta):
		acceso.cambiar_contrasena("no es la actual", "contraseña nueva 2")
	acceso.cambiar_contrasena(CONTRASENA, "contraseña nueva 2")
	assert Fichas(acceso.base).por_alias("Luna").notas == "Usa bastón largo"
	acceso.bloquear()
	with pytest.raises(ContrasenaIncorrecta):
		acceso.desbloquear(CONTRASENA)
	base = acceso.desbloquear("contraseña nueva 2")
	assert Fichas(base).por_alias("Luna").nombre_real == "Ana"
	assert not acceso.ruta_acceso.with_name(acceso.ruta_acceso.name + ".nuevo").exists()
	acceso.cerrar()


def test_sin_cifrado_pedido_abre_sin_contrasena_y_respeta_una_ya_creada(tmp_path):
	acceso = _acceso(tmp_path, **{"privacidad.cifrar_fichas": False})
	assert acceso.estado() == mod_acceso.SIN_CIFRAR
	base = acceso.abrir_sin_cifrar()
	assert not base.cifrador.activo
	Fichas(base).alta("Sol", nombre_real="Marta")
	acceso.cerrar()
	# Al crear la contraseña después, lo que había en claro se cifra.
	acceso.crear_contrasena(CONTRASENA)
	acceso.bloquear()
	assert b"Marta" not in (tmp_path / "db" / "base.db").read_bytes()
	assert acceso.estado() == mod_acceso.BLOQUEADA
	with pytest.raises(ErrorAcceso):
		acceso.abrir_sin_cifrar()


def test_al_abrir_se_incorporan_las_sesiones_y_se_borra_el_fichero(tmp_path):
	from app.seguimiento import grabadora, sesiones

	acceso = _acceso(tmp_path)
	ruta = tmp_path / "sessions" / ("a" * 32 + grabadora.EXTENSION)
	grabadora.escribir_sesion(ruta, documento_sesion("a" * 32, "Luna"))
	base = acceso.crear_contrasena(CONTRASENA)
	assert acceso.ultimo_resumen.nuevas == 1
	assert acceso.ultimo_resumen.alumnos_creados == 1
	assert "1" in acceso.ultimo_resumen.frase()
	assert len(sesiones.listar(base)) == 1
	assert not ruta.exists()
	acceso.cerrar()


def test_caducidad_configurada_borra_sesiones_antiguas(tmp_path):
	from app.seguimiento import grabadora, sesiones

	acceso = _acceso(tmp_path, **{"privacidad.caducidad_dias": 30})
	ruta = tmp_path / "sessions" / ("b" * 32 + grabadora.EXTENSION)
	grabadora.escribir_sesion(ruta, documento_sesion("b" * 32, "Luna", inicio="2020-01-01T10:00:00+00:00", fin="2020-01-01T10:05:00+00:00"))
	base = acceso.crear_contrasena(CONTRASENA)
	assert acceso.ultimo_resumen.caducadas == 1
	assert sesiones.listar(base) == []
	acceso.cerrar()


def test_fichero_de_acceso_danado_se_explica(tmp_path):
	acceso = _acceso(tmp_path)
	acceso.crear_contrasena(CONTRASENA)
	acceso.bloquear()
	acceso.ruta_acceso.write_text("{esto no es json", encoding="utf-8")
	with pytest.raises(ErrorAcceso):
		acceso.estado()


# ── Diálogos ─────────────────────────────────────────────────────────────────


def test_teclado_de_los_dialogos_de_contrasena(equipo):
	for clase in (dialogos_acceso.DialogoCrearContrasena, dialogos_acceso.DialogoPedirContrasena, dialogos_acceso.DialogoCambiarContrasena):
		dialogo = clase(equipo.contexto.ventana, equipo.servicio.acceso)
		try:
			revisar(dialogo)
		finally:
			dialogo.Destroy()


def test_dialogo_crear_rechaza_contrasenas_distintas_y_enfoca(equipo, dialogo_modal):
	dialogo = dialogos_acceso.DialogoCrearContrasena(equipo.contexto.ventana, equipo.servicio.acceso)
	dialogo.nueva.SetValue("contraseña larga")
	dialogo.repetida.SetValue("otra cosa distinta")
	assert dialogo.aceptar() is False
	assert "no coinciden" in dialogo_modal.ultimo.textos[0] or any("no coinciden" in t for t in dialogo_modal.ultimo.textos)
	assert dialogo.repetida.GetValue() == ""
	assert equipo.servicio.acceso.base is None
	dialogo.nueva.SetValue(CONTRASENA)
	dialogo.repetida.SetValue(CONTRASENA)
	assert dialogo.aceptar() is True
	assert equipo.servicio.acceso.base is not None
	dialogo.Destroy()


def test_asegurar_base_crea_la_contrasena_la_primera_vez(equipo, dialogo_modal):
	def rellenar(dialogo):
		assert "NO hay forma de recuperar" in dialogo.explicacion.GetValue()
		dialogo.nueva.SetValue(CONTRASENA)
		dialogo.repetida.SetValue(CONTRASENA)

	dialogo_modal.responder(responder_con(rellenar))
	base = dialogos_acceso.asegurar_base(equipo.contexto, equipo.servicio)
	assert base is not None and base.cifrador.activo
	assert any("Contraseña creada" in texto for texto in equipo.contexto.anunciados)
	# La segunda vez ya está abierta: no se pregunta nada.
	antes = len(dialogo_modal.mostrados)
	assert dialogos_acceso.asegurar_base(equipo.contexto, equipo.servicio) is base
	assert len(dialogo_modal.mostrados) == antes


def test_asegurar_base_con_contrasena_equivocada_y_despues_cancelar(equipo, dialogo_modal):
	equipo.abrir_base()
	equipo.servicio.acceso.bloquear()

	def equivocarse(dialogo):
		dialogo.campo.SetValue("no es esta")

	# El diálogo de la contraseña (que rechaza) y, dentro, el del mensaje de error.
	dialogo_modal.responder(responder_con(equivocarse), wx.ID_OK)
	assert dialogos_acceso.asegurar_base(equipo.contexto, equipo.servicio) is None
	assert any("no es correcta" in texto for mostrado in dialogo_modal.mostrados for texto in mostrado.textos)

	dialogo_modal.responder(responder_con(lambda d: d.campo.SetValue(CONTRASENA)))
	assert dialogos_acceso.asegurar_base(equipo.contexto, equipo.servicio) is not None


def test_cambiar_contrasena_desde_el_dialogo_y_bloquear(equipo, dialogo_modal):
	equipo.abrir_base()

	def rellenar(dialogo):
		dialogo.actual.SetValue(CONTRASENA)
		dialogo.nueva.SetValue("otra contraseña 9")
		dialogo.repetida.SetValue("otra contraseña 9")

	dialogo_modal.responder(responder_con(rellenar))
	assert dialogos_acceso.cambiar_contrasena(equipo.contexto, equipo.servicio, equipo.contexto.ventana) is True
	dialogos_acceso.bloquear(equipo.contexto, equipo.servicio)
	assert equipo.servicio.acceso.base is None
	with pytest.raises(ContrasenaIncorrecta):
		equipo.servicio.acceso.desbloquear(CONTRASENA)
	assert equipo.servicio.acceso.desbloquear("otra contraseña 9") is not None
