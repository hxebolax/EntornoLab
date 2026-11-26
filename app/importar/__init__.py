"""Importación de entornos desde fuentes externas: OpenStreetMap, DXF, SVG, GPX y GeoJSON.

Todo lo que sale de aquí es un BORRADOR que el profesional revisa y completa:
cada importador devuelve el entorno y un informe en español con lo importado,
lo deducido, lo que la fuente no dice y lo que conviene comprobar in situ.

Regla común: nada inventado. Si la fuente no dice algo, se dice «el mapa no
lo dice» en lugar de suponerlo.

Privacidad: solo ``osm.buscar_lugar`` y ``osm.descargar_zona`` salen a
Internet, y solo cuando el profesional lo pide. Los planos (DXF, SVG, imagen
de fondo) se leen del disco y nunca salen del equipo.
"""
