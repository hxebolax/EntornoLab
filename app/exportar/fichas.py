"""Fichas en frases de los elementos de calle: pasos de peatones y escaleras exteriores.

Una ficha es la lista de frases que un instructor de movilidad quiere saber
de un paso: si tiene semáforo, si suena, si vibra, si hay pulsador, isleta,
pavimento táctil y bordillo, y cuántos metros se cruzan.

Regla que no se rompe nunca: se distingue «no tiene» de «el mapa no lo
dice». En un entorno importado, ``datos["segun_mapa"]`` guarda cada atributo
con tres estados (``si``, ``no``, ``desconocido``); los valores verdadero o
falso del resto de ``datos`` son los que usa el motor, y un «desconocido» se
guarda ahí como falso porque el motor no puede simular lo que no se sabe.

Lo usan el importador (para redactar la descripción del paso) y la
exportación en texto, y por eso está en un módulo aparte.
"""

from __future__ import annotations

from typing import Any

from app.core.i18n import N_, _, _n, separador_decimal
from app.dominio import geometria as geo
from app.dominio.modelo import PASAMANOS, Espacio, nombre_visible

SI = "si"
NO = "no"
DESCONOCIDO = "desconocido"

NO_LO_DICE = N_("el mapa no lo dice")

# Bordillo: valor guardado → frase.
_BORDILLOS: dict[str, str] = {
	"lowered": N_("Bordillo rebajado."),
	"flush": N_("Bordillo a nivel, sin escalón."),
	"raised": N_("Bordillo alto: hay escalón."),
	"rolled": N_("Bordillo redondeado."),
	"no": N_("Sin bordillo."),
	"yes": N_("Con bordillo."),
}


def _m(valor: float) -> str:
	"""Una medida como se dice en español: «7», «3,5»."""
	texto = f"{valor:.1f}".rstrip("0").rstrip(".")
	return (texto or "0").replace(".", separador_decimal())


def viene_de_mapa(datos: dict[str, Any]) -> bool:
	"""True si el elemento se importó de un mapa (y por tanto puede haber cosas que el mapa no diga)."""
	return isinstance(datos.get("segun_mapa"), dict)


def estado_de(datos: dict[str, Any], clave: str) -> str:
	"""«si», «no» o «desconocido» de un atributo.

	Manda lo apuntado en ``segun_mapa``; si el elemento se hizo a mano, vale
	el verdadero o falso de ``datos``, que el profesional puso sabiendo.
	"""
	segun = datos.get("segun_mapa")
	if isinstance(segun, dict) and clave in segun:
		valor = str(segun[clave])
		return valor if valor in (SI, NO) else DESCONOCIDO
	valor = datos.get(clave)
	if isinstance(valor, bool):
		return SI if valor else NO
	return DESCONOCIDO


def _frase(datos: dict[str, Any], clave: str, con: str, sin: str, nombre: str) -> str:
	"""Frase de un atributo de tres estados; cadena vacía si no se sabe y no hay mapa al que achacarlo."""
	estado = estado_de(datos, clave)
	if estado == SI:
		return con
	if estado == NO:
		return sin
	if viene_de_mapa(datos):
		return _("{atributo}: {no_lo_dice}.").format(atributo=nombre, no_lo_dice=_(NO_LO_DICE))
	return ""


def ficha_paso(paso: Espacio) -> list[str]:
	"""Frases que describen un paso de peatones, de lo más importante a lo menos."""
	datos = paso.datos
	lineas: list[str] = []
	semaforo = estado_de(datos, "semaforo")
	lineas.append(_frase(datos, "semaforo", _("Con semáforo."), _("Sin semáforo: hay que escuchar el tráfico para cruzar."), _("Semáforo")))
	if semaforo != NO:
		lineas.append(_frase(datos, "sonoro", _("Con señal sonora."), _("Sin señal sonora."), _("Señal sonora")))
		lineas.append(_frase(datos, "vibracion", _("Con vibración en el poste."), _("Sin vibración."), _("Vibración")))
		lineas.append(_frase(datos, "pulsador", _("Con pulsador."), _("Sin pulsador."), _("Pulsador")))
	lineas.append(_frase(datos, "isleta", _("Con isleta en medio: se cruza en dos tiempos."), _("Sin isleta."), _("Isleta")))
	lineas.append(_frase(datos, "tactil", _("Con pavimento táctil."), _("Sin pavimento táctil."), _("Pavimento táctil")))
	bordillo = str(datos.get("bordillo") or "")
	if bordillo in _BORDILLOS:
		lineas.append(_(_BORDILLOS[bordillo]))
	elif viene_de_mapa(datos):
		lineas.append(_("{atributo}: {no_lo_dice}.").format(atributo=_("Bordillo"), no_lo_dice=_(NO_LO_DICE)))
	longitud = datos.get("longitud")
	if isinstance(longitud, (int, float)) and longitud > 0:
		rumbo = datos.get("rumbo_cruce")
		if isinstance(rumbo, (int, float)):
			lineas.append(
				_("Se cruzan {metros} metros de calzada, hacia el {punto} o en sentido contrario.").format(
					metros=_m(float(longitud)), punto=geo.punto_cardinal(float(rumbo))
				)
			)
		else:
			lineas.append(_("Se cruzan {metros} metros de calzada.").format(metros=_m(float(longitud))))
	ciclo = datos.get("ciclo")
	if semaforo == SI and isinstance(ciclo, dict) and ciclo.get("verde_peatones_s"):
		frase = _("Verde para peatones durante {verde} segundos de cada {total}.").format(
			verde=ciclo.get("verde_peatones_s"),
			total=sum(int(ciclo.get(clave, 0) or 0) for clave in ("verde_peatones_s", "intermitente_s", "rojo_peatones_s")),
		)
		if datos.get("ciclo_estimado"):
			frase += " " + _("Son tiempos de serie, no medidos: {no_lo_dice}.").format(no_lo_dice=_(NO_LO_DICE))
		lineas.append(frase)
	return [linea for linea in lineas if linea]


def ficha_escalera(escalera: Espacio) -> list[str]:
	"""Frases que describen unas escaleras o una rampa exteriores."""
	datos = escalera.datos
	lineas: list[str] = []
	mapa = viene_de_mapa(datos)
	peldanos = datos.get("peldanos")
	if isinstance(peldanos, int) and peldanos > 0:
		lineas.append(_n("{n} peldaño.", "{n} peldaños.", peldanos).format(n=peldanos))
	elif mapa and not datos.get("rampa"):
		lineas.append(_("{atributo}: {no_lo_dice}.").format(atributo=_("Número de peldaños"), no_lo_dice=_(NO_LO_DICE)))
	pasamanos = str(datos.get("pasamanos") or "")
	if pasamanos in PASAMANOS:
		lineas.append(_("Pasamanos: {valor}.").format(valor=nombre_visible(PASAMANOS, pasamanos).lower()))
	elif datos.get("pasamanos_lado_desconocido"):
		lineas.append(_("Con pasamanos; en qué lado, {no_lo_dice}.").format(no_lo_dice=_(NO_LO_DICE)))
	elif mapa:
		lineas.append(_("{atributo}: {no_lo_dice}.").format(atributo=_("Pasamanos"), no_lo_dice=_(NO_LO_DICE)))
	sube = datos.get("sube_hacia")
	if isinstance(sube, (int, float)):
		lineas.append(_("Se sube hacia el {punto}.").format(punto=geo.punto_cardinal(float(sube))))
	elif mapa:
		lineas.append(_("Hacia dónde sube: {no_lo_dice}.").format(no_lo_dice=_(NO_LO_DICE)))
	pendiente = datos.get("pendiente_pct")
	if isinstance(pendiente, (int, float)):
		lineas.append(_("Pendiente del {valor} por ciento.").format(valor=_m(abs(float(pendiente)))))
	lineas.append(_frase(datos, "tactil", _("Con pavimento táctil de aviso."), _("Sin pavimento táctil de aviso."), _("Pavimento táctil")))
	return [linea for linea in lineas if linea]


def atributos_que_faltan(datos: dict[str, Any], claves: dict[str, str]) -> list[str]:
	"""Nombres de los atributos que el mapa no dice, para el informe de importación."""
	segun = datos.get("segun_mapa")
	if not isinstance(segun, dict):
		return []
	return [nombre for clave, nombre in claves.items() if segun.get(clave) == DESCONOCIDO]
