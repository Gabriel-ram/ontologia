from flask import Flask, render_template, request
from rdflib import Graph, RDFS, RDF, Namespace, Literal
from SPARQLWrapper import SPARQLWrapper, JSON
import re

app = Flask(__name__)

# Cargar ontología local
g = Graph()
g.parse("reposteria.rdf", format="xml")

NS = Namespace("http://www.semanticweb.org/ontologies/reposteria#")

# Configurar endpoint de DBpedia
DBPEDIA_ENDPOINT = "https://dbpedia.org/sparql"

def get_all_subclasses(cls):
    subclasses = set()
    for sub in g.subjects(RDFS.subClassOf, cls):
        subclasses.add(sub)
        subclasses |= get_all_subclasses(sub)
    return subclasses

def get_all_superclasses(cls):
    superclasses = set()
    for sup in g.objects(cls, RDFS.subClassOf):
        superclasses.add(sup)
        superclasses |= get_all_superclasses(sup)
    return superclasses

def get_instances_of_class(cls):
    subclasses = {cls} | get_all_subclasses(cls)
    instances = set()
    for c in subclasses:
        for inst in g.subjects(RDF.type, c):
            instances.add(inst)
    return list(instances)

# -----------------------------------------------
# BÚSQUEDA LOCAL (tu código original)
# -----------------------------------------------
def search_instances(term):
    term_lower = term.lower()
    results = []
    seen = set()

    for inst in g.subjects(RDF.type, None):
        if inst in seen:
            continue

        nombre = g.value(inst, NS.nombre)
        inst_name = str(nombre) if nombre else inst.split("#")[-1]

        match = False

        if term_lower in inst_name.lower():
            match = True

        if not match:
            for prop, obj in g.predicate_objects(inst):
                if isinstance(obj, Literal) and term_lower in str(obj).lower():
                    match = True
                    break

        if not match:
            for prop, obj in g.predicate_objects(inst):
                if not isinstance(obj, Literal):
                    obj_name = obj.split("#")[-1].lower()
                    if term_lower in obj_name:
                        match = True
                        break

        if not match:
            for cls_uri in g.objects(inst, RDF.type):
                cls_name = cls_uri.split("#")[-1].lower()
                if term_lower in cls_name:
                    match = True
                    break

        if not match:
            continue

        clases = [cls.split("#")[-1] for cls in g.objects(inst, RDF.type)]

        superclases = []
        for cls_uri in g.objects(inst, RDF.type):
            superclases += [str(s.split("#")[-1]) for s in get_all_superclasses(cls_uri)]

        clases_uris = list(g.objects(inst, RDF.type))
        es_producto = False
        for cls_uri in clases_uris:
            cls_name = cls_uri.split("#")[-1].lower()
            if cls_name == "producto":
                es_producto = True
                break
            superclases_names = [s.split("#")[-1].lower() for s in get_all_superclasses(cls_uri)]
            if "producto" in superclases_names:
                es_producto = True
                break

        ingredientes = []
        herramientas = []
        tecnicas = []
        atributos = {}

        for prop, obj in g.predicate_objects(inst):
            prop_name = prop.split("#")[-1]

            if prop == RDF.type:
                continue

            if es_producto:
                if prop == NS.tieneIngrediente or prop_name.lower().startswith("ingrediente"):
                    ingredientes.append(obj.split("#")[-1])
                    continue

                if prop == NS.usaHerramienta or prop_name.lower().startswith("herramienta"):
                    herramientas.append(obj.split("#")[-1])
                    continue

                if prop == NS.requiereTecnica or prop_name.lower().startswith("tecnica"):
                    tecnicas.append(obj.split("#")[-1])
                    continue

            if isinstance(obj, Literal):
                atributos.setdefault(prop_name, []).append(str(obj))
                continue

            if not es_producto:
                if not isinstance(obj, Literal):
                    atributos.setdefault(prop_name, []).append(obj.split("#")[-1])

        usada_en = []
        for s, p, o in g:
            if str(o) == str(inst):
                usada_en.append(str(s).split("#")[-1])

        results.append({
            "tipo": "instancia",
            "nombre": inst_name,
            "clases": clases,
            "superclases": list(set(superclases)),
            "es_producto": es_producto,
            "ingredientes": ingredientes if es_producto else [],
            "herramientas": herramientas if es_producto else [],
            "tecnicas": tecnicas if es_producto else [],
            "atributos": atributos,
            "usada_en": list(set(usada_en)),
            "fuente": "local"  # Marcador de fuente
        })

        seen.add(inst)

    return results

def search_classes(term):
    term_lower = term.lower()
    results = []

    for cls in g.subjects(RDF.type, RDFS.Class):
        cls_name = cls.split("#")[-1]

        if term_lower != cls_name.lower():
            continue

        atributos = []
        for s, p, o in g.triples((cls, None, None)):
            if "domain" in p.split("#")[-1]: 
                continue
            atributos.append(p.split("#")[-1])

        subclasses = [c.split("#")[-1] for c in get_all_subclasses(cls)]
        superclasses = [c.split("#")[-1] for c in get_all_superclasses(cls)]
        instancias = [i.split("#")[-1] for i in get_instances_of_class(cls)]

        results.append({
            "tipo": "clase",
            "nombre": cls_name,
            "atributos": list(set(atributos)),
            "subclases": subclasses,
            "superclases": superclasses,
            "instancias": instancias,
            "fuente": "local"
        })

    return results


# -----------------------------------------------
# BÚSQUEDA EN DBPEDIA
# -----------------------------------------------
def search_dbpedia_food(term):
    """
    Busca recetas, postres, ingredientes relacionados con repostería en DBpedia
    """
    results = []
    
    try:
        sparql = SPARQLWrapper(DBPEDIA_ENDPOINT)
        sparql.setTimeout(20)
        
        # Traducir términos comunes al inglés para mejor búsqueda
        term_translations = {
            'chocolate': 'chocolate',
            'vainilla': 'vanilla',
            'pastel': 'cake',
            'galleta': 'cookie',
            'tarta': 'tart',
            'postre': 'dessert',
            'brownie': 'brownie',
            'cheesecake': 'cheesecake',
            'cupcake': 'cupcake',
            'bizcocho': 'sponge cake',
            'mousse': 'mousse',
            'flan': 'flan',
            'tiramisu': 'tiramisu',
            'macarons': 'macaron'
        }
        
        search_term = term_translations.get(term.lower(), term)
        
        # Consulta SPARQL simplificada
        query = f"""
        PREFIX dbo: <http://dbpedia.org/ontology/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT DISTINCT ?item ?label
        WHERE {{
            ?item rdfs:label ?label .
            FILTER(LANG(?label) = "en")
            FILTER(CONTAINS(LCASE(?label), LCASE("{search_term}")))
           
            {{
                ?item a dbo:Food .
            }}
            UNION
            {{
                ?item a dbo:Ingredient .
            }}
        }}
        LIMIT 8
        """
        
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        query_results = sparql.query().convert()
        
        processed_items = set()
        
        for result in query_results["results"]["bindings"]:
            item_uri = result["item"]["value"]
            
            if item_uri in processed_items:
                continue
            processed_items.add(item_uri)
            
            label = result.get("label", {}).get("value", item_uri.split("/")[-1])
            
            print(f"\n{'='*60}")
            print(f"Procesando: {label}")
            print(f"URI: {item_uri}")
            
            # ===== CONSULTA CORREGIDA - UNION dentro del WHERE =====
            abstract = "Descripción no disponible en DBpedia"
            try:
                abstract_query = f"""
                PREFIX dbo: <http://dbpedia.org/ontology/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT ?text
                WHERE {{
                    {{
                        <{item_uri}> dbo:abstract ?text .
                        FILTER(LANG(?text) = "en")
                    }}
                    UNION
                    {{
                        <{item_uri}> rdfs:comment ?text .
                        FILTER(LANG(?text) = "en")
                    }}
                    UNION
                    {{
                        <{item_uri}> dbo:description ?text .
                    }}
                }}
                LIMIT 1
                """
                
                sparql_abstract = SPARQLWrapper(DBPEDIA_ENDPOINT)
                sparql_abstract.setQuery(abstract_query)
                sparql_abstract.setReturnFormat(JSON)
                sparql_abstract.setTimeout(10)
                abstract_result = sparql_abstract.query().convert()
                
                if abstract_result["results"]["bindings"]:
                    abstract = abstract_result["results"]["bindings"][0]["text"]["value"]
                    print(f"✓ Descripción obtenida correctamente")
                else:
                    print(f"✗ No se encontró ninguna descripción")
                    
            except Exception as e:
                print(f"✗ Error: {str(e)}")
                abstract = "Descripción no disponible en DBpedia"
            
            # Limitar el abstract a 400 caracteres
            if abstract and abstract != "Descripción no disponible en DBpedia" and len(abstract) > 400:
                abstract = abstract[:397] + "..."
            
            # Buscar ingredientes
            ingredientes = []
            try:
                ing_query = f"""
                PREFIX dbo: <http://dbpedia.org/ontology/>
                
                SELECT DISTINCT ?ingredient 
                WHERE {{
                    <{item_uri}> dbo:ingredient ?ingredient .
                }}
                LIMIT 15
                """
                sparql_ing = SPARQLWrapper(DBPEDIA_ENDPOINT)
                sparql_ing.setQuery(ing_query)
                sparql_ing.setReturnFormat(JSON)
                sparql_ing.setTimeout(10)
                ing_results = sparql_ing.query().convert()
                
                for ing_result in ing_results["results"]["bindings"]:
                    ing = ing_result["ingredient"]["value"]
                    ing_name = ing.split("/")[-1].replace("_", " ")
                    if ing_name not in ingredientes:
                        ingredientes.append(ing_name)
                        
                print(f"Ingredientes: {len(ingredientes)}")
            except:
                pass
            
            # Buscar país de origen y región
            pais_origen = None
            region = None
            
            try:
                location_query = f"""
                PREFIX dbo: <http://dbpedia.org/ontology/>
                PREFIX dbp: <http://dbpedia.org/property/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT DISTINCT ?countryLabel ?regionLabel 
                WHERE {{
                    OPTIONAL {{
                        <{item_uri}> dbo:country ?country .
                        ?country rdfs:label ?countryLabel .
                        FILTER(LANG(?countryLabel) = "en")
                    }}
                    OPTIONAL {{
                        <{item_uri}> dbp:country ?country2 .
                        ?country2 rdfs:label ?countryLabel .
                        FILTER(LANG(?countryLabel) = "en")
                    }}
                    OPTIONAL {{
                        <{item_uri}> dbo:region ?region .
                        ?region rdfs:label ?regionLabel .
                        FILTER(LANG(?regionLabel) = "en")
                    }}
                }}
                LIMIT 1
                """
                sparql_loc = SPARQLWrapper(DBPEDIA_ENDPOINT)
                sparql_loc.setQuery(location_query)
                sparql_loc.setReturnFormat(JSON)
                sparql_loc.setTimeout(10)
                loc_results = sparql_loc.query().convert()
                
                if loc_results["results"]["bindings"]:
                    loc_data = loc_results["results"]["bindings"][0]
                    if "countryLabel" in loc_data:
                        pais_origen = loc_data["countryLabel"]["value"]
                    if "regionLabel" in loc_data:
                        region = loc_data["regionLabel"]["value"]
            except:
                pass
            
            # Construir atributos
            atributos = {
                "descripcion": [abstract]
            }
            
            if pais_origen:
                atributos["pais_origen"] = [pais_origen]
            
            if region:
                atributos["region"] = [region]
            
            atributos["dbpedia_uri"] = [item_uri]
            
            results.append({
                "tipo": "instancia",
                "nombre": label,
                "clases": ["Food (DBpedia)"],
                "superclases": [],
                "es_producto": True,
                "ingredientes": ingredientes[:12],
                "herramientas": [],
                "tecnicas": [],
                "atributos": atributos,
                "usada_en": [],
                "fuente": "dbpedia"
            })
        
    except Exception as e:
        print(f"Error consultando DBpedia: {e}")
    
    return results

def search_dbpedia_ingredients(term):
    """
    Busca ingredientes específicos en DBpedia
    """
    results = []
    
    try:
        sparql = SPARQLWrapper(DBPEDIA_ENDPOINT)
        sparql.setTimeout(10)
        
        query = f"""
        PREFIX dbo: <http://dbpedia.org/ontology/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT DISTINCT ?item ?label ?abstract ?type
        WHERE {{
            {{
                ?item a dbo:Ingredient .
                ?item rdfs:label ?label .
                FILTER(LANG(?label) = "en")
                FILTER(CONTAINS(LCASE(?label), LCASE("{term}")))
            }}
            UNION
            {{
                ?item rdfs:label ?label .
                ?item a ?type .
                FILTER(LANG(?label) = "en")
                FILTER(CONTAINS(LCASE(?label), LCASE("{term}")))
                FILTER(?type = dbo:Food || ?type = dbo:Ingredient)
            }}
            
            OPTIONAL {{ ?item dbo:abstract ?abstract . FILTER(LANG(?abstract) = "en") }}
        }}
        LIMIT 5
        """
        
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        query_results = sparql.query().convert()
        
        for result in query_results["results"]["bindings"]:
            label = result.get("label", {}).get("value", "")
            abstract = result.get("abstract", {}).get("value", "Sin descripción")
            
            if len(abstract) > 300:
                abstract = abstract[:297] + "..."
            
            results.append({
                "tipo": "instancia",
                "nombre": label,
                "clases": ["Ingredient (DBpedia)"],
                "superclases": [],
                "es_producto": False,
                "ingredientes": [],
                "herramientas": [],
                "tecnicas": [],
                "atributos": {
                    "descripcion": [abstract]
                },
                "usada_en": [],
                "fuente": "dbpedia"
            })
    
    except Exception as e:
        print(f"Error consultando DBpedia ingredientes: {e}")
    
    return results


# -----------------------------------------------
# 🔍 CONTROLADOR PRINCIPAL
# -----------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    results = []
    term = ""

    if request.method == "POST":
        term = request.form.get("term", "").strip()

        if term:
            # 1. Buscar en ontología local
            inst_res = search_instances(term)
            class_res = search_classes(term)
            local_results = inst_res + class_res
            
            # 2. Buscar en DBpedia (siempre para enriquecer)
            dbpedia_food_results = search_dbpedia_food(term)
            dbpedia_ingredient_results = search_dbpedia_ingredients(term)
            
            # 3. Combinar resultados: primero locales, luego DBpedia
            results = local_results + dbpedia_food_results + dbpedia_ingredient_results
            
            # Si no hay resultados locales, asegurar que al menos haya algo de DBpedia
            if not local_results and not dbpedia_food_results:
                results.append({
                    "tipo": "mensaje",
                    "nombre": f"No se encontraron resultados locales para '{term}'",
                    "fuente": "sistema"
                })

    return render_template("index.html", results=results, term=term)

if __name__ == "__main__":
    app.run(debug=True)