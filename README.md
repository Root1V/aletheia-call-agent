# Copiloto de Atención al Cliente Bancario

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
make dev       # API en :8000 y portal en :5180
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
| 4 | RAG y sugerencia generativa con citación obligatoria | pendiente |
| 5 | Clasificación reclamo/requerimiento (Ley 31763) | pendiente |
| 6 | Resumen y tipificación post-llamada | pendiente |
| 7 | Endurecimiento: PII, auditoría, RBAC, observabilidad | ✅ parcial (PII) |

La Fase 1 está completa por el camino de reproducción (`FileReplayAdapter`), que
es el que sostiene los tests y la evaluación. Falta el adaptador de LiveKit para
audio de micrófono en vivo; el pipeline no cambia, sólo la fuente de las tramas.

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
modelos de la plataforma Prometheus, detrás de un protocolo propio para que el
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
make lint     # ruff + tsc
make fmt      # formatea
make reset    # recrea la base desde cero
```

Los tests de la API corren **contra Postgres real, no contra mocks**. Ninguno de
los defectos encontrados durante la construcción —el foco que apuntaba al
reintento rechazado en vez del cargo cobrado, los intentos del defraudador
contados como compras previas del cliente— habría aparecido con un motor de base
de datos simulado.
