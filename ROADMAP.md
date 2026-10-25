# Roadmap

Estado de cada pieza, de un vistazo. El **porqué** de lo pendiente, lo que se
midió y de qué depende está en [`docs/BACKLOG.md`](docs/BACKLOG.md).

| | |
|---|---|
| ✅ | hecho y verificado contra infraestructura real |
| ◐ | parcial — funciona por un camino, no por todos |
| ⛔ | bloqueado por algo que no depende de este repositorio |
| ○ | pendiente |
| ✖ | fuera de alcance, por decisión |

---

## Bloqueantes de hoy

| | Qué pasa |
|---|---|
| ⛔ **Modelo de texto** | El token no tiene concedido ninguno. `qwen3-8b-q6` desapareció del registro de la plataforma. Sin él no hay generación: caen la sugerencia en vivo y la redacción de la justificación. Pedido en `E-10` del canal. |
| ⛔ **Audio real** | Sólo existe `FileReplayAdapter`. Sin adaptador de telefonía (LiveKit SIP, AudioSocket, mod_audio_fork, SIPREC) no hay piloto posible. |
| ○ **Latencia** | La sugerencia verificada sale en 1700–2100 ms contra un presupuesto de 1500 ms. |

---

## Fases

| Fase | Alcance | Estado |
|---|---|---|
| 0 | Monorepo, contratos, infraestructura, datos sintéticos es-PE | ✅ |
| — | Autenticación, portal, tema claro/oscuro | ✅ |
| 1 | Transcripción en vivo: ASR en streaming, bus, WebSocket | ◐ sólo por reproducción de fichero |
| 2 | Contexto de llamada, enriquecimiento, predicción de intención | ✅ |
| 3 | Emoción del cliente en tiempo real | ◐ sólo activación; sin alerta de escalamiento |
| 4 | RAG híbrido y sugerencia con citación obligatoria | ✅ (⛔ sin modelo) |
| 5 | Clasificación reclamo/requerimiento (Ley 31763) | ✅ (◐ sin modelo redacta la regla) |
| 6 | Resumen, tipificación y compromisos post-llamada | ○ |
| 7 | Endurecimiento: PII, auditoría, RBAC, observabilidad | ◐ sólo PII |

---

## Requerimientos funcionales

El origen de cada uno —qué evidencia lo justifica— está en el plan y se resume
en [`docs/BACKLOG.md`](docs/BACKLOG.md).

| ID | Requerimiento | Estado |
|---|---|---|
| RF-01 | Transcripción bilateral con separación de hablantes | ✅ |
| RF-02 | Emoción del cliente en barras en tiempo real | ◐ |
| RF-02b | Alerta de escalamiento por umbral sostenido | ○ |
| RF-03 | Sugerencia adaptada al estado emocional, con cita obligatoria | ✅ |
| RF-04 | Búsqueda de conocimiento en vivo | ✅ |
| RF-05 | Panel de transacciones enriquecidas | ✅ |
| RF-06 | Contexto del journey digital | ✅ |
| RF-07 | Predicción de intención y reconfiguración del workspace | ✅ |
| RF-08 | Resumen, tipificación y compromisos post-llamada | ○ |
| RF-09 | Clasificador reclamo vs. requerimiento con justificación | ✅ |
| RF-10 | Reloj de SLA regulatorio sobre casos abiertos | ✅ |
| RF-11 | Barra de identidad y confianza | ◐ simulada |
| RF-12 | Indicadores de vulnerabilidad | ◐ sólo declarada |
| RF-13 | 360 completo bajo demanda | ✅ |
| RF-14 | Redacción de PII/PCI antes de persistir y antes del prompt | ✅ |
| RF-15 | Auditoría de qué sugirió la IA y qué aceptó el ejecutivo | ◐ al bus, sin persistencia |
| RF-16 | Acciones ejecutables embebidas | ✖ |
| RF-17 | Motor de propensión y siguiente-mejor-oferta | ✖ |
| RF-18 | Flujo de servicing | ✖ |

---

## Calidad y evaluación

| | Estado |
|---|---|
| Golden set de llamadas guionadas | ◐ 2 de 5 escenarios tienen guion y audio |
| WER del reconocimiento, limpio y a 8 kHz | ✅ `make eval-asr` |
| Recuperación: acierto@1 y cobertura | ✅ `make eval-rag` |
| Carga del copiloto con N ejecutivos | ✅ `make carga` (compara, no dimensiona) |
| Emoción: correlación de concordancia (CCC) | ○ |
| Emoción: sesgo por género, edad y región | ○ |
| RAG: *groundedness* y *faithfulness* | ○ |
| Sugerencias: tasa de aceptación del ejecutivo | ○ el evento existe, falta el informe |
| Clasificación: matriz de confusión | ○ |
| Evaluaciones en CI | ○ |

---

## Fuera de alcance, por decisión

Lo que sigue **no** es deuda: se decidió dejarlo fuera y conviene que se note al
medir resultados. El detalle y el coste de cada uno, en `docs/BACKLOG.md`.

| | Por qué importa que falte |
|---|---|
| ✖ Acciones ejecutables (RF-16) | El 67% de las llamadas exige ejecutar una tarea. Es el techo de la reducción de AHT que este sistema puede demostrar. |
| ✖ Flujo de venta (RF-17) | |
| ✖ Flujo de servicing (RF-18) | |
| ✖ Biometría de voz y detección de voz sintética | Hoy la barra de confianza es simulada. |
| ✖ Vulnerabilidad inferida | Hoy sólo la declarada, y por elección. |
| ✖ Diarización en streaming | Sólo hace falta si llega audio mono por SIPREC. |
| ✖ Coaching y auto-QA sobre el 100% de llamadas | Exige acuerdo previo con RR.HH. |
