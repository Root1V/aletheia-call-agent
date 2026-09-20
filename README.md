# Aletheia

> *ἀλήθεια* — lo que deja de estar oculto.

El caso insignia de este proyecto es un cargo que el cliente mira en su estado
de cuenta, no reconoce, y está a punto de disputar. Dice **SUNRISE TECH**. Es
**inDrive**, un viaje suyo al aeropuerto, desde su propio teléfono, el sexto en
noventa días. No hacía falta investigar nada: hacía falta dejar de ocultarlo.

Asistente en tiempo real para ejecutivos de atención telefónica de un banco.
Todo el stack es **open source y auto-hospedable**: no hay ningún servicio
gestionado en el camino crítico.

**Perímetro:** Perú (SBS / Indecopi), es-PE · **Flujo profundo:** reclamos y
disputas · **Licencia:** Apache-2.0

---

## Qué resuelve

Un ejecutivo atiende con el CRM en una pestaña, el core en otra, el tarifario en
un PDF y la campaña en un Excel. La investigación del sector es concreta sobre
lo que eso cuesta:

| Necesidad de una llamada | % de llamadas |
|---|---|
| Ejecutar una tarea por el cliente | 67% |
| Reunir contexto de la interacción | 57% |
| Trabajo post-llamada (~3 min cada una) | 54% |
| Buscar una respuesta durante la conversación | 45% |

A eso se suma un **20-30% del tiempo perdido sólo cambiando de aplicación**.

La conclusión que ordena el diseño: **un panel "360" que lo muestra todo,
siempre, es el paradigma CRM antiguo.** Lo que hace falta no es más
información, es el contexto de *esta* llamada, ordenado por probabilidad de ser
lo que el cliente va a pedir, con el resto a un clic.

### La palanca del flujo de reclamos

El **61% de las disputas se abren porque el cliente no reconoce un cargo** — no
por fraude — y esas generan más insatisfacción (29%) que las de fraude real
(12%). Traducir el descriptor crudo resuelve buena parte sin abrir un caso:

```
"DLO*RAPPI PE 5511234567"
  → Rappi · Delivery · Miraflores
  → 03/09 14:32 · app · iPhone de Juan · S/ 42.50 · liquidada
  → 5 compras previas en los últimos 90 días
```

---

## Arranque

Requisitos: Docker, [uv](https://docs.astral.sh/uv/), Node 20+.

```bash
make up        # Postgres+pgvector, Redis, MinIO, LiveKit
make migrate   # esquema
make seed      # dataset sintético es-PE, reproducible por semilla
make admin USER=carlos NAME="Carlos Ruiz"   # primer usuario; imprime la contraseña
make models    # modelos de voz (muestra la licencia de cada uno)
make audio     # renderiza los guiones a audio con `say` (macOS)
make kb        # indexa la base de conocimiento (requiere credenciales de la plataforma)
make dev       # API en :8000, portal en :5180 y copiloto
```

Abrir <http://localhost:5180> e iniciar sesión. La bandeja muestra cinco
escenarios guionados.

### Ver la transcripción en vivo

Con el portal abierto en una llamada, en otra terminal:

```bash
make replay
```

Reproduce el guion respetando su cronología —silencios incluidos, porque la
detección de fin de turno es exactamente eso— y la transcripción va apareciendo
en el panel. Los turnos aún abiertos se pintan en cursiva y atenuados: el texto
parcial todavía puede cambiar, y un ejecutivo que lea en voz alta una hipótesis
no consolidada le está diciendo al cliente algo que el sistema aún no afirma.

> Los puertos se configuran en `infra/.env`. Redis sale por el **6380** porque
> el 6379 suele estar ocupado por otro servicio en la máquina de desarrollo.
> Keycloak está en el perfil `sso` y no arranca por defecto.

### Acceso

No hay registro público: las altas son una acción administrativa y el primer
usuario sale de `scripts/create_admin.py`. En una herramienta interna no existe
caso de uso para el auto-registro, y quitarlo elimina la enumeración de cuentas,
la confirmación por correo y la recuperación abierta como superficies de ataque.

Tres decisiones de seguridad, las tres con test:

- **Contra un usuario inexistente se verifica igual la contraseña**, contra un
  hash señuelo. Sin eso la respuesta vuelve en microsegundos frente a los
  ~200 ms de bcrypt, y esa diferencia basta para enumerar cuentas cronometrando.
- **Usuario inexistente, contraseña incorrecta y cuenta desactivada devuelven el
  mismo error.** Distinguirlos convierte el login en un directorio de cuentas.
- **La API se niega a arrancar** si el entorno no es `dev` y el secreto de firma
  sigue siendo el de desarrollo. Una advertencia en el log de arranque es
  justamente lo que nadie lee cuando el despliegue "funcionó".

La autenticación vive detrás de un protocolo con dos implementaciones: `local`
(JWT propio, la actual) y `oidc` (Keycloak, para cuando el banco integre su SSO).
El resto de la aplicación depende de `AgentIdentity`, no de cómo se obtuvo.

---

## Estado

Lo construido y lo pendiente, sin ambigüedad. El portal marca cada zona no
construida con su fase en lugar de rellenarla con datos simulados: en una demo
para un comité, una transcripción falsa indistinguible de una real es la forma
más rápida de perder la confianza.

| Fase | Alcance | Estado |
|---|---|---|
| 0 | Monorepo, contratos, infraestructura, datos sintéticos | ✅ |
| — | Autenticación, portal con sidebar, tema claro/oscuro | ✅ |
| 2 | Contexto de llamada, enriquecimiento, predicción de intención | ✅ |
| 1 | Transcripción en vivo (ASR en streaming + bus + WebSocket) | ✅ parcial |
| 3 | Emoción del cliente en tiempo real | ✅ parcial |
| 4 | RAG y sugerencia generativa con citación obligatoria | ✅ |
| 5 | Clasificación reclamo/requerimiento (Ley 31763) | ✅ |
| 6 | Resumen y tipificación post-llamada | pendiente |
| 7 | Endurecimiento: PII, auditoría, RBAC, observabilidad | ✅ parcial (PII) |

La Fase 1 está completa por el camino de reproducción (`FileReplayAdapter`), que
es el que sostiene los tests y la evaluación. Falta el adaptador de LiveKit para
audio de micrófono en vivo; el pipeline no cambia, sólo la fuente de las tramas.

### La sugerencia, medida

`make eval-rag` evalúa la recuperación con trece consultas escritas **como habla
un cliente por teléfono**, no como está redactado el documento. Esa distancia es
el problema real: el tarifario dice "comisión por disposición de efectivo" y el
cliente dice "sacar plata del cajero". Un conjunto construido parafraseando el
propio documento mide lo fácil y sale siempre bien.

| | acierto@1 | cobertura@5 | coste |
|---|---|---|---|
| RRF solo (léxica + densa) | 54% | 92% | 3 ms |
| RRF + `qwen3-reranker` | **85%** | **100%** | +278 ms |

El acierto en primera posición es lo que importa: con cinco pasajes en el
prompt, el que encabeza es el que el modelo cita. El reordenador cuesta ~26 ms
por pasaje, de forma lineal y estable entre 3 y 39 documentos.

Cuatro cosas que conviene declarar en vez de esconderlas en el p50:

**El primer token es caro, y una medición anterior decía lo contrario.**
Repitiendo el MISMO prompt el primer token sale a 100 ms, y sobre eso llegué a
escribir aquí que la latencia era plana con el número de pasajes. Era falso: lo
que medía era la caché de prefijo del despliegue. Con el prompt real, en el que
los pasajes cambian en cada sugerencia:

| Qué cambia entre sugerencias | primer token |
|---|---|
| nada (caché completa) | 136 ms |
| sólo el turno del cliente, al final | 187 ms |
| **los pasajes — el caso real** | **1502 ms** |
| el contexto de la llamada, al principio | 3850 ms |

De ahí que el orden del prompt no sea cosmético: lo estable —sistema y datos de
la llamada— va primero y lo volátil al final, para que la caché cubra todo lo
que pueda. Cada pasaje añade ~210 ms de prefill, así que el número de pasajes es
una palanca de latencia real (1 pasaje 325 ms · 3 pasajes 729 ms · 5 pasajes
1166 ms). Se mantienen cinco porque con el reordenador la cobertura sube al 100%,
y un pasaje que falta no da una respuesta mala sino ninguna.

**La tarjeta no se pinta hasta el final**, aunque el primer token llegue antes.
La verificación de cifras se hace sobre el texto completo, y una comisión
equivocada que parpadea medio segundo en pantalla ya se la puede haber leído el
ejecutivo al cliente: entonces el guardarraíl no sirvió de nada. Se gana latencia
percibida anunciando la tarjeta —`suggestion.started` sale antes de recuperar
nada—, no arriesgando el número.

**En una sola máquina, el reconocimiento de voz y el modelo se pelean por la
CPU.** Sin carga el primer token es estable; con una llamada transcribiéndose en
paralelo en la misma Mac, dos de cada cinco generaciones saltan a 1100-1900 ms.
sherpa-onnx transcribiendo dos hablantes en tiempo real y el servidor de
inferencia comparten los mismos núcleos. En un despliegue real van en hosts
distintos y el modelo en GPU, así que **el número de esta máquina no se puede
presentar como el de producción, ni bueno ni malo**.

**Hoy la sugerencia verificada sale en 1700-2100 ms, por encima del presupuesto
de 1500 ms.** No se ajusta el presupuesto para que cuadre: el 1.5 s viene de la
evidencia sobre cuándo el ejecutivo deja de confiar en la herramienta, no de lo
que esta máquina consigue. Las palancas medidas son el número de pasajes, la
profundidad del reordenador y separar el ASR del modelo.

**Acciones ejecutables (RF-16) están fuera del alcance actual, por decisión.**
Conviene tenerlo presente al medir: el sistema ataca los segmentos del 45%, 54%
y 57%, pero no el 67%. El ejecutivo seguirá saliendo del portal para actuar, así
que la reducción de AHT demostrable está acotada y no debe proyectarse el ROI
completo de la categoría.

---

## Decisiones de diseño

**La emoción se mide sólo del cliente, nunca del ejecutivo.** La restricción
vive en el tipo (`EmotionFrame.speaker` es un `Literal` fijado a `CUSTOMER`),
no en una opción de configuración que alguien pueda invertir por descuido.
El EU AI Act lo prohíbe en el ámbito laboral, pero en Perú esa prohibición no
aplica: se mantiene porque medir emocionalmente a los empleados envenena la
relación laboral, convierte al copiloto en herramienta de vigilancia a ojos del
ejecutivo —que entonces lo sabotea— y cierra la puerta a exportar el producto.

**El LLM decide cómo decirlo, nunca qué es verdad ni qué se le puede vender a
quién.** La elegibilidad es un motor de reglas determinista; las cifras citables
viven en una tabla estructurada (`kb_facts`) contra la que se verifica toda tasa
o comisión que el modelo emita. Ese control, y no el prompt, es lo que evita el
incidente regulatorio.

**El copiloto se calla más de lo que habla.** Sugiere sólo ante un turno del
cliente de al menos cinco palabras, con seis segundos de enfriamiento entre
tarjetas, y un turno nuevo cancela la generación anterior en vuelo. No es para
ahorrar en el modelo: es porque una tarjeta nueva mientras el ejecutivo lee la
anterior hace que deje de leerlas, y la sobrecarga cognitiva —no la calidad del
modelo— es la causa número uno de abandono de estas herramientas. Cuando el
copiloto no sugiere, el log dice por qué: "no sugirió" sin causa es
indistinguible de un fallo.

**Las reglas clasifican, el modelo sólo redacta el porqué.** Clasificar un
reclamo como requerimiento priva al usuario del plazo de quince días hábiles y
de la vía de escalamiento a la SBS: es un incumplimiento, y tiene que poder
explicarse ante un auditor con la regla que se aplicó. La regla que gobierna
está en el procedimiento del banco: *ante la duda se registra como reclamo*. La
justificación que escribe el modelo no puede contradecir el veredicto ni inventar
cifras; si lo hace se conserva el enunciado de la regla y el descarte queda
registrado.

Y las señales salen sólo de los turnos del CLIENTE. Si el clasificador se apoyara
en lo que dice el ejecutivo —"vamos a registrar un reclamo formal"— no haría más
que repetirle lo que acaba de decidir, y sería ciego al único caso que importa:
que NO lo registre.

**El copiloto no sugiere sobre un cierre de cortesía.** Es donde el modelo
confabula. Ante "De acuerdo, gracias por la ayuda" escribió tres veces de tres
*«le informo que se ha generado el folio correspondiente para atender su
reclamo»*: no existe tal folio, y el ejecutivo se lo habría dicho al cliente. Los
guardarraíles lo bloquearon las tres veces, pero el arreglo correcto es no
pedirlo — un modelo sin material contesta igual, y lo que inventa cuando no tiene
nada que decir es justo lo que más daño hace.

**Una cita tiene que respaldar la frase, no acompañarla.** Citar el primer
pasaje recuperado es lo cómodo, y produce referencias falsas: en el flujo de
reclamos la mayoría de las frases se construyen enteras con los datos de la
llamada —el comercio real, la fecha, las compras previas— y no deben nada a
ningún documento. Se cita sólo el pasaje que aportó términos que la frase no
podía sacar del contexto de la llamada; cuando no hay ninguno, la tarjeta dice
"según los datos de esta llamada, sin respaldo en la base de conocimiento". Es
el ejecutivo quien responde si el cliente pregunta de dónde sale el dato.

**Una sugerencia bloqueada se muestra igual, con su motivo.** Un hueco en
blanco es indistinguible de un fallo y deja al ejecutivo esperando. Decir "me
callé porque sólo pude respaldar el 40% de lo que iba a decir" mantiene la
confianza; callarse en silencio la destruye.

**La evidencia exacta manda sobre la circunstancial.** Dos cargos del mismo
monto en el mismo comercio con minutos de diferencia no son indicio de
duplicado: son un duplicado. Dejar que la suma de tres corazonadas tumbe un
hecho comprobado es un error de diseño, no de ajuste.

**Los números dictados en voz alta son el caso que rompe la redacción estándar.**
Nadie deletrea su DNI: lo dice. El reconocedor transcribe "cuatro, cinco, seis,
siete, ocho, nueve, uno, dos", y cualquier detector de PII de biblioteca
—Presidio, una expresión regular, un NER— busca ocho dígitos seguidos y no
encuentra nada. No falla ni avisa: informa cero coincidencias mientras el número
queda en claro en la base. Por eso `services/redaction` normaliza las secuencias
habladas antes de aplicar los detectores, y retiene los parciales mientras hay
un dictado en curso: publicarlos cifra a cifra filtraría el número completo
antes de que ningún patrón pudiera reconocerlo.

Todo esto ocurre **antes** de publicar al bus. Una vez que el número entra a la
base de datos o al historial de un proveedor de modelos, tacharlo después no lo
des-publica.

**La emoción se mide sólo donde hay evidencia.** El motor actual usa la señal
prosódica —energía, tono y ritmo comparados con la línea base del propio
hablante— más las interrupciones. Eso sostiene **activación**, y de ahí
frustración y urgencia.

No sostiene **valencia**, **satisfacción** ni **confusión**: la prosodia sola no
distingue alegría de enfado, porque ambas suenan con energía y tono altos. Esas
dimensiones se devuelven **ausentes, no en cero** — un cero se lee como
"neutral", y "no lo sé" no es "neutral". El panel las muestra como pendientes de
un modelo acústico validado para español, que todavía no hemos elegido: las
opciones disponibles en abierto son subidas comunitarias sin verificar.

La normalización contra la propia voz del cliente es lo que hace que la señal
signifique algo. La energía absoluta depende de la ganancia de la línea: sin
esa referencia, una persona de voz fuerte mediría siempre "muy activada".

**El reconocimiento se mide, no se promete.** `make eval-asr` corre el guion
completo y reporta WER por hablante, siempre también sobre audio degradado a
8 kHz µ-law. La telefonía real no entrega micrófono limpio, y medir sólo con
audio bueno produce un número que se ve bien en una presentación y no se parece
a producción. Sobre el guion actual: **5.31%**, con la advertencia de que macOS
no trae voz peruana y las voces disponibles son de España y México.

**Los pesos de los modelos no se versionan.** `make models` los descarga y
muestra la licencia de cada uno. Además del tamaño, cada modelo trae términos
distintos de la Apache-2.0 del proyecto: descargándolos, el código conserva su
licencia y el modelo la suya. Conviene saber que el único modelo de streaming en
español del catálogo de sherpa-onnx es CC-BY-SA; la alternativa de licencia
limpia (NeMo, CC-BY-4.0) está declarada en el registro y no hace streaming.

**La latencia es el requisito no funcional número uno.** Si la sugerencia llega
después de que el ejecutivo ya respondió, el sistema pierde la confianza en una
semana. Objetivos: transcripción visible **<700 ms**, sugerencia **<1.5 s**. El
portal muestra el tiempo de armado del contexto en la barra superior.

**Todo se almacena en UTC y se muestra en America/Lima.** Mezclarlo hace que un
consumo de las 20:25 aparezca como "01:25 del día siguiente", y los 15 días
hábiles de la Ley 31763 se cuentan sobre el calendario local.

---

## Stack

**Backend** — FastAPI · SQL plano con migraciones numeradas · PostgreSQL 17 +
pgvector · python-jose + passlib[bcrypt] · pydantic-settings · uv.

**Voz e inferencia** — sherpa-onnx (ASR en streaming) · `axonium` para los
modelos de la plataforma Prometheus (chat, embeddings y `rerank`), detrás de un protocolo propio para que el
copiloto, la clasificación de reclamos y el resumen no conozcan al proveedor.

**Frontend** — React 19 + Vite · TypeScript · Tailwind CSS v4 con el patrón
shadcn/ui (paleta en variables CSS) · @tanstack/react-query · react-router-dom ·
axios con interceptors · lucide-react · ESLint 9 flat config.

La paleta está centralizada en `src/index.css`: un solo lugar para el modo
oscuro y para un rebranding. Cuando llegue el canvas de las barras de emoción,
leerá esas mismas variables en vez de traer los colores escritos a mano.

## Estructura

```
apps/
  api/                 FastAPI: autenticación, contexto, datos del portal, WebSocket
  agent-worker/        pipeline de la llamada: ingesta → reconocimiento → bus
  web/                 React + TS: portal del ejecutivo
    src/components/ui/   primitivos (patrón shadcn)
    src/features/        auth, tema, paneles de la llamada
    src/pages/           una por ruta
packages/
  contracts/           esquemas de eventos y dominio (fuente de verdad)
  synthetic-data/      generador y escenarios es-PE
  eventbus/            bus de la llamada sobre Redis Streams
services/
  asr/                 reconocimiento en streaming y sus métricas
  emotion/             estado emocional a partir de prosodia y conversación
  redaction/           redacción de PII, incluidos números dictados en voz alta
  llm-gateway/         acceso a modelos vía el SDK de Axonium
  rag/                 base de conocimiento: troceado, búsqueda híbrida, cifras citables
  copilot/             la frase que se dice en voz alta: prompt, tono y guardarraíles
  reclamos/            Ley 31763: reglas de clasificación, plazo y justificación
  orchestrator/        qué sugerir y cuándo, sobre la llamada en vivo
evals/
  scenarios/           guiones reproducibles
  runners/             evaluación de WER y latencia
scripts/
  create_admin.py      alta de usuarios: el único camino
infra/
  docker-compose.yml   infraestructura local
  migrations/          esquema en SQL plano, revisable sin ejecutar Python
```

`packages/contracts` es la única dependencia común: es lo que permite
reemplazar cualquier modelo sin tocar la UI y reproducir una llamada completa
desde su log de eventos para evaluaciones deterministas.

---

## Desarrollo

```bash
make test     # suite completa
make eval-rag # recuperación, con y sin reordenador
make lint     # ruff + tsc
make fmt      # formatea
make reset    # recrea la base desde cero
```

Los tests de la API corren **contra Postgres real, no contra mocks**. Ninguno de
los defectos encontrados durante la construcción —el foco que apuntaba al
reintento rechazado en vez del cargo cobrado, los intentos del defraudador
contados como compras previas del cliente— habría aparecido con un motor de base
de datos simulado.
