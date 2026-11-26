"""Pruebas del cifrado por contraseña de las fichas (scrypt + AES-GCM)."""

from __future__ import annotations

import builtins

import pytest

from app.core import cifrado
from app.core.cifrado import ErrorCifrado

# Coste bajo para que las pruebas vayan rápidas; el de producción se prueba una vez.
RAPIDO = {"log2_n": 10}
SAL = bytes(range(16))


@pytest.fixture(scope="module")
def clave() -> bytes:
	return cifrado.derivar_clave("contraseña del profesional", SAL, **RAPIDO)


def test_derivar_clave_es_determinista_y_depende_de_la_sal_y_la_contrasena(clave):
	assert len(clave) == 32
	assert cifrado.derivar_clave("contraseña del profesional", SAL, **RAPIDO) == clave
	assert cifrado.derivar_clave("contraseña del profesional", bytes(16), **RAPIDO) != clave
	assert cifrado.derivar_clave("Contraseña del profesional", SAL, **RAPIDO) != clave
	assert cifrado.derivar_clave("contraseña del profesional", SAL, log2_n=11) != clave


def test_derivar_clave_con_el_coste_de_produccion():
	sal = cifrado.nueva_sal()
	assert len(sal) == cifrado.LONGITUD_SAL
	assert cifrado.nueva_sal() != sal
	assert len(cifrado.derivar_clave("ñandú 你好 🔑", sal)) == 32


@pytest.mark.parametrize(
	("contrasena", "sal", "opciones"),
	[
		("", SAL, {}),
		(None, SAL, {}),
		("x", b"corta", {}),
		("x", "no son bytes", {}),
		("x", SAL, {"log2_n": 5}),
		("x", SAL, {"log2_n": 30}),
		("x", SAL, {"r": 0}),
	],
)
def test_derivar_clave_rechaza_entradas_no_validas(contrasena, sal, opciones):
	with pytest.raises(ErrorCifrado):
		cifrado.derivar_clave(contrasena, sal, **opciones)


def test_cifrar_y_descifrar(clave):
	dato = "Ana García, 12 años, baja visión".encode()
	bloque = cifrado.cifrar(dato, clave)
	assert bloque.startswith(cifrado.MARCA_BLOQUE)
	assert dato not in bloque and b"Ana" not in bloque
	assert cifrado.descifrar(bloque, clave) == dato
	assert cifrado.cifrar(dato, clave) != bloque, "cada bloque lleva su propio nonce: dos cifrados no se parecen"
	assert cifrado.descifrar(cifrado.cifrar(b"", clave), clave) == b""
	assert cifrado.descifrar(bytearray(bloque), bytearray(clave)) == dato


def test_clave_equivocada_o_bloque_manipulado(clave):
	bloque = cifrado.cifrar(b"dato personal", clave)
	otra = cifrado.derivar_clave("otra contraseña", SAL, **RAPIDO)
	with pytest.raises(ErrorCifrado, match="contraseña no es correcta"):
		cifrado.descifrar(bloque, otra)
	for posicion in (len(cifrado.MARCA_BLOQUE), len(bloque) // 2, len(bloque) - 1):
		tocado = bytearray(bloque)
		tocado[posicion] ^= 0x01
		with pytest.raises(ErrorCifrado):
			cifrado.descifrar(bytes(tocado), clave)
	with pytest.raises(ErrorCifrado):
		cifrado.descifrar(bloque[:-3], clave)
	with pytest.raises(ErrorCifrado):
		cifrado.descifrar(b"XXXX" + bloque[4:], clave)
	with pytest.raises(ErrorCifrado):
		cifrado.descifrar(b"", clave)


def test_dato_asociado_ata_el_bloque_a_su_ficha(clave):
	bloque = cifrado.cifrar(b"telefono", clave, asociado=b"alumno:7")
	assert cifrado.descifrar(bloque, clave, asociado=b"alumno:7") == b"telefono"
	with pytest.raises(ErrorCifrado):
		cifrado.descifrar(bloque, clave, asociado=b"alumno:8")
	with pytest.raises(ErrorCifrado):
		cifrado.descifrar(bloque, clave)


@pytest.mark.parametrize("mala", [b"", b"corta", b"x" * 31, b"x" * 33, "texto" * 8, None])
def test_claves_mal_formadas(mala, clave):
	with pytest.raises(ErrorCifrado):
		cifrado.cifrar(b"dato", mala)
	with pytest.raises(ErrorCifrado):
		cifrado.descifrar(cifrado.cifrar(b"dato", clave), mala)


def test_solo_se_cifran_bytes(clave):
	with pytest.raises(ErrorCifrado):
		cifrado.cifrar("texto sin codificar", clave)
	with pytest.raises(ErrorCifrado):
		cifrado.descifrar("texto", clave)


def test_cifrar_con_contrasena_lleva_la_sal_dentro():
	bloque = cifrado.cifrar_con_contrasena(b"copia de seguridad", "frase larga de paso")
	assert bloque.startswith(cifrado.MARCA_CONTRASENA)
	assert cifrado.descifrar_con_contrasena(bloque, "frase larga de paso") == b"copia de seguridad"
	with pytest.raises(ErrorCifrado):
		cifrado.descifrar_con_contrasena(bloque, "otra frase")
	# Tocar la sal o el coste de la cabecera invalida el bloque.
	tocado = bytearray(bloque)
	tocado[len(cifrado.MARCA_CONTRASENA) + 5] ^= 0x01
	with pytest.raises(ErrorCifrado):
		cifrado.descifrar_con_contrasena(bytes(tocado), "frase larga de paso")
	with pytest.raises(ErrorCifrado):
		cifrado.descifrar_con_contrasena(bloque[:10], "frase larga de paso")
	with pytest.raises(ErrorCifrado):
		cifrado.descifrar_con_contrasena(b"ELC1" + bloque[4:], "frase larga de paso")


def test_comprobante_de_contrasena(clave):
	comprobante = cifrado.crear_comprobante(clave)
	assert cifrado.clave_correcta(clave, comprobante) is True
	otra = cifrado.derivar_clave("otra", SAL, **RAPIDO)
	assert cifrado.clave_correcta(otra, comprobante) is False
	assert cifrado.clave_correcta(clave, b"basura") is False
	assert cifrado.clave_correcta(clave, cifrado.cifrar(b"otro texto", clave)) is False


def test_sin_cryptography_se_dice_claramente(clave, monkeypatch):
	importar = builtins.__import__

	def sin_cryptography(nombre, *args, **kwargs):
		if nombre.startswith("cryptography"):
			raise ImportError("No module named 'cryptography'")
		return importar(nombre, *args, **kwargs)

	monkeypatch.setattr(builtins, "__import__", sin_cryptography)
	with pytest.raises(ErrorCifrado, match="cryptography"):
		cifrado.cifrar(b"dato", clave)


def test_los_errores_no_revelan_la_contrasena(clave, caplog):
	secreta = "MiContraseñaSecreta123"
	bloque = cifrado.cifrar_con_contrasena(b"dato", secreta)
	with pytest.raises(ErrorCifrado) as error:
		cifrado.descifrar_con_contrasena(bloque, secreta + "x")
	assert secreta not in str(error.value)
	assert secreta not in caplog.text
