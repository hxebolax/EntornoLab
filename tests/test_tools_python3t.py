"""Pruebas de la corrección de ``python3t.dll`` en la compilación.

Las extensiones «abi3t» de Python 3.15 (cryptography) enlazan con
``python3t.dll``; si la compilación lleva la de la variante sin bloqueo global,
el cifrado de las fichas no carga en el equipo del usuario.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "tools"))

import verificar_build  # noqa: E402

VARIANTE = f"python{sys.version_info.major}{sys.version_info.minor}t."
NORMAL = f"python{sys.version_info.major}{sys.version_info.minor}."


def _dll(carpeta: Path, destino: str) -> Path:
	"""Escribe una ``python3t.dll`` falsa que redirige a ``destino``."""
	ruta = carpeta / "python3t.dll"
	ruta.write_bytes(b"MZ...PyLong_FromLong (forwarded to " + destino.encode("ascii") + b"PyLong_FromLong)")
	return ruta


def test_avisa_si_redirige_a_la_variante_que_no_viaja(tmp_path: Path) -> None:
	"""La DLL de la variante sin su ``python3XXt.dll`` al lado es un problema."""
	_dll(tmp_path, VARIANTE)
	problemas = verificar_build._verificar_python3t(tmp_path)
	assert problemas and "python3t.dll" in problemas[0]


def test_no_avisa_si_redirige_al_python_normal(tmp_path: Path) -> None:
	"""La DLL que redirige a ``python3XX.dll`` es la correcta."""
	_dll(tmp_path, NORMAL)
	assert verificar_build._verificar_python3t(tmp_path) == []


def test_no_avisa_sin_python3t(tmp_path: Path) -> None:
	"""Sin extensiones abi3t no hay ``python3t.dll`` y no hay nada que comprobar."""
	assert verificar_build._verificar_python3t(tmp_path) == []


def test_setup_detecta_la_variante(tmp_path: Path) -> None:
	"""``setup_cx.python3t_apunta_a_variante`` distingue las dos DLL."""
	sys.path.insert(0, str(RAIZ))
	setup_cx = pytest.importorskip("setup_cx")
	assert setup_cx.python3t_apunta_a_variante(_dll(tmp_path, VARIANTE))
	assert not setup_cx.python3t_apunta_a_variante(_dll(tmp_path, NORMAL))


def test_el_cifrado_funciona_en_este_entorno() -> None:
	"""``comprobar_disponible`` es lo que usa ``--comprobar-arranque``."""
	from app.core import cifrado

	assert cifrado.comprobar_disponible() is None
