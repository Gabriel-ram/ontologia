Buscador Semántico – Repostería

Este proyecto es un buscador semántico local basado en una ontología de repostería en formato RDF/OWL.
Permite buscar instancias, clases, ingredientes, herramientas y técnicas definidas dentro de la ontología, mostrando sus relaciones y atributos.

Contenido del repositorio

- app.py Aplicación: Flask que carga la ontología local (reposteria.rdf) usando rdflib y ejecuta las búsquedas.
- templates/index.html : Página principal con el buscador y visualización de resultados.
- static/css/styles.css: Estilos visuales del buscador.
- reposteria.rdf: Ontología OWL/RDF con clases, subclases, propiedades e instancias del dominio de la repostería.
- README.md: Este archivo.
Requisitos:
  pip install flask rdflib

Cómo ejecutar la app (local):
  1. Asegúrate de que app.py y reposteria.rdf estén en la misma carpeta del proyecto.
  2. Instalar dependencias.
  3. python app.py
  4. Abrir http://127.0.0.1:5000 en el navegador.

Cómo poblar la ontología (ejemplo):
  python populate_ontology.py --lang es --limit 50 --out populated.owl

Notas:
- La aplicación NO se conecta a DBpedia.
Todo funciona de manera local mediante el archivo reposteria.rdf.
- El sistema funciona exclusivamente con:
Flask (para el servidor web)
RDFlib (para cargar y recorrer la ontología RDF)