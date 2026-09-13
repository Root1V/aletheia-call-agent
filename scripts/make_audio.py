#!/usr/bin/env python
"""Renderiza los guiones de `evals/scenarios/*.yaml` a audio.

Usa `say`, el sintetizador que ya trae macOS, en vez de añadir un motor de TTS
al proyecto: para un conjunto de evaluación sólo hace falta audio reproducible
y con voces distintas por hablante.

    uv run python scripts/make_audio.py

LIMITACIÓN que conviene tener presente al leer cualquier WER medido sobre este
material: macOS no trae voz peruana. Las disponibles son de España y México, y
un modelo puede comportarse distinto con acento limeño, con seseo andino o con
el vocabulario local. El número que sale de aquí sirve para detectar
regresiones entre versiones, no para prometerle a nadie una tasa de acierto en
producción.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import wave
from pathlib import Path

import yaml

RAIZ_GUIONES = Path("evals/scenarios")
RAIZ_AUDIO = Path("evals/audio")
TASA = 16000


def _say_a_wav(texto: str, voz: str, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["say", "-v", voz, "-o", str(destino), "--data-format=LEI16@16000", texto],
        check=True,
        capture_output=True,
    )


def _duracion_ms(wav: Path) -> int:
    with wave.open(str(wav)) as w:
        return int(w.getnframes() / w.getframerate() * 1000)


def renderizar(guion: Path, forzar: bool = False) -> dict:
    datos = yaml.safe_load(guion.read_text())
    sid = datos["scenario_id"]
    voces = datos["voces"]
    salida = RAIZ_AUDIO / sid
    salida.mkdir(parents=True, exist_ok=True)

    turnos = []
    for i, turno in enumerate(datos["turnos"]):
        hablante = turno["speaker"]
        # El YAML pliega los saltos de línea en espacios; se normalizan para
        # que el texto de referencia del WER sea exactamente lo pronunciado.
        texto = " ".join(turno["texto"].split())
        wav = salida / f"{i:02d}-{hablante}.wav"
        if forzar or not wav.exists():
            _say_a_wav(texto, voces[hablante], wav)
        turnos.append(
            {
                "indice": i,
                "speaker": hablante,
                "texto": texto,
                "wav": str(wav),
                "duracion_ms": _duracion_ms(wav),
                "pausa_antes_ms": turno.get("pausa_antes_ms", 300),
            }
        )

    manifiesto = {
        "scenario_id": sid,
        "descripcion": datos.get("descripcion", ""),
        "resultado_esperado": datos.get("resultado_esperado", {}),
        "sample_rate": TASA,
        "turnos": turnos,
        "duracion_total_ms": sum(t["duracion_ms"] + t["pausa_antes_ms"] for t in turnos),
    }
    (salida / "manifiesto.yaml").write_text(
        yaml.safe_dump(manifiesto, allow_unicode=True, sort_keys=False)
    )
    return manifiesto


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Renderiza los guiones a audio.")
    p.add_argument("--force", action="store_true", help="Regenera aunque el wav exista.")
    p.add_argument("--scenario", help="Sólo este guion.")
    args = p.parse_args(argv)

    if sys.platform != "darwin":
        print("Este generador usa `say`, que sólo existe en macOS.", file=sys.stderr)
        return 1

    guiones = sorted(RAIZ_GUIONES.glob("*.yaml"))
    if args.scenario:
        guiones = [g for g in guiones if g.stem == args.scenario]
    if not guiones:
        print("No hay guiones en evals/scenarios/", file=sys.stderr)
        return 1

    for g in guiones:
        m = renderizar(g, forzar=args.force)
        seg = m["duracion_total_ms"] / 1000
        print(
            f"{m['scenario_id']}: {len(m['turnos'])} turnos · {seg:.1f}s"
            f" → {RAIZ_AUDIO / m['scenario_id']}"
        )

    print("\nNota: las voces son de España y México; macOS no trae voz peruana.")
    print("El WER medido aquí sirve para detectar regresiones, no como promesa de producción.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
