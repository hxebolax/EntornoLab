"""Genera los datos FICTICIOS de prueba de esta carpeta a partir de coordenadas en metros.

Los ficheros de ``tests/datos`` (el cruce de dos calles y el edificio con
interiores en formato de OpenStreetMap, el plano DXF, los SVG, la ruta GPX y
la GeoJSON) no proceden de ningún mapa real: se escriben con este guion para
que las coordenadas salgan exactas y se puedan cambiar sin editar a mano
latitudes y longitudes. Las pruebas leen los ficheros, no este guion.

Uso, desde la raíz del proyecto:

	.venv/Scripts/python.exe tests/datos/generar_datos.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from xml.sax.saxutils import quoteattr

DESTINO = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent)
LAT0, LON0 = 40.0, -3.7
M = math.pi * 6371008.8 / 180.0
KX = M * math.cos(math.radians(LAT0))


def ll(x, y):
	return round(LAT0 + y / M, 7), round(LON0 + x / KX, 7)


def construir(nodos, vias, relaciones=()):
	elementos = []
	for ident, (x, y, tags) in nodos.items():
		lat, lon = ll(x, y)
		e = {"type": "node", "id": ident, "lat": lat, "lon": lon}
		if tags:
			e["tags"] = tags
		elementos.append(e)
	for ident, (refs, tags) in vias.items():
		elementos.append({"type": "way", "id": ident, "nodes": refs, "tags": tags})
	for ident, (miembros, tags) in relaciones:
		elementos.append({"type": "relation", "id": ident, "members": miembros, "tags": tags})
	return elementos


def a_xml(elementos, recuadro):
	lineas = ['<?xml version="1.0" encoding="UTF-8"?>', '<osm version="0.6" generator="EntornoLab (datos ficticios de prueba)">']
	lineas.append(f' <bounds minlat="{recuadro[0]}" minlon="{recuadro[1]}" maxlat="{recuadro[2]}" maxlon="{recuadro[3]}"/>')
	for e in elementos:
		tags = e.get("tags", {})
		if e["type"] == "node":
			cab = f' <node id="{e["id"]}" lat="{e["lat"]}" lon="{e["lon"]}"'
			if not tags:
				lineas.append(cab + "/>")
				continue
			lineas.append(cab + ">")
		elif e["type"] == "way":
			lineas.append(f' <way id="{e["id"]}">')
			for n in e["nodes"]:
				lineas.append(f'  <nd ref="{n}"/>')
		else:
			lineas.append(f' <relation id="{e["id"]}">')
			for m in e["members"]:
				lineas.append(f'  <member type="{m["type"]}" ref="{m["ref"]}" role="{m["role"]}"/>')
		for k, v in tags.items():
			lineas.append(f"  <tag k={quoteattr(k)} v={quoteattr(v)}/>")
		lineas.append(f" </{e['type']}>")
	lineas.append("</osm>")
	return "\n".join(lineas) + "\n"


def escribir(nombre, texto):
	with open(f"{DESTINO}/{nombre}", "w", encoding="utf-8", newline="\n") as fichero:
		fichero.write(texto)


AVISO = "EntornoLab: datos FICTICIOS de prueba; no proceden de OpenStreetMap"

# ── Cruce de dos calles ──
nodos = {
	1: (-70, 0, {}),
	2: (
		-20,
		0,
		{
			"highway": "crossing",
			"crossing": "traffic_signals",
			"traffic_signals:sound": "yes",
			"traffic_signals:vibration": "yes",
			"button_operated": "yes",
			"crossing:island": "no",
			"tactile_paving": "yes",
			"kerb": "lowered",
		},
	),
	3: (0, 0, {}),
	4: (30, 0, {}),
	5: (70, 0, {}),
	6: (0, -60, {}),
	7: (0, -15, {"highway": "crossing"}),
	8: (0, 60, {}),
	# Edificio de viviendas con portal y número
	20: (10, 12, {}),
	21: (20, 12, {"entrance": "main", "addr:housenumber": "12", "addr:street": "Calle Mayor"}),
	22: (40, 12, {}),
	23: (40, 30, {}),
	24: (10, 30, {}),
	# Mercado
	25: (-45, 12, {}),
	26: (-15, 12, {}),
	27: (-15, 30, {}),
	28: (-45, 30, {}),
	# Parada
	30: (45, 4.5, {"highway": "bus_stop", "name": "Calle Mayor", "shelter": "yes", "bench": "no", "route_ref": "3;7", "ref": "1021"}),
	# Escaleras
	40: (-30, -12, {}),
	41: (-30, -25, {}),
	42: (-40, -12, {}),
	43: (-40, -20, {}),
	# Obstáculos y lugares
	50: (8, 4.2, {"barrier": "bollard"}),
	51: (-10, 4.4, {"amenity": "bench"}),
	52: (25, 11, {"shop": "bakery", "name": "Panadería La Espiga"}),
	53: (25, 20, {"natural": "tree"}),
	54: (-50, 4.4, {"amenity": "pharmacy"}),
	# Valla con cancela
	60: (-60, -30, {}),
	61: (-52, -30, {"barrier": "gate"}),
	62: (-45, -30, {}),
	# Parque y sendero
	70: (15, -50, {}),
	71: (60, -50, {}),
	72: (60, -15, {}),
	73: (15, -15, {}),
	74: (20, -45, {}),
	75: (55, -20, {}),
}
vias = {
	100: (
		[1, 2, 3, 4, 5],
		{"highway": "tertiary", "name": "Calle Mayor", "lanes": "2", "sidewalk": "both", "maxspeed": "30", "surface": "asphalt"},
	),
	101: ([6, 7, 3, 8], {"highway": "residential", "name": "Calle del Río", "oneway": "yes"}),
	200: ([20, 21, 22, 23, 24, 20], {"building": "apartments", "building:levels": "4"}),
	201: ([25, 26, 27, 28, 25], {"building": "yes", "name": "Mercado", "amenity": "marketplace"}),
	300: ([40, 41], {"highway": "steps", "step_count": "12", "handrail:left": "yes", "handrail:right": "yes", "incline": "up"}),
	301: ([42, 43], {"highway": "steps"}),
	400: ([60, 61, 62], {"barrier": "fence"}),
	500: ([70, 71, 72, 73, 70], {"leisure": "park", "name": "Parque del Río"}),
	501: ([74, 75], {"highway": "footway", "surface": "gravel"}),
}
sur, oeste = ll(-80, -80)
norte, este = ll(80, 80)
elementos = construir(nodos, vias)
datos = {
	"version": 0.6,
	"generator": AVISO,
	"osm3s": {"timestamp_osm_base": "2026-11-01T00:00:00Z"},
	"recuadro": [sur, oeste, norte, este],
	"elements": elementos,
}
escribir("cruce.osm.json", json.dumps(datos, ensure_ascii=False, indent="\t") + "\n")
escribir("cruce.osm", a_xml(elementos, [sur, oeste, norte, este]))

# ── Interior: un edificio con un pasillo y dos salas en la planta 0 y un aula en la planta 1 ──
nodos = {
	1: (-40, 0, {}),
	2: (40, 0, {}),
	10: (0, 5, {}),
	11: (20, 5, {}),
	12: (20, 17, {}),
	13: (0, 17, {}),
	20: (0, 8, {}),
	21: (20, 8, {}),
	22: (10, 8, {}),
	23: (10, 17, {}),
	30: (10, 5, {"entrance": "main", "door": "sliding", "automatic_door": "yes", "level": "0"}),
	31: (5, 8, {"door": "hinged", "level": "0"}),
	32: (15, 8, {"door": "no", "level": "0"}),
	40: (18, 6.5, {"highway": "elevator", "level": "0;1"}),
}
vias = {
	100: ([1, 2], {"highway": "residential", "name": "Calle de la Estación", "sidewalk": "both"}),
	200: ([10, 30, 11, 21, 12, 23, 13, 20, 10], {"building": "public", "name": "Centro cívico"}),
	210: ([10, 30, 11, 21, 32, 22, 31, 20, 10], {"indoor": "corridor", "level": "0", "name": "Pasillo de entrada"}),
	211: ([20, 31, 22, 23, 13, 20], {"indoor": "room", "level": "0", "name": "Sala de lectura"}),
	212: ([22, 32, 21, 12, 23, 22], {"indoor": "room", "level": "0"}),
	213: ([10, 11, 12, 13, 10], {"indoor": "room", "level": "1", "name": "Aula"}),
}
sur, oeste = ll(-45, -15)
norte, este = ll(45, 30)
datos = {"version": 0.6, "generator": AVISO, "recuadro": [sur, oeste, norte, este], "elements": construir(nodos, vias)}
escribir("interior.osm.json", json.dumps(datos, ensure_ascii=False, indent="\t") + "\n")


# ── Plano DXF de prueba: dos salas, una puerta, un muro suelto, una columna en un bloque ──
def dxf(pares):
	return "".join(f"{codigo}\n{valor}\n" for codigo, valor in pares)


def lwpolilinea(capa, puntos, cerrada=True):
	pares = [(0, "LWPOLYLINE"), (8, capa), (90, len(puntos)), (70, 1 if cerrada else 0)]
	for x, y in puntos:
		pares += [(10, x), (20, y)]
	return pares


def polilinea(capa, puntos, cerrada=True):
	pares = [(0, "POLYLINE"), (8, capa), (66, 1), (70, 1 if cerrada else 0)]
	for x, y in puntos:
		pares += [(0, "VERTEX"), (8, capa), (10, x), (20, y), (30, 0)]
	return pares + [(0, "SEQEND")]


pares = [(999, "Plano FICTICIO de prueba de EntornoLab, en milimetros")]
pares += [(0, "SECTION"), (2, "HEADER"), (9, "$ACADVER"), (1, "AC1015"), (9, "$INSUNITS"), (70, 4), (0, "ENDSEC")]
pares += [(0, "SECTION"), (2, "BLOCKS"), (0, "BLOCK"), (8, "0"), (2, "COLUMNA"), (70, 0), (10, 0), (20, 0), (30, 0)]
pares += lwpolilinea("0", [(0, 0), (300, 0), (300, 300), (0, 300)])
pares += [(0, "ENDBLK"), (0, "ENDSEC")]
pares += [(0, "SECTION"), (2, "ENTITIES")]
pares += lwpolilinea("MUROS", [(0, 0), (4000, 0), (4000, 3000), (0, 3000)])
pares += polilinea("MUROS", [(4000, 0), (8000, 0), (8000, 3000), (4000, 3000)])
pares += [(0, "LINE"), (8, "MUROS"), (10, 8000), (20, 0), (30, 0), (11, 10000), (21, 0), (31, 0)]
pares += [(0, "INSERT"), (8, "MUROS"), (2, "COLUMNA"), (10, 9000), (20, 1000), (30, 0), (41, 1.0), (42, 1.0), (50, 0)]
pares += [(0, "ARC"), (8, "PUERTAS"), (10, 4000), (20, 1000), (30, 0), (40, 900), (50, 90), (51, 180)]
pares += [(0, "LINE"), (8, "PUERTAS"), (10, 4000), (20, 1000), (30, 0), (11, 3100), (21, 1000), (31, 0)]
pares += [(0, "TEXT"), (8, "TEXTOS"), (10, 1000), (20, 1500), (30, 0), (40, 250), (1, "Cocina")]
pares += [
	(0, "MTEXT"),
	(8, "TEXTOS"),
	(10, 5000),
	(20, 1500),
	(30, 0),
	(40, 250),
	(71, 1),
	(1, "{" + chr(92) + "fArial|b0|i0;Salon" + chr(92) + "Pcomedor}"),
]
pares += [(0, "CIRCLE"), (8, "MOBILIARIO"), (10, 2000), (20, 500), (30, 0), (40, 300)]
pares += [(0, "HATCH"), (8, "SOMBREADO"), (2, "SOLID"), (70, 1)]
pares += [(0, "LINE"), (8, "COTAS"), (67, 1), (10, 0), (20, -500), (30, 0), (11, 8000), (21, -500), (31, 0)]
pares += [(0, "ENDSEC"), (0, "EOF")]
escribir("planta.dxf", dxf(pares))

# ── Plano SVG de prueba ──
escribir(
	"planta.svg",
	"""<?xml version="1.0" encoding="UTF-8"?>
<!-- Plano FICTICIO de prueba de EntornoLab. Una unidad son 10 centimetros. -->
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" viewBox="0 0 100 60">
	<script>alert("esto no se ejecuta nunca")</script>
	<defs><rect id="molde" x="0" y="0" width="500" height="500"/></defs>
	<g inkscape:groupmode="layer" inkscape:label="salas">
		<rect x="0" y="0" width="40" height="30"/>
		<polygon points="40,0 80,0 80,30 40,30"/>
		<path d="M 0 30 h 80 v 20 h -80 z"/>
	</g>
	<g id="muros" transform="translate(10,0)">
		<line x1="80" y1="0" x2="80" y2="50"/>
		<polyline points="70,50 80,50"/>
	</g>
	<g id="rotulos">
		<text x="10" y="15" font-size="4">Cocina</text>
		<text x="50" y="15" font-size="4"><tspan x="50" y="15">Salón</tspan></text>
		<text x="20" y="40" font-size="4">Pasillo</text>
	</g>
	<image xlink:href="http://example.invalid/no-se-descarga.png" x="0" y="0" width="10" height="10"/>
	<use xlink:href="#molde"/>
</svg>
""",
)

# ── SVG malicioso: entidad externa que intenta leer un fichero del equipo ──
escribir(
	"malicioso.svg",
	"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE svg [
	<!ENTITY secreto SYSTEM "file:///C:/Windows/win.ini">
	<!ENTITY remoto SYSTEM "http://example.invalid/robar">
]>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 60">
	<rect x="0" y="0" width="40" height="30"/>
	<text x="10" y="15">&secreto;&remoto;</text>
</svg>
""",
)


# ── Ruta GPX y GeoJSON sobre el cruce de prueba ──
def wpt(etiqueta, x, y, nombre=""):
	lat, lon = ll(x, y)
	interior = f"<name>{nombre}</name>" if nombre else ""
	return f'<{etiqueta} lat="{lat}" lon="{lon}">{interior}</{etiqueta}>'


recorrido = [(-60, 4.2), (-20, 4.2), (-20, -4.2), (-6, -4.2), (-6, -40)]
escribir(
	"ruta.gpx",
	'<?xml version="1.0" encoding="UTF-8"?>\n'
	'<gpx version="1.1" creator="EntornoLab (datos ficticios de prueba)" xmlns="http://www.topografix.com/GPX/1/1">\n'
	+ "\t"
	+ wpt("wpt", -60, 4.2, "Casa")
	+ "\n"
	+ "\t"
	+ wpt("wpt", 5000, 5000, "Muy lejos")
	+ "\n"
	+ "\t<trk><name>Ruta al parque</name><trkseg>\n"
	+ "".join("\t\t" + wpt("trkpt", x, y) + "\n" for x, y in recorrido)
	+ "\t</trkseg></trk>\n</gpx>\n",
)
geo = {
	"type": "FeatureCollection",
	"features": [
		{
			"type": "Feature",
			"properties": {"name": "Ruta al mercado"},
			"geometry": {"type": "LineString", "coordinates": [list(reversed(ll(x, y))) for x, y in [(50, 4.2), (10, 4.2), (-30, 4.2)]]},
		},
		{
			"type": "Feature",
			"properties": {"name": "Punto de encuentro", "description": "Junto al banco."},
			"geometry": {"type": "Point", "coordinates": list(reversed(ll(-10, 3.8)))},
		},
	],
}
escribir("ruta.geojson", json.dumps(geo, ensure_ascii=False, indent="\t") + "\n")
