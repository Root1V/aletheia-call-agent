"""Tests del reconocedor en streaming.

Cada uno protege un defecto real que apareció al construirlo. Todos daban
transcripciones que *parecían* razonables: ninguno lanzaba una excepción ni
dejaba rastro en los logs, y el único síntoma era un WER alto que es fácil
achacar al modelo. Sin estos tests, cualquiera de ellos vuelve sin que nadie
se entere.
"""

from __future__ import annotations

import wave
from pathlib import Path

import pytest
import yaml
from cea_asr import SherpaStreamingASR, calcular_wer, degradar_a_telefonia, pcm16_a_float32
from cea_contracts import Speaker

MODELO = Path("models/sherpa-onnx-streaming-zipformer-es-kroko-2025-08-06")
AUDIO = Path("evals/audio/disputa_cargo_no_reconocido")

pytestmark = [
    pytest.mark.skipif(not MODELO.exists(), reason="Falta el modelo. Ejecutar `make models`."),
    pytest.mark.skipif(
        not (AUDIO / "manifiesto.yaml").exists(),
        reason="Falta el audio guionado. Ejecutar `make audio`.",
    ),
]

TROZO_MS = 100


def _transcribir(asr: SherpaStreamingASR, wav: Path, speaker: Speaker, *, telefonia=False) -> str:
    """Reproduce un wav por el reconocedor y devuelve el texto final completo."""
    with wave.open(str(wav)) as w:
        sr = w.getframerate()
        pcm = w.readframes(w.getnframes())
    if telefonia:
        pcm = degradar_a_telefonia(pcm, sr)
    audio = pcm16_a_float32(pcm)

    asr.open("test", speaker)
    finales: list[str] = []
    paso = int(sr * TROZO_MS / 1000)
    for i in range(0, len(audio), paso):
        for hip in asr.accept("test", speaker, audio[i : i + paso]):
            if hip.is_final:
                finales.append(hip.text)
    for hip in asr.close("test", speaker):
        finales.append(hip.text)
    return " ".join(t for t in finales if t)


@pytest.fixture(scope="module")
def manifiesto() -> dict:
    return yaml.safe_load((AUDIO / "manifiesto.yaml").read_text())


def test_no_se_pierden_las_ultimas_palabras_del_turno(asr, manifiesto) -> None:
    """La cola de silencio del cierre vacía el lookahead del decodificador.

    Sin ella, el final de CADA turno se pierde. Es el defecto más traicionero
    de los cuatro: la transcripción se ve bien, sólo que le faltan las dos o
    tres últimas palabras, y nadie lo nota leyendo por encima.
    """
    incompletos = []
    for turno in manifiesto["turnos"]:
        texto = _transcribir(asr, Path(turno["wav"]), Speaker(turno["speaker"]))
        ultima = turno["texto"].rstrip("?.!¿ ").split()[-1].strip(".,?!¿").lower()
        if ultima not in texto.lower():
            incompletos.append(f"{turno['indice']}: falta {ultima!r} en {texto!r}")

    # Se tolera un turno: la última palabra puede ser una marca en inglés que
    # el modelo transcribe de otro modo. Más de uno indica truncamiento.
    assert len(incompletos) <= 1, "Turnos truncados:\n" + "\n".join(incompletos)


def test_un_turno_hablado_no_se_parte_en_fragmentos(asr, manifiesto) -> None:
    """`rule3_min_utterance_length` es un TOPE, no un mínimo.

    Interpretado al revés, fuerza un corte cada N segundos y trocea las
    palabras por la mitad: "aplica ción", "oche nta". El WER se dispara sin
    que nada falle de forma visible.
    """
    turno = next(t for t in manifiesto["turnos"] if len(t["texto"].split()) > 25)
    with wave.open(turno["wav"]) as w:
        sr = w.getframerate()
        audio = pcm16_a_float32(w.readframes(w.getnframes()))

    speaker = Speaker(turno["speaker"])
    asr.open("frag", speaker)
    fragmentos = 0
    paso = int(sr * TROZO_MS / 1000)
    for i in range(0, len(audio), paso):
        for hip in asr.accept("frag", speaker, audio[i : i + paso]):
            if hip.is_final:
                fragmentos += 1
    list(asr.close("frag", speaker))

    # Una intervención larga puede partirse legítimamente en un par de turnos
    # por las pausas naturales; troceada cada 0.3 s salían diez o más.
    assert fragmentos <= 3, f"el turno se partió en {fragmentos} fragmentos"


def test_el_wer_del_guion_no_se_degrada(asr, manifiesto) -> None:
    """Prueba de regresión sobre el conjunto completo.

    El umbral está por encima del valor medido (5.3%) para absorber variación
    entre versiones del modelo, pero muy por debajo de lo que producía
    cualquiera de los defectos corregidos, que daban entre 8% y 90%.
    """
    errores = palabras = 0
    for turno in manifiesto["turnos"]:
        hip = _transcribir(asr, Path(turno["wav"]), Speaker(turno["speaker"]))
        r = calcular_wer(turno["texto"], hip)
        errores += r.errores
        palabras += r.palabras_referencia

    wer = errores / palabras * 100
    assert wer < 10.0, f"WER {wer:.2f}% sobre el guion completo"


def test_la_telefonia_degrada_pero_sigue_siendo_utilizable(asr, manifiesto) -> None:
    """El audio real llega a 8 kHz con µ-law, no limpio de micrófono.

    Este test existe para que nadie presente un WER medido con micrófono como
    si fuera lo que verá en producción.
    """
    turno = max(manifiesto["turnos"], key=lambda t: len(t["texto"].split()))
    limpio = _transcribir(asr, Path(turno["wav"]), Speaker(turno["speaker"]))
    telefono = _transcribir(asr, Path(turno["wav"]), Speaker(turno["speaker"]), telefonia=True)

    wer_telefono = calcular_wer(turno["texto"], telefono).wer
    assert limpio and telefono
    assert wer_telefono < 25.0, f"WER telefónico {wer_telefono:.1f}%"


def test_cada_hablante_decodifica_por_separado(asr) -> None:
    """El estado vive por (llamada, hablante), no en el reconocedor.

    Si se compartiera, el texto del cliente y el del ejecutivo se mezclarían en
    la misma hipótesis y la separación por track —que es lo que nos ahorra la
    diarización— no serviría de nada.
    """
    asr.open("c1", Speaker.CUSTOMER)
    asr.open("c1", Speaker.AGENT)
    asr.open("c2", Speaker.CUSTOMER)

    claves = set(asr._estados)  # noqa: SLF001 - se comprueba justo el aislamiento
    assert ("c1", Speaker.CUSTOMER) in claves
    assert ("c1", Speaker.AGENT) in claves
    assert ("c2", Speaker.CUSTOMER) in claves

    list(asr.close("c1", Speaker.CUSTOMER))
    assert ("c1", Speaker.AGENT) in asr._estados  # noqa: SLF001
    list(asr.close("c1", Speaker.AGENT))
    list(asr.close("c2", Speaker.CUSTOMER))


def test_cerrar_un_hablante_inexistente_no_revienta(asr) -> None:
    assert list(asr.close("no-existe", Speaker.CUSTOMER)) == []
