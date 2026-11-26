"""Aclaración de cierre normal en ``fallo_nativo.log``.

En Windows, faulthandler apunta excepciones que el sistema resuelve solo; al
cerrar bien, el registro debe decir que no fueron mortales, y no decir nada si
no se apuntó nada.
"""

from __future__ import annotations

from pathlib import Path

from app.core import registro


def _preparar(tmp_path: Path, contenido_extra: str) -> tuple[Path, object, int]:
	"""Simula el estado de ``_activar_faulthandler`` con un archivo propio."""
	ruta = tmp_path / "fallo_nativo.log"
	archivo = open(ruta, "a", encoding="utf-8")  # noqa: SIM115 - imita al registro
	archivo.write("\n=== Sesión prueba ===\n")
	archivo.flush()
	tamano = ruta.stat().st_size
	if contenido_extra:
		archivo.write(contenido_extra)
		archivo.flush()
	return ruta, archivo, tamano


def test_anota_el_cierre_normal_si_hubo_volcados(tmp_path: Path, monkeypatch) -> None:
	"""Con un volcado en la sesión, se añade la línea aclaratoria."""
	ruta, archivo, tamano = _preparar(tmp_path, "Windows fatal exception: code 0x8001010d\n")
	estado = {"archivo_fallo_nativo": archivo, "fallo_nativo_ruta": ruta, "fallo_nativo_tamano": tamano}
	monkeypatch.setattr(registro, "_estado", estado)
	registro._anotar_cierre_normal_en_fallo_nativo()
	archivo.close()
	assert "terminó con normalidad" in ruta.read_text(encoding="utf-8")


def test_no_anota_nada_si_no_hubo_volcados(tmp_path: Path, monkeypatch) -> None:
	"""Sin volcados, el archivo queda como estaba."""
	ruta, archivo, tamano = _preparar(tmp_path, "")
	estado = {"archivo_fallo_nativo": archivo, "fallo_nativo_ruta": ruta, "fallo_nativo_tamano": tamano}
	monkeypatch.setattr(registro, "_estado", estado)
	registro._anotar_cierre_normal_en_fallo_nativo()
	archivo.close()
	assert "terminó con normalidad" not in ruta.read_text(encoding="utf-8")
