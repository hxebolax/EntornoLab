"""Pruebas del vocabulario de vibración."""

from __future__ import annotations

from app.audio.haptica import PATRONES, Haptica, nombres_patrones


def test_vocabulario_completo() -> None:
	esperados = {"choque", "premio_cerca", "pared_izquierda", "pared_derecha", "objetivo", "peldano", "aviso"}
	assert esperados <= set(PATRONES)
	assert set(nombres_patrones()) == set(PATRONES)
	for pulsos in PATRONES.values():
		for p in pulsos:
			assert 0.0 <= p.grave <= 1.0 and 0.0 <= p.agudo <= 1.0 and p.ms > 0


def test_lados() -> None:
	h = Haptica()
	h.patron("pared_izquierda")
	h.patron("pared_derecha")
	(g1, a1, _ms1), (g2, a2, _ms2) = h.registro
	assert g1 > 0 and a1 == 0
	assert g2 == 0 and a2 > 0


def test_vibrar_recorta_y_aplica_fuerza() -> None:
	emitido: list[tuple[float, float, int]] = []
	h = Haptica(lambda g, a, ms: emitido.append((g, a, ms)), {"fuerza": 0.5})
	h.vibrar(3.0, -1.0, 100)
	assert emitido == [(0.5, 0.0, 100)]
	h.configurar({"fuerza": 0.0})
	assert h.fuerza == 0.2
	h.vibrar(1.0, 1.0, 0)
	assert len(emitido) == 1


def test_doble_pulso_avanza_con_tic() -> None:
	h = Haptica()
	assert h.patron("objetivo")
	assert len(h.registro) == 1 and h.pendiente
	h.tic(0.05)
	assert len(h.registro) == 1
	h.tic(0.2)
	assert len(h.registro) == 2 and not h.pendiente


def test_tic_con_reloj() -> None:
	h = Haptica()
	ahora = [5.0]
	h._reloj = lambda: ahora[0]
	h.tic()
	h.patron("objetivo")
	ahora[0] += 0.3
	h.tic()
	assert len(h.registro) == 2


def test_intensidad_desconocido_inactiva_y_parar() -> None:
	h = Haptica()
	assert h.patron("no_existe") is False
	h.patron("choque", intensidad=0.5)
	assert h.registro[-1][0] == 0.5
	h.patron("aviso")
	h.parar()
	h.tic(1.0)
	assert len(h.registro) == 2
	h.configurar({"activa": False})
	assert h.patron("choque") is True
	h.vibrar(1, 1, 100)
	assert len(h.registro) == 2


def test_emisor_que_falla_no_rompe() -> None:
	def roto(g: float, a: float, ms: int) -> None:
		raise OSError("mando desconectado")

	h = Haptica(roto)
	h.vibrar(1, 1, 100)
	h.parar()
