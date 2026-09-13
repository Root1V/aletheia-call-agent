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
make up        # Postgres+pgvector, Redis, MinIO, Keycloak, LiveKit
make migrate   # esquema
make seed      # dataset sintético es-PE, reproducible por semilla
make dev       # API en :8000 y portal en :5180
```

Abrir <http://localhost:5180>. La bandeja muestra cinco escenarios guionados.

> Los puertos se configuran en `infra/.env`. Redis sale por el **6380** porque
> el 6379 suele estar ocupado por otro servicio en la máquina de desarrollo.

---

## Estado

Lo construido y lo pendiente, sin ambigüedad. El portal marca cada zona no
construida con su fase en lugar de rellenarla con datos simulados: en una demo
para un comité, una transcripción falsa indistinguible de una real es la forma
más rápida de perder la confianza.

| Fase | Alcance | Estado |
|---|---|---|
| 0 | Monorepo, contratos, infraestructura, datos sintéticos | ✅ |
| 2 | Contexto de llamada, enriquecimiento, predicción de intención | ✅ |
| 1 | Transcripción en vivo (LiveKit + ASR en streaming) | pendiente |
| 3 | Emoción del cliente en tiempo real | pendiente |
| 4 | RAG y sugerencia generativa con citación obligatoria | pendiente |
| 5 | Clasificación reclamo/requerimiento (Ley 31763) | pendiente |
| 6 | Resumen y tipificación post-llamada | pendiente |
| 7 | Endurecimiento: PII, auditoría, RBAC, observabilidad | pendiente |

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

**La latencia es el requisito no funcional número uno.** Si la sugerencia llega
después de que el ejecutivo ya respondió, el sistema pierde la confianza en una
semana. Objetivos: transcripción visible **<700 ms**, sugerencia **<1.5 s**. El
portal muestra el tiempo de armado del contexto en la barra superior.

**Todo se almacena en UTC y se muestra en America/Lima.** Mezclarlo hace que un
consumo de las 20:25 aparezca como "01:25 del día siguiente", y los 15 días
hábiles de la Ley 31763 se cuentan sobre el calendario local.

---

## Estructura

```
apps/
  api/                 FastAPI: contexto de llamada, WS gateway
  web/                 React + TS: workspace del ejecutivo
packages/
  contracts/           esquemas de eventos y dominio (fuente de verdad)
  synthetic-data/      generador y escenarios es-PE
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
