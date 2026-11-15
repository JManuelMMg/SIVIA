"""
Agente Vigía: clima y eventos extremos con datos del Servicio Meteorológico Nacional (dataset #45).

1. Series diarias históricas de precipitación de las estaciones 14065 Guadalajara (OBS) y
   14066 Guadalajara (DGE) de la Base de Datos Climatológica Nacional (SMN/CONAGUA).
   De ahí salen los umbrales de lluvia intensa (percentiles 90, 95 y 99 de los días con lluvia),
   la climatología mensual y el número de eventos extremos por año.
2. Pronóstico diario por municipio del SMN (4 días) para Guadalajara.
3. Cruce con ATUS (dataset #08): accidentes por mes contra lluvia del mes, 2022-2024.
4. Factor de clima por tipo de hallazgo para el Coordinador.

Uso:  python agente/vigia_smn.py            (descarga y calcula)
      python agente/vigia_smn.py --sin-red  (usa los archivos ya descargados)
Salida: agente/salida/clima_smn.json
"""
import argparse
import csv
import gzip
import json
import os
import statistics as st
import urllib.request
from collections import defaultdict
from datetime import date

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(BASE, "datos", "smn")
SALIDA = os.path.join(BASE, "agente", "salida")
ESTACIONES = {"14065": "Guadalajara (OBS)", "14066": "Guadalajara (DGE)"}
URL_DIARIO = "https://smn.conagua.gob.mx/tools/RESOURCES/Normales_Climatologicas/Diarios/jal/dia{}.txt"
URL_PRONOSTICO = "https://smn.conagua.gob.mx/tools/GUI/webservices/?method=1"

# Qué hallazgos empeoran con lluvia o viento, y cuánto (multiplicador máximo en evento extremo)
SENSIBLE = {
    "alcantarilla_tapada": ("lluvia", 0.6), "alcantarilla_riesgo": ("lluvia", 0.6),
    "bache": ("lluvia", 0.35), "dano_pavimento": ("lluvia", 0.35), "grieta_cocodrilo": ("lluvia", 0.25),
    "arbol_riesgo": ("viento", 0.6), "rama_riesgo": ("viento", 0.6), "rama_sobre_cable": ("viento", 0.6), "tronco_inclinado": ("viento", 0.6),
    "poste_electrico": ("viento", 0.4), "sin_cruce": ("lluvia", 0.15),
}


def bajar(url, destino):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(destino, "wb") as fh:
        fh.write(r.read())


def serie(path):
    """{fecha: precipitación mm} de un archivo diario del SMN (FECHA PRECIP EVAP TMAX TMIN)."""
    out = {}
    with open(path, encoding="latin-1") as fh:
        for linea in fh:
            p = linea.split()
            if len(p) >= 2 and len(p[0]) == 10 and p[0][4] == "-":
                try:
                    out[date.fromisoformat(p[0])] = float(p[1])
                except ValueError:
                    pass  # NULO
    return out


def pct(v, q):
    v = sorted(v)
    k = (len(v) - 1) * q
    i = int(k)
    return v[i] + (v[min(i + 1, len(v) - 1)] - v[i]) * (k - i)


def nivel(prec, prob, raf, u):
    """0 normal, 1 lluvia/viento fuerte, 2 evento extremo (según umbrales históricos)."""
    if prec >= u["p99"] or raf >= 60:
        return 2
    if prec >= u["p95"] or raf >= 45:
        return 2 if prec >= u["p95"] and prob >= 60 else 1
    if prec >= u["p90"] or raf >= 35 or (prob >= 70 and prec >= 5):
        return 1
    return 0


def factores(lluvia, viento):
    """Multiplicador por hallazgo dado el nivel de lluvia y de viento (0, 1, 2)."""
    return {k: round(1 + m * ({"lluvia": lluvia, "viento": viento}[tipo] / 2), 3)
            for k, (tipo, m) in SENSIBLE.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-red", action="store_true")
    a = ap.parse_args()
    os.makedirs(DATOS, exist_ok=True)
    os.makedirs(SALIDA, exist_ok=True)
    if not a.sin_red:
        for e in ESTACIONES:
            bajar(URL_DIARIO.format(e), os.path.join(DATOS, f"dia{e}.txt"))
        bajar(URL_PRONOSTICO, os.path.join(DATOS, "pronostico_municipios.gz"))

    # 1) Serie combinada: promedio de las estaciones disponibles cada día
    series = {e: serie(os.path.join(DATOS, f"dia{e}.txt")) for e in ESTACIONES}
    dias = defaultdict(list)
    for s in series.values():
        for d, v in s.items():
            dias[d].append(v)
    comb = {d: sum(v) / len(v) for d, v in dias.items() if d.year >= 1981}
    lluviosos = [v for v in comb.values() if v >= 0.1]
    u = {q: round(pct(lluviosos, p), 1) for q, p in (("p90", .90), ("p95", .95), ("p99", .99))}
    anios = sorted({d.year for d in comb})
    por_mes = defaultdict(list)
    for d, v in comb.items():
        por_mes[(d.year, d.month)].append(v)
    completos = {k: sum(v) for k, v in por_mes.items() if len(v) >= 25}
    clima_mes = [round(st.mean([t for (y, m), t in completos.items() if m == mes]), 1) for mes in range(1, 13)]
    extremos = defaultdict(int)
    for d, v in comb.items():
        if v >= u["p95"]:
            extremos[d.year] += 1
    ext_mes = [0] * 12
    for d, v in comb.items():
        if v >= u["p95"]:
            ext_mes[d.month - 1] += 1
    maximo = max(comb.items(), key=lambda kv: kv[1])

    # 2) Pronóstico SMN para Guadalajara (ides 14, idmun 39)
    with gzip.open(os.path.join(DATOS, "pronostico_municipios.gz")) as fh:
        pron = [r for r in json.loads(fh.read()) if r.get("ides") == "14" and r.get("idmun") == "39"]
    dias_p = []
    for r in sorted(pron, key=lambda r: int(r["ndia"])):
        prec, prob, raf = float(r["prec"]), float(r["probprec"]), float(r["raf"])
        nl = nivel(prec, prob, 0, u)
        nv = 2 if raf >= 60 else 1 if raf >= 35 else 0
        dias_p.append({"fecha": r["dloc"][:8], "cielo": r["desciel"], "tmax": float(r["tmax"]), "tmin": float(r["tmin"]),
                       "prec_mm": prec, "prob_prec": prob, "rafagas_kmh": raf, "viento_kmh": float(r["velvien"]),
                       "nivel_lluvia": nl, "nivel_viento": nv})
    nl_max = max((d["nivel_lluvia"] for d in dias_p), default=0)
    nv_max = max((d["nivel_viento"] for d in dias_p), default=0)

    # 3) Lluvia del mes contra accidentes del mes (ATUS 2022-2024)
    acc_mes = defaultdict(int)
    with open(os.path.join(BASE, "datos", "atus_gdl_2022_2024.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            acc_mes[(int(r["ANIO"]), int(r["MES"]))] += 1
    pares = [(completos[k], acc_mes[k]) for k in sorted(acc_mes) if k in completos]
    r_pearson = None
    if len(pares) > 5:
        xs, ys = zip(*pares)
        mx, my = st.mean(xs), st.mean(ys)
        num = sum((x - mx) * (y - my) for x, y in pares)
        den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
        r_pearson = round(num / den, 3) if den else None
    temporal = [y for (yy, m), y in acc_mes.items() if 6 <= m <= 9]
    secas = [y for (yy, m), y in acc_mes.items() if not 6 <= m <= 9]

    out = {
        "fuente": "SMN/CONAGUA: Base de Datos Climatológica Nacional (estaciones 14065 y 14066) "
                  "y pronóstico diario por municipio",
        "estaciones": ESTACIONES,
        "periodo_historico": [min(comb).isoformat(), max(comb).isoformat()],
        "dias_con_dato": len(comb),
        "umbrales_mm": u,
        "maximo_historico": {"fecha": maximo[0].isoformat(), "mm": round(maximo[1], 1)},
        "climatologia_mensual_mm": clima_mes,
        "eventos_extremos_por_mes": ext_mes,
        "eventos_extremos_por_anio": {str(y): extremos.get(y, 0) for y in anios[-15:]},
        "pronostico": dias_p,
        "nivel_actual": {"lluvia": nl_max, "viento": nv_max},
        "factores_actuales": factores(nl_max, nv_max),
        "factores_escenario_extremo": factores(2, 2),
        "lluvia_vs_accidentes": {
            "meses": [{"anio": k[0], "mes": k[1], "lluvia_mm": round(completos.get(k, 0), 1), "accidentes": v}
                      for k, v in sorted(acc_mes.items())],
            "pearson_r": r_pearson,
            "accidentes_promedio_temporal_jun_sep": round(st.mean(temporal), 1) if temporal else None,
            "accidentes_promedio_resto": round(st.mean(secas), 1) if secas else None},
    }
    with open(os.path.join(SALIDA, "clima_smn.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ("periodo_historico", "dias_con_dato", "umbrales_mm", "maximo_historico",
                                          "climatologia_mensual_mm", "eventos_extremos_por_mes", "nivel_actual")},
                     ensure_ascii=False))
    print("pronóstico:", [(d["fecha"], d["prec_mm"], d["prob_prec"], d["rafagas_kmh"]) for d in dias_p])
    print("lluvia vs accidentes:", {k: v for k, v in out["lluvia_vs_accidentes"].items() if k != "meses"})


if __name__ == "__main__":
    main()
