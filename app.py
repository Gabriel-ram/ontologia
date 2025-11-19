from flask import Flask, render_template, request
from rdflib import Graph, RDFS, RDF, Namespace, Literal

app = Flask(__name__)

# Cargar ontología
g = Graph()
g.parse("reposteria.rdf", format="xml")  # Ajusta el nombre de tu archivo RDF

NS = Namespace("http://www.semanticweb.org/ontologies/reposteria#")

# Obtener subclases recursivamente
def get_all_subclasses(cls):
    subclasses = set()
    for sub in g.subjects(RDFS.subClassOf, cls):
        subclasses.add(sub)
        subclasses |= get_all_subclasses(sub)
    return subclasses

# Obtener todas las superclases de una clase
def get_all_superclasses(cls):
    superclasses = set()
    for sup in g.objects(cls, RDFS.subClassOf):
        superclasses.add(sup)
        superclasses |= get_all_superclasses(sup)
    return superclasses

# Buscar instancias según término
def search_instances(term):
    term_lower = term.lower()
    results = []
    seen = set()

    # Iteramos sobre todas las instancias
    for inst in g.subjects(RDF.type, None):
        if inst in seen:
            continue

        # Nombre de la instancia
        nombre = g.value(inst, NS.nombre)
        inst_name = str(nombre) if nombre else inst.split("#")[-1]

        if term_lower in inst_name.lower():
            # Obtener clases de la instancia
            clases = [cls.split("#")[-1] for cls in g.objects(inst, RDF.type)]
            
            # Obtener superclases
            superclases = []
            for cls_uri in g.objects(inst, RDF.type):
                superclases += [str(s.split("#")[-1]) for s in get_all_superclasses(cls_uri)]
            
            # Obtener propiedades principales
            propiedades = {}
            for prop in [NS.tieneIngrediente, NS.requiereTecnica, NS.usaHerramienta]:
                objetos = [str(o.split("#")[-1]) for o in g.objects(inst, prop)]
                if objetos:
                    propiedades[prop.split("#")[-1]] = objetos

            # Buscar si esta instancia es usada en otras
            usada_en = []
            for s, p, o in g:
                if str(o) == str(inst):
                    usada_en.append(str(s).split("#")[-1])

            results.append({
                "nombre": inst_name,
                "clases": clases,
                "superclases": list(set(superclases)),
                "propiedades": propiedades,
                "usada_en": list(set(usada_en))
            })
            seen.add(inst)

    return results

@app.route("/", methods=["GET", "POST"])
def index():
    results = []
    term = ""
    if request.method == "POST":
        term = request.form.get("term", "")
        results = search_instances(term) if term else []
    return render_template("index.html", results=results, term=term)

if __name__ == "__main__":
    app.run(debug=True)
