#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
weather.py — Leitura de meteorologia para o Briefing Diário (Lisboa)

Substitui o passo `web_search: "Lisboa weather today ... hourly forecast"`
(Secção 3.5 de BRIEFING_DIARIO_v12.0.md) por uma chamada directa à API
gratuita e sem chave da Open-Meteo (https://open-meteo.com). Não exige
julgamento nenhum — é leitura determinística de dados, por isso não
precisa de passar pela LLM. Apenas a stdlib do Python (urllib), tal como
o script de publicação no GitHub já usado pelo módulo HFF.

Uso:
    python3 weather.py > tempo.json
    python3 weather.py --date 2026-07-10 > tempo.json   (para os "horas_chave")

Saída (JSON, stdout):
{
  "location": "Lisboa",
  "generated_at": "<ISO8601>",
  "current_temp": <int>,
  "tabela_7dias": [ {"date": "Sex 10", "icone": "☀️", "max": 29, "min": 19, "chuva_pct": 0}, ... x7 ],
  "horas_chave": {
    "08:00": {"temp": 21, "icone": "☀️"},
    "16:30": {"temp": 27, "icone": "🌤️"},
    "21:00": {"temp": 24, "icone": "🌤️"}
  }
}

O briefing usa "tabela_7dias" directamente na tab Tempo, e "horas_chave"
para montar tempo.janelas (o script não decide horários/actividades —
isso é lógica do módulo, ex: regresso às 16h30 ou ~21h em dia SIGIC).

Código de saída 0 = sucesso. Falha de rede/API aborta com mensagem clara
(nunca inventa uma previsão).
"""

import sys
import json
import argparse
import urllib.request
import urllib.error
from datetime import datetime

LAT, LON = 38.7223, -9.1393
TIMEZONE = "Europe/Lisbon"

DIAS_ABR = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

WEATHERCODE_ICON = {
    0: "☀️",
    1: "🌤️", 2: "⛅", 3: "☁️",
    45: "🌫️", 48: "🌫️",
    51: "🌦️", 53: "🌦️", 55: "🌦️",
    56: "🌦️", 57: "🌦️",
    61: "🌧️", 63: "🌧️", 65: "🌧️",
    66: "🌧️", 67: "🌧️",
    71: "🌨️", 73: "🌨️", 75: "🌨️", 77: "🌨️",
    80: "🌦️", 81: "🌧️", 82: "🌧️",
    85: "🌨️", 86: "🌨️",
    95: "⛈️", 96: "⛈️", 99: "⛈️",
}


def icon_for(code):
    return WEATHERCODE_ICON.get(code, "🌡️")


def fetch_forecast():
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        "&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
        "&hourly=temperature_2m,weathercode"
        "&current_weather=true"
        f"&timezone={TIMEZONE.replace('/', '%2F')}"
        "&forecast_days=7"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "personal-system-briefing/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(f"ERRO: falha ao contactar a Open-Meteo — {e}", file=sys.stderr)
        sys.exit(2)


def nearest_hour_index(hourly_times, target_iso_prefix):
    for i, t in enumerate(hourly_times):
        if t.startswith(target_iso_prefix):
            return i
    return None


def build_weather_json(raw, target_date=None):
    daily = raw.get("daily")
    hourly = raw.get("hourly")
    current = raw.get("current_weather")
    if not daily or not hourly or not current:
        print("ERRO: resposta da Open-Meteo sem 'daily'/'hourly'/'current_weather'.", file=sys.stderr)
        sys.exit(3)

    tabela_7dias = []
    for i, date_str in enumerate(daily["time"]):
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        dia_abr = DIAS_ABR[dt.weekday()]
        tabela_7dias.append({
            "date": f"{dia_abr} {dt.day}",
            "icone": icon_for(daily["weathercode"][i]),
            "max": round(daily["temperature_2m_max"][i]),
            "min": round(daily["temperature_2m_min"][i]),
            "chuva_pct": daily["precipitation_probability_max"][i],
        })

    if target_date is None:
        target_date = daily["time"][0]

    horas_chave = {}
    for hhmm in ("08:00", "16:30", "21:00"):
        prefix = f"{target_date}T{hhmm}"
        idx = nearest_hour_index(hourly["time"], f"{target_date}T{hhmm[:2]}")
        if idx is not None:
            horas_chave[hhmm] = {
                "temp": round(hourly["temperature_2m"][idx]),
                "icone": icon_for(hourly["weathercode"][idx]),
            }
        else:
            horas_chave[hhmm] = None

    return {
        "location": "Lisboa",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "current_temp": round(current["temperature"]),
        "tabela_7dias": tabela_7dias,
        "horas_chave": horas_chave,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD para calcular horas_chave (default: hoje)")
    args = parser.parse_args()

    raw = fetch_forecast()
    result = build_weather_json(raw, target_date=args.date)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
