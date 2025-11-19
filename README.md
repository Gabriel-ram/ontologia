Buscador Semántico - Repostería
===============================

Contenido del repositorio:
- app.py               -> Aplicación Flask que consulta DBpedia y muestra resultados.
- templates/index.html -> Página de búsqueda.
- templates/results.html-> Página de resultados.
- reposteria.rdf      -> Ontología OWL básica (clases y propiedades).
- README.md            -> Este archivo.

Requisitos:
  pip install flask rdflib

Cómo ejecutar la app (local):
  1. Activar un entorno virtual (recomendado).
  2. Instalar dependencias.
  3. python app.py
  4. Abrir http://127.0.0.1:5000 en el navegador.

Cómo poblar la ontología (ejemplo):
  python populate_ontology.py --lang es --limit 50 --out populated.owl

Notas:
- El script populate_ontology.py realiza consultas SPARQL a DBpedia y requiere conexión a internet.
