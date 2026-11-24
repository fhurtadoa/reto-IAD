"""Transcripción independiente de los enunciados originales de IAD."""
from pathlib import Path
import json
import sys

EQUAL = [(0.5, 0.5)]


def model(name, variables, objectives, constraints, integer=False):
    return {
        "name": name,
        "variables": [
            {"name": v, "var_type": "integer" if integer else "continuous",
             "lower_bound": 0, "upper_bound": None} for v in variables
        ],
        "objectives": [
            {"name": title, "sense": sense, "coefficients": coeffs}
            for title, sense, coeffs in objectives
        ],
        "constraints": [
            {"name": title, "sense": sense, "coefficients": coeffs, "rhs": rhs}
            for title, sense, coeffs, rhs in constraints
        ],
        "weights": [0.5, 0.5],
    }


def transportation(n=0, integer=False):
    # Taller 1, enunciado. Taller 2, celdas 9–12 (índices desde cero).
    return model(
        f"IAD Transporte {'T2 n='+str(n) if integer else 'continuo base'}",
        [f"x{i+1}{j+1}" for i in range(3) for j in range(4)],
        [("Costo", "minimize", [4,3,3,4,5,2,1,5,7,10,8,9]),
         ("Riesgo", "minimize", [6,0,1,5,2,4,0,2,3,1,2,1])],
        [(f"Oferta O{i+1}", "<=", [int(k//4==i) for k in range(12)], bound)
         for i,bound in enumerate((800+n,1200,1500))]
        + [(f"Demanda D{j+1}", ">=", [int(k%4==j) for k in range(12)], bound)
           for j,bound in enumerate((500,700+n,900,1400))], integer,
    )


def paper(n=0, assigned=False):
    # Taller 1 y Taller 3, tablas TASAPROD, COSTEPROD, FCij, DATDEM, TIEMPOMAQ.
    rate = [53,51,52,42,52,49,45,44,49,44,47,40]
    return model(
        f"IAD Papel {'T3 n='+str(n) if assigned else 'T1 base'}",
        [f"x{i+1}{j+1}" for i in range(3) for j in range(4)],
        [("Costo (millones de pesos)", "minimize", [76,82,96,72,75,70,95,71,73,78,92,70]),
         ("Calidad (factor·ton)", "maximize", [45,76,39,45,42,64,41,42,38,70,36,38])],
        [(f"Tiempo M{i+1}", "<=", [1/r if k//4==i else 0 for k,r in enumerate(rate)], bound)
         for i,bound in enumerate((5,3,3))]
        + [(f"Demanda {name}", ">=", [int(k%4==j) for k in range(12)], bound)
           for j,(name,bound) in enumerate(zip(("Prensa","Folio","Imprenta","Reciclado"),(77+n,81,99,105)))],
    )


def chain(integer):
    # Enunciado T1, dos eslabones. Objetivo en días·caja: entregable pp. 8–9.
    return model(
        f"IAD Cadena {'entera' if integer else 'continua'}",
        ["x11","x12","x21","x22","y11","y12","y13","y21","y22","y23"],
        [("Costo (USD)", "minimize", [60,65,60,65,50,80,65,90,60,65]),
         ("Tiempo (dias-caja)", "minimize", [1,2,1,2,4,5,3,3,2,6])],
        [("Planta 1","<=",[1,1,0,0,0,0,0,0,0,0],563.35),
         ("Planta 2","<=",[0,0,1,1,0,0,0,0,0,0],563.35),
         ("Bodega 1","<=",[1,0,1,0,0,0,0,0,0,0],500),
         ("Bodega 2","<=",[0,1,0,1,0,0,0,0,0,0],600),
         ("Region 1",">=",[0,0,0,0,1,0,0,1,0,0],300),
         ("Region 2",">=",[0,0,0,0,0,1,0,0,1,0],300),
         ("Region 3",">=",[0,0,0,0,0,0,1,0,0,1],300),
         ("Balance 1","==",[19,0,19,0,-20,-20,-20,0,0,0],0),
         ("Balance 2","==",[0,19,0,19,0,0,0,-20,-20,-20],0)], integer,
    )


def all_cases():
    cases = {
        "clase11": (model("IAD Clase 11 p8", ["x1","x2"],
                          [("Z1","maximize",[4,8]),("Z2","maximize",[5,3])],
                          [("Suma","<=",[1,1],10),("Capacidad","<=",[3,1],15)]), EQUAL, "all"),
        "celdas": (model("IAD Celdas Clase 14 y 15", ["x1","x2"],
                         [("Margen bruto (USD)","maximize",[1000,3000]),
                          ("Contaminantes (kg)","minimize",[1,2])],
                         [("Cota satelites","<=",[1,0],300),("Cota GPS","<=",[0,1],200),
                          ("Horas","<=",[1,1],400),("Punto de equilibrio",">=",[1000,3000],300000)]),
                   EQUAL + [(i/5, (5-i)/5) for i in range(6)], "all"),
        "transporte": (transportation(), EQUAL + [(0,1),(.25,.75),(.75,.25),(1,0)], "all"),
        "papel": (paper(), EQUAL, "all"),
        "cadena_continua": (chain(False), EQUAL, "all"),
        "cadena_entera": (chain(True), EQUAL, "all"),
    }
    for n in range(10):
        cases[f"t2_{n}"] = (transportation(n, True), [(1,0)] if n==5 else EQUAL, "payoff")
        cases[f"t3_{n}"] = (paper(n, True), [((50+n)/100, (50-n)/100)], "all")
    return cases


def metric_workbook():
    # Hoja1 D11:F14. Los valores ya están normalizados de 0 a 100.
    definition = model("IAD Ejercicio para entender la metrica", [f"a{i}" for i in range(1, 5)],
                       [(f"Objetivo {i + 1}", "maximize", [0 if j == i else 100 for j in range(3)] + [200 / 3])
                        for i in range(3)], [("Una alternativa", "==", [1, 1, 1, 1], 1)])
    for variable in definition["variables"]:
        variable.update(var_type="binary", upper_bound=1)
    return definition, [(1 / 3, 1 / 3, 1 / 3)], "workbook"


def main(directory):
    directory.mkdir(parents=True, exist_ok=True)
    schedule = {}
    for key, (definition, profiles, scope) in {**all_cases(), "metrica_discreta": metric_workbook()}.items():
        definition["weights"] = list(profiles[0])
        (directory / f"{key}.json").write_text(json.dumps(definition, ensure_ascii=False))
        schedule[key] = {"weights": profiles, "scope": scope}
    (directory / "agenda.json").write_text(json.dumps(schedule, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
