# Backlog

El **porqué** de cada cosa pendiente: de qué depende, qué se midió y qué se
decidió. El estado de un vistazo está en [`../ROADMAP.md`](../ROADMAP.md).

Una regla para este documento: **un número sin dónde se midió no entra.** Ya nos
pasó dar una capacidad medida en un portátil cargado como si fuera un
dimensionamiento.

---

## 1 · Bloqueantes

### 1.1 · Sin modelo de texto concedido ⛔

Medido el 25/10 contra el despliegue con `axonium 1.0.0rc11`:

```
GET /v1/models  ->  qwen3-embedding (embedding), qwen3-reranker (rerank)

qwen3-8b-q6        UnknownModelError  — ya no está en el registro
qwen3-0.6b         UnknownModelError
gpt-oss-20b-mxfp4  ForbiddenError     — existe, sin permiso para este token
fara-7b            ForbiddenError
qwen3vl-30b-a3b    ForbiddenError
promptguard2-tei   ForbiddenError
```

Son dos cosas distintas: `qwen3-8b-q6` **desapareció del registro** —no es
permiso— y de los que sí existen, este token no tiene concedido ninguno de
texto.

**Qué cae:** la sugerencia en vivo (Fase 4) y la redacción de la justificación
del caso (Fase 5). **Qué sobrevive:** la recuperación entera —embeddings y
rerank responden— y la clasificación de reclamos, porque las reglas deciden y el
modelo sólo redacta: sin modelo se publica el enunciado de la regla y queda
registrado el motivo. Ese reparto se eligió por trazabilidad regulatoria y hoy
es además lo que sostiene la Fase 5.

**Pedido en `E-10`** del canal con plataforma. No pedimos un modelo concreto:
sus propias medidas dan un factor 13 entre `qwen3-0.6b` y `qwen3-8b-q6`, y esa
elección merece la curva antes que la costumbre.

### 1.2 · Sin audio real ⛔

Sólo existe `FileReplayAdapter`, que reproduce WAV guionados. Es el camino que
sostiene los tests y la evaluación, y no sirve para una llamada de verdad.

Faltan los adaptadores declarados en el plan, todos detrás del mismo
`AudioIngressAdapter`: LiveKit SIP, AudioSocket (Asterisk), mod_audio_fork
(FreeSWITCH) y SIPREC. LiveKit aparece hoy en `docker-compose` y en la
configuración, pero **no hay agente**: el contenedor está y nadie se conecta.

Es el bloqueante del piloto, y no lo arregla más capacidad de inferencia.

### 1.3 · Latencia fuera de presupuesto ○

La sugerencia verificada sale en **1700–2100 ms** contra un presupuesto de
1500 ms. El presupuesto no se mueve: viene de la evidencia sobre cuándo el
ejecutivo deja de confiar en la herramienta.

Lo medido sobre las palancas:

```
prefill por pasaje .......... ~210 ms   (los pasajes cambian en cada
                                         sugerencia: la caché no los cubre)
5 pasajes -> 3 .............. -437 ms   cuesta 1 consulta de 13 en cobertura
reordenador ................. +280 ms   sube el acierto@1 del 54% al 85%
```

**Lo que NO sabemos es la capacidad de la plataforma.** El número que
manejábamos —~36 generaciones/min— se midió en este mismo portátil con el propio
orquestador al 44% de CPU. Plataforma lo repitió mirando la carga: 28–36 gen/min
con la máquina tranquila, 8–14 con carga alta. Factor 4,3, y la variable era el
escritorio. No hay máquina dedicada, así que ese número **no existe todavía**.

---

## 2 · Fases sin construir

### 2.1 · Fase 6 — resumen, tipificación y compromisos (RF-08)

El 54% de las llamadas exige trabajo posterior, unos 3 minutos cada una. El
panel ya está marcado en el portal y el evento `SummaryReady` ya está en los
contratos, sin productor.

Tres cosas a tener en cuenta desde el diseño, no después:

- **No debe compartir bolsa ni modelo con la sugerencia en vivo.** El resumen se
  ejecuta con la llamada colgada: tolera segundos y no tiene presupuesto de
  1,5 s. Si comparte cupo, le roba capacidad al único que sí tiene reloj. Lo
  avisó plataforma en `P-06` y estamos de acuerdo.
- **`logprobs: true`** ya está disponible en el gateway y devuelve la
  probabilidad por token. Sirve para marcar una frase de baja confianza en lugar
  de presentarla igual que el resto. Son logaritmos naturales: `-0,00054` es
  ~99,95%.
- Los compromisos extraídos son afirmaciones sobre lo que el banco hará. Les
  toca el mismo verificador de cifras que a las sugerencias.

### 2.2 · Fase 7 — endurecimiento

| | Estado |
|---|---|
| Redacción de PII/PCI (RF-14) | ✅ hecho |
| Auditoría inmutable (RF-15) | ○ ver §4.1 |
| RBAC | ○ hoy sólo hay autenticación, no autorización por rol |
| Observabilidad (OpenTelemetry) | ○ nada instrumentado |
| Helm | ○ |
| Pruebas de carga | ◐ existe `make carga`, pero compara en vez de dimensionar |
| Evaluaciones en CI | ○ |

`promptguard2-tei` (detección de inyecciones, ~15 ms) existe en la plataforma y
encaja aquí. No está concedido a este token.

---

## 3 · Fuera de alcance, por decisión

No es deuda: se decidió. Lo que importa es que se note al presentar resultados.

### 3.1 · Acciones ejecutables (RF-16)

El 67% de las llamadas exige **ejecutar una tarea**, y es donde está la mayor
parte del ROI de la categoría. Al dejarlo fuera, el sistema ataca los segmentos
del 45% (búsqueda de conocimiento), 54% (trabajo posterior) y 57% (reunir
contexto), pero no el 67%.

**Consecuencia concreta:** el ejecutivo sigue saliendo del portal para actuar, el
"toggle tax" del 20-30% permanece, y **la reducción de AHT que se puede
demostrar está acotada**. Al presentar resultados hay que declarar ese techo en
lugar de proyectar el ROI completo de la categoría.

Hoy se nota en dos sitios del producto: el caso se prepara como borrador con
folio provisional y no se registra, y la política del copiloto se calla ante los
cierres de cortesía porque ahí el modelo inventaba un folio que no existe.

### 3.2 · Flujo de venta (RF-17)

Propensión (GBM), motor de elegibilidad **determinista** —jamás un LLM
decidiendo elegibilidad—, valor esperado y bandit contextual. Con una regla que
es el diferenciador: **suprimir la venta cruzada cuando la emoción del cliente
está caliente o hay un reclamo activo.** Vender un seguro a quien acaba de
gritar por un cobro indebido es la forma más rápida de perderlo.

### 3.3 · Flujo de servicing (RF-18)

Acciones de mantenimiento y RAG sobre procedimientos operativos.

### 3.4 · Identidad y fraude reales

Hoy la barra de confianza es **simulada**. La biometría de voz pasiva es un
proyecto en sí mismo, y la práctica correcta es tratarla como **una señal de
riesgo entre varias** —junto a detección de habla sintética y de vivacidad—
nunca como contraseña: el 91% de los bancos de EE. UU. está reconsiderándola por
el riesgo de clonación con IA.

### 3.5 · Vulnerabilidad inferida

Hoy sólo la **declarada**, y por elección. Inferirla exige consentimiento,
revisión humana y **prohibición explícita de usarla para precios u ofertas**:
sólo para adaptar el trato.

### 3.6 · Diarización en streaming

Sólo hace falta cuando llegue audio mono por SIPREC. Mientras la telefonía
entregue canales separados, la separación de hablantes es gratuita y perfecta, y
diarizar sería añadir la pieza más frágil del sistema sin necesidad.

### 3.7 · Coaching y auto-QA sobre el 100% de llamadas

Evaluar al ejecutivo con IA exige acuerdo previo con RR.HH. y transparencia
total hacia él. Relacionado: **no se mide la emoción del ejecutivo**, y esa
restricción vive en el tipo (`EmotionFrame.speaker` es un `Literal` fijado a
`CUSTOMER`), no en una opción que alguien pueda invertir por descuido.

---

## 4 · Deuda declarada

### 4.1 · El registro de eventos no se persiste

`call_events`, `emotion_timeline` y `audit_log` existen como tablas en la
migración y **nadie escribe en ellas**. Los eventos viven sólo en Redis, con un
TTL de 6 horas.

Importa por tres cosas que el proyecto afirma:

- **"Event-sourced"** es cierto a medias: los eventos son el contrato y la
  llamada se reproduce, pero sólo dentro de esas 6 horas.
- **La auditoría (RF-15)** no existe de forma duradera. El evento
  `suggestion.feedback` —qué hizo el ejecutivo con cada sugerencia— se publica y
  se pierde. Es la señal de calidad más valiosa del sistema y la única que no se
  puede reconstruir después.
- Las **evaluaciones deterministas sobre tráfico real** dependen de poder
  reproducir una llamada pasada.

### 4.2 · Eventos contratados sin productor

Declarados en `packages/contracts` y nunca publicados: `EscalationAlert`
(RF-02b), `NluTurn`, `RiskSignal`, `SummaryReady` (Fase 6), `IntentPredicted`
—este último porque la predicción viaja dentro de `ContextEnriched`—.

`RiskSignal` merece mención aparte: las señales de riesgo textuales —mención de
la SBS, de Indecopi, del Libro de Reclamaciones, de un abogado— **sí** están
implementadas, pero dentro de `cea_reclamos.senales` y sólo se evalúan al
colgar. En vivo nadie avisa al ejecutivo de que el cliente acaba de nombrar a la
SBS, que es justo cuando serviría.

### 4.3 · Números calibrados contra una base de trece trozos

`PASAJES = 3` en el copiloto y `PROFUNDIDAD = 10` en el reordenador se eligieron
midiendo contra una base de conocimiento de **13 trozos**. Con esa base, RRF casi
siempre mete el pasaje correcto entre los tres primeros; en una base bancaria de
miles aparecerá con frecuencia en el puesto diez o quince.

**Hay que volver a medirlos contra la base real del banco antes de fijarlos.**

### 4.4 · Días hábiles sin feriados peruanos

El plazo de la Ley 31763 se cuenta sobre el calendario local saltando fines de
semana, pero **no contempla los feriados**, que se publican por decreto y cambian
cada año. El plazo calculado sale igual o más corto que el real, que es el lado
seguro del error, pero es incorrecto.

### 4.5 · Emoción incompleta

El motor sostiene **activación** —y de ahí frustración y urgencia— a partir de
prosodia e interrupciones. **No sostiene valencia, satisfacción ni confusión**:
la prosodia sola no distingue alegría de enfado, porque ambas suenan con energía
y tono altos. Esas dimensiones se devuelven **ausentes, no en cero**.

Falta elegir un modelo acústico validado para español. Las opciones en abierto
son subidas comunitarias sin verificar, y meter una en un banco sin verificar su
procedencia es el tipo de atajo que luego no se puede defender.

### 4.6 · El apaño del `/no_think`

Para apagar el razonamiento usamos un sufijo `/no_think` en el mensaje del
usuario (Qwen3) y un `Reasoning: minimal` de sistema (gpt-oss). La plataforma
ofrece ahora la vía soportada:

```json
{ "chat_template_kwargs": { "enable_thinking": false } }   // qwen3
{ "chat_template_kwargs": { "reasoning_effort": "low" } }  // gpt-oss
```

Medido por ellos: 215 → 16 tokens en qwen3. Es mejor que nuestro apaño, que
además ensucia el prompt que la caché de prefijo indexa. **No se ha migrado
porque sin modelo de texto no se puede verificar**, y cambiar a ciegas un
mecanismo que funciona es peor que esperar.

### 4.7 · Las voces del guion no son peruanas

El WER de **5,31%** lleva esa advertencia: macOS no trae voz peruana y las voces
disponibles son de España y México.

---

## 5 · Evaluación incompleta

### 5.1 · Tres de cinco escenarios no tienen guion ni audio

```
disputa_cargo_no_reconocido    guion ✅  audio ✅
disputa_fraude                 guion ✅  audio ✅
disputa_cobro_duplicado        guion ✖   audio ✖
tarjeta_rechazada              guion ✖   audio ✖
seguimiento_reclamo_por_vencer guion ✖   audio ✖
```

Los tres existen en la bandeja, tienen pre-pop y traen su verdad de referencia en
`demo_scenarios`, pero **nunca se han reproducido como llamada**.

`seguimiento_reclamo_por_vencer` es el único que ejercita el reloj de SLA de la
Fase 5, así que ahora mismo esa fase está probada contra la mitad de los casos
que dice cubrir.

El plan pedía un golden set de **30-50** llamadas. Hay 2.

### 5.2 · Métricas sin medir

- **Emoción:** correlación de concordancia (CCC) sobre valencia y activación, y
  **evaluación de sesgo por género, edad y región**. El reconocimiento de
  emociones tiene sesgos documentados por acento y tono, y en un banco eso es
  riesgo reputacional.
- **RAG:** *groundedness* y *faithfulness* (Ragas). Hoy se mide acierto@1 y
  cobertura, que es recuperación y no fidelidad de la respuesta.
- **Sugerencias:** tasa de aceptación del ejecutivo y distancia de edición. El
  evento `suggestion.feedback` ya se publica; falta persistirlo (§4.1) y el
  informe.
- **Clasificación:** matriz de confusión, tratando el falso "requerimiento" como
  error crítico.
- **Negocio:** AHT, FCR, NPS y tasa de escalamiento, declarando el techo de §3.1.

---

## 6 · Documentación que el plan pedía

`docs/architecture.md`, `docs/LICENSES.md`, `docs/DATA_GOVERNANCE.md` y los ADR
en `docs/adr/`, que está vacío.

De los cuatro, **`LICENSES.md` es el que tiene consecuencia**: el repositorio es
público bajo Apache-2.0 y `make models` descarga modelos con licencias distintas
de la del proyecto. El riesgo grande ya está cubierto en código —el registro de
`services/asr/models.py` muestra la licencia de cada modelo al descargarlo,
incluida la advertencia de que el único modelo de streaming en español del
catálogo de sherpa-onnx es **CC-BY-SA**— pero falta la auditoría escrita.

---

## 7 · Abierto con otros equipos

El canal compartido es
`~/Documents/Victor/prometheus_copiloto_axonium/canal-copiloto-ejecutivo.md`.

| | |
|---|---|
| `E-10` | **Pedimos un modelo de texto concedido.** Es el bloqueante 1.1. |
| `E-11` | Contestado a `P-06`: el modelo era `qwen3-8b-q6`, y nuestros 1106 ms eran una sola muestra y no un p50. |
| `P-06` | Plataforma pide decidir qué modelo, para rehacer la curva contra ése. |

Pendiente de nuestro lado cuando haya modelo: migrar el `/no_think` (§4.6) y
rehacer la curva de latencia por número de pasajes contra el modelo nuevo.

---

## 8 · Higiene

- **Rotar el `AXONIUM_CLIENT_SECRET`**: se compartió por chat. No está en el
  repositorio ni en el historial de git —auditado— pero sigue en esa
  conversación.
- Renombrar el directorio local, que todavía se llama `customer_executiv
  _assistant`, con espacio y con la errata.
