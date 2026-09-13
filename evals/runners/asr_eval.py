#!/usr/bin/env python
"""Evaluación del reconocimiento de voz sobre los guiones.

    uv run python evals/runners/asr_eval.py
    uv run python evals/runners/asr_eval.py --telefonia

Mide WER por hablante y la latencia con que aparecen los parciales, que es lo
que el ejecutivo percibe como "el texto va apareciendo mientras habla".

Se evalúa SIEMPRE también con audio degradado a telefonía. La telefonía real
entrega 8 kHz con µ-law, y medir sólo con audio limpio de micrófono produce un
número que se ve bien en una presentación y que no se parece a producción.
"""

from __future__ import annotations

import argparse
import sys
import time
import wave
from pathlib import Path

import yaml

sys.path.insert(0, "services/asr/src")

from cea_asr import (  # noqa: E402
    SherpaStreamingASR,
    calcular_wer,
    degradar_a_telefonia,
    pcm16_a_float32,
)
from cea_contracts import Speaker  # noqa: E402

MODELO = Path("models/sherpa-onnx-streaming-zipformer-es-kroko-2025-08-06")
RAIZ_AUDIO = Path("evals/audio")
TROZO_MS = 100  # tamaño de bloque, como llegaría de la red


def _leer_wav(ruta: Path) -> tuple[bytes, int]:
    with wave.open(str(ruta)) as w:
        return w.readframes(w.getnframes()), w.getframerate()


def evaluar_turno(asr: SherpaStreamingASR, turno: dict, *, telefonia: bool) -> dict:
    pcm, sr = _leer_wav(Path(turno["wav"]))
    if telefonia:
        pcm = degradar_a_telefonia(pcm, sr)
    audio = pcm16_a_float32(pcm)

    call_id = "eval"
    speaker = Speaker(turno["speaker"])
    asr.open(call_id, speaker)

    paso = int(sr * TROZO_MS / 1000)
    parciales: list[tuple[float, str]] = []
    retrasos: list[float] = []
    # Los finales se ACUMULAN, no se reemplazan.
    #
    # El reconocedor corta turno por sí mismo cuando detecta silencio
    # sostenido, así que una intervención del guion puede salir como varios
    # turnos de ASR: "Buenos días." y luego "Mire, le llamo porque...".
    # Quedarse sólo con el último fragmento descarta casi todo lo dicho y
    # produce un WER absurdo que parece culpa del modelo.
    finales: list[str] = []
    t0 = time.perf_counter()

    for i in range(0, len(audio), paso):
        pos_audio_s = (i + paso) / sr
        for hip in asr.accept(call_id, speaker, audio[i : i + paso]):
            transcurrido = time.perf_counter() - t0
            if hip.is_final:
                finales.append(hip.text)
                continue
            parciales.append((pos_audio_s, hip.text))
            # Cuánto tarda el texto en aparecer respecto al audio ya
            # reproducido. Si fuera tiempo real, es el retraso percibido.
            retrasos.append(max(0.0, transcurrido - pos_audio_s))

    for hip in asr.close(call_id, speaker):
        finales.append(hip.text)

    final = " ".join(t for t in finales if t)

    duracion_audio = len(audio) / sr
    proceso = time.perf_counter() - t0
    wer = calcular_wer(turno["texto"], final)

    return {
        "speaker": turno["speaker"],
        "referencia": turno["texto"],
        "hipotesis": final,
        "wer": wer.wer,
        "sustituciones": wer.sustituciones,
        "inserciones": wer.inserciones,
        "borrados": wer.borrados,
        "palabras": wer.palabras_referencia,
        "parciales": len(parciales),
        "fragmentos": len(finales),
        "retraso_max_ms": max(retrasos) * 1000 if retrasos else 0.0,
        "rtf": proceso / duracion_audio,
        "duracion_s": duracion_audio,
    }


def evaluar(scenario_id: str, *, telefonia: bool) -> dict:
    manifiesto = yaml.safe_load((RAIZ_AUDIO / scenario_id / "manifiesto.yaml").read_text())
    asr = SherpaStreamingASR(MODELO)

    resultados = [evaluar_turno(asr, t, telefonia=telefonia) for t in manifiesto["turnos"]]

    def agregar(filtro) -> dict:
        sel = [r for r in resultados if filtro(r)]
        if not sel:
            return {"wer": 0.0, "palabras": 0, "turnos": 0}
        errores = sum(r["sustituciones"] + r["inserciones"] + r["borrados"] for r in sel)
        palabras = sum(r["palabras"] for r in sel)
        return {
            "wer": errores / palabras * 100 if palabras else 0.0,
            "palabras": palabras,
            "turnos": len(sel),
            "rtf_max": max(r["rtf"] for r in sel),
            "retraso_max_ms": max(r["retraso_max_ms"] for r in sel),
        }

    return {
        "scenario_id": scenario_id,
        "telefonia": telefonia,
        "turnos": resultados,
        "global": agregar(lambda r: True),
        "cliente": agregar(lambda r: r["speaker"] == "customer"),
        "ejecutivo": agregar(lambda r: r["speaker"] == "agent"),
    }


def imprimir(res: dict, detalle: bool) -> None:
    canal = "TELEFONÍA 8 kHz µ-law" if res["telefonia"] else "MICRÓFONO 16 kHz"
    print(f"\n{'=' * 78}\n{res['scenario_id']}  ·  {canal}\n{'=' * 78}")

    g, c, e = res["global"], res["cliente"], res["ejecutivo"]
    print(f"  WER global   {g['wer']:6.2f}%   ({g['palabras']} palabras, {g['turnos']} turnos)")
    print(f"  WER cliente  {c['wer']:6.2f}%   ({c['palabras']} palabras)")
    print(f"  WER ejecutivo{e['wer']:6.2f}%   ({e['palabras']} palabras)")
    print(
        f"  RTF máximo   {g['rtf_max']:6.3f}    "
        f"retraso máx. de parcial {g['retraso_max_ms']:.0f} ms"
    )

    if detalle:
        print()
        for t in res["turnos"]:
            marca = "·" if t["wer"] < 10 else "!"
            print(
                f"  {marca} [{t['speaker']:8}] WER {t['wer']:5.1f}%  "
                f"{t['parciales']:2d} parciales · {t['fragmentos']} turnos de ASR"
            )
            if t["wer"] >= 10:
                print(f"      ref: {t['referencia'][:100]}")
                print(f"      hip: {t['hipotesis'][:100]}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Evaluación de ASR sobre los guiones.")
    p.add_argument("--scenario", default="disputa_cargo_no_reconocido")
    p.add_argument("--detalle", action="store_true", help="Muestra turno por turno.")
    p.add_argument("--solo-limpio", action="store_true", help="Omite la pasada de telefonía.")
    args = p.parse_args(argv)

    if not MODELO.exists():
        print("Falta el modelo. Ejecutar `make models`.", file=sys.stderr)
        return 1
    if not (RAIZ_AUDIO / args.scenario).exists():
        print("Falta el audio. Ejecutar `make audio`.", file=sys.stderr)
        return 1

    imprimir(evaluar(args.scenario, telefonia=False), args.detalle)
    if not args.solo_limpio:
        imprimir(evaluar(args.scenario, telefonia=True), args.detalle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
