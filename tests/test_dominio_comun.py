"""Material común de las pruebas del dominio: un complemento de prueba y un piso mínimo.

No usa nunca el ``data`` real: el complemento se escribe en la carpeta
temporal de cada prueba.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.dominio import edicion as ed
from app.dominio.catalogo import Catalogo
from app.dominio.modelo import Entorno, Espacio, Planta


def _objeto(id_objeto: str, nombre: str, categoria: str, ancho, fondo, alto, **extra) -> dict:
	ficha = {
		"id": id_objeto,
		"nombre": nombre,
		"categoria": categoria,
		"etiquetas": extra.pop("etiquetas", [id_objeto]),
		"descripcion": f"{nombre} de prueba.",
		"ambito": extra.pop("ambito", ["interior"]),
		"forma": extra.pop("forma", {"tipo": "rectangulo"}),
		"medidas": {"ancho": ancho, "fondo": fondo, "alto": alto},
		"colocacion": extra.pop("colocacion", ["suelo", "pared"]),
		"material": "madera",
		"simbolo": {"letra": nombre[0].upper(), "color": "#8B5A2B"},
	}
	ficha.update(extra)
	return ficha


FICHA_PRUEBA: dict = {
	"formato": 1,
	"id": "prueba",
	"nombre": "Complemento de prueba",
	"version": "1.0",
	"autor": "Pruebas",
	"licencia": "CC0",
	"descripcion": "Muebles para las pruebas.",
	"categorias": {"dormitorio": "Dormitorio", "salon": "Salón"},
	"objetos": [
		_objeto(
			"cama",
			"Cama",
			"dormitorio",
			[0.8, 1.5, 2.0],
			[1.8, 2.0, 2.1],
			[0.4, 0.5, 0.7],
			variantes=[
				{"id": "individual", "nombre": "Individual", "ancho": 0.9, "fondo": 1.9, "alto": 0.5},
				{"id": "matrimonio", "nombre": "De matrimonio", "ancho": 1.5, "fondo": 2.0, "alto": 0.5},
			],
			contenedor=True,
		),
		_objeto(
			"mesilla",
			"Mesilla de noche",
			"dormitorio",
			[0.3, 0.45, 0.6],
			[0.3, 0.4, 0.5],
			[0.4, 0.55, 0.7],
			etiquetas=["mesilla", "mesita"],
		),
		_objeto(
			"armario",
			"Armario",
			"dormitorio",
			[0.8, 1.2, 3.0],
			[0.5, 0.6, 0.7],
			[1.8, 2.0, 2.4],
			estados=["cerrado", "abierto"],
			acciones=[
				{"id": "abrir", "nombre": "Abrir", "de": "cerrado", "a": "abierto", "sonido": "puerta_armario"},
				{"id": "cerrar", "nombre": "Cerrar", "de": "abierto", "a": "cerrado", "sonido": "puerta_armario"},
			],
			contenedor=True,
		),
		_objeto("mesa", "Mesa", "salon", [0.8, 1.2, 2.4], [0.6, 0.8, 1.2], [0.7, 0.75, 0.8], colocacion=["suelo"]),
		_objeto("mesa_redonda", "Mesa redonda", "salon", [0.6, 1.0, 1.6], [0.6, 1.0, 1.6], [0.7, 0.75, 0.8], forma={"tipo": "circulo"}),
		_objeto("silla", "Silla", "salon", [0.4, 0.45, 0.5], [0.4, 0.45, 0.5], [0.8, 0.9, 1.0], colocacion=["suelo"]),
		_objeto("sofa", "Sofá", "salon", [1.4, 2.0, 3.0], [0.8, 0.9, 1.0], [0.8, 0.85, 0.9], etiquetas=["sofa", "sofá"]),
		_objeto(
			"rinconera",
			"Sofá rinconera",
			"salon",
			[2.0, 2.4, 3.0],
			[1.6, 2.0, 2.4],
			[0.8, 0.85, 0.9],
			forma={"tipo": "ele"},
			colocacion=["esquina"],
		),
		_objeto("estanteria", "Estantería", "salon", [0.6, 0.9, 1.2], [0.25, 0.3, 0.4], [1.6, 1.8, 2.2]),
		_objeto("alfombra", "Alfombra", "salon", [1.0, 2.0, 3.0], [0.6, 1.4, 2.0], [0.01, 0.02, 0.03], bloquea=False, colocacion=["suelo"]),
		_objeto(
			"lampara",
			"Lámpara colgante",
			"salon",
			[0.3, 0.5, 0.8],
			[0.3, 0.5, 0.8],
			[0.3, 0.4, 0.5],
			altura_base=1.9,
			detectable_baston=False,
		),
		_objeto(
			"frigorifico",
			"Frigorífico",
			"cocina",
			[0.55, 0.6, 0.9],
			[0.55, 0.65, 0.75],
			[1.4, 1.8, 2.0],
			etiquetas=["frigorifico", "nevera"],
			sonidos={"golpe": "golpe_metal", "propio": {"sonido": "frigorifico", "volumen": 0.5, "radio": 6}},
		),
		_objeto("encimera", "Encimera", "cocina", [0.6, 1.8, 3.6], [0.55, 0.6, 0.65], [0.85, 0.9, 0.95]),
		_objeto("inodoro", "Inodoro", "bano", [0.35, 0.4, 0.45], [0.6, 0.65, 0.7], [0.4, 0.4, 0.8], etiquetas=["inodoro", "váter"]),
		_objeto("lavabo", "Lavabo", "bano", [0.45, 0.6, 0.9], [0.4, 0.45, 0.55], [0.8, 0.85, 0.9]),
		_objeto("pupitre", "Pupitre", "aula", [0.6, 0.7, 0.7], [0.5, 0.5, 0.6], [0.7, 0.75, 0.8], colocacion=["suelo"]),
		_objeto("pizarra", "Pizarra", "aula", [1.2, 2.4, 3.6], [0.05, 0.08, 0.1], [1.0, 1.2, 1.3], altura_base=0.9),
		_objeto("escritorio", "Escritorio", "oficina", [1.0, 1.4, 1.8], [0.6, 0.7, 0.8], [0.7, 0.75, 0.8]),
		_objeto("papelera", "Papelera", "oficina", [0.25, 0.3, 0.35], [0.25, 0.3, 0.35], [0.3, 0.35, 0.4], forma={"tipo": "circulo"}),
		_objeto("banco", "Banco", "calle", [1.2, 1.8, 2.4], [0.5, 0.6, 0.7], [0.8, 0.85, 0.9], ambito=["exterior"], colocacion=["acera"]),
		_objeto(
			"jardinera",
			"Jardinera triangular",
			"calle",
			[0.6, 1.0, 1.5],
			[0.6, 1.0, 1.5],
			[0.5, 0.6, 0.7],
			ambito=["exterior", "interior"],
			forma={"tipo": "poligono", "puntos": [[0, 0], [1, 0], [0, 1]]},
			colocacion=["acera", "suelo"],
		),
	],
}


def escribir_complemento(raiz: Path, ficha: dict | None = None, traducciones: dict[str, dict] | None = None) -> Path:
	"""Escribe un complemento en ``raiz/<id>/`` y devuelve su carpeta."""
	ficha = ficha if ficha is not None else FICHA_PRUEBA
	carpeta = raiz / str(ficha.get("id", "sin-id"))
	carpeta.mkdir(parents=True, exist_ok=True)
	(carpeta / "complemento.json").write_text(json.dumps(ficha, ensure_ascii=False, indent="\t"), encoding="utf-8")
	for idioma, textos in (traducciones or {}).items():
		(carpeta / "locales").mkdir(exist_ok=True)
		(carpeta / "locales" / f"{idioma}.json").write_text(json.dumps(textos, ensure_ascii=False), encoding="utf-8")
	return carpeta


def catalogo_de_prueba(tmp_path: Path) -> Catalogo:
	"""Catálogo con el complemento de prueba, cargado de una carpeta temporal."""
	raiz = tmp_path / "plugins"
	escribir_complemento(raiz)
	return Catalogo.cargar(raiz)


def piso_minimo() -> tuple[Entorno, Planta, Espacio, Espacio]:
	"""Entorno con un salón de 5 × 4 y una cocina de 3 × 4 adosada al este, unidos por una puerta."""
	entorno = ed.crear_entorno("Piso mínimo")
	planta = ed.crear_planta(entorno, "Planta baja")
	salon = ed.crear_habitacion_rectangular(entorno, planta, "Salón", 0, 0, 5, 4)
	cocina = ed.crear_habitacion_adosada(entorno, planta, "Cocina", salon, "este", 3, 4)
	ed.anadir_puerta_entre(entorno, planta, salon, cocina, estado="abierta")
	ed.fijar_inicio(entorno, planta, 2.5, 2.0, 0.0)
	return entorno, planta, salon, cocina


def test_material_comun(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	assert not catalogo.avisos
	assert len(catalogo.objetos()) == len(FICHA_PRUEBA["objetos"])
	entorno, planta, salon, cocina = piso_minimo()
	assert planta.espacio_en(1, 1) is salon
	assert planta.espacio_en(6, 1) is cocina
	assert entorno.inicio.planta == planta.id
