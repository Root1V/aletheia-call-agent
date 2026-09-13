"""Enumeraciones del dominio.

Perímetro: banca peruana (SBS / Indecopi). Los valores de texto son estables y
forman parte del contrato entre servicios: no se renombran sin una migración.
"""

from enum import StrEnum


class Speaker(StrEnum):
    """Participante de la llamada.

    La separación es por track de audio (LiveKit), no por diarización, así que
    es exacta por construcción en el MVP.
    """

    CUSTOMER = "customer"
    AGENT = "agent"


class CallFlow(StrEnum):
    """Flujo de atención. El MVP profundiza en RECLAMOS; el resto es backlog."""

    RECLAMOS = "reclamos"
    VENTA = "venta"
    SERVICING = "servicing"


class CallIntent(StrEnum):
    """Taxonomía de motivos de llamada.

    Mantenida deliberadamente corta: la evidencia de la industria dice que los
    5 motivos principales concentran el 60-80% del volumen, y una taxonomía de
    15-40 líneas es lo que se etiqueta de forma fiable en la práctica.
    """

    # Reclamos y disputas — 45-60% del volumen en bancos digitales
    DISPUTA_CARGO_NO_RECONOCIDO = "disputa_cargo_no_reconocido"
    DISPUTA_FRAUDE = "disputa_fraude"
    DISPUTA_COBRO_DUPLICADO = "disputa_cobro_duplicado"
    DISPUTA_SERVICIO_NO_RECIBIDO = "disputa_servicio_no_recibido"
    RECLAMO_COMISION = "reclamo_comision"
    RECLAMO_TASA_INTERES = "reclamo_tasa_interes"
    SEGUIMIENTO_RECLAMO = "seguimiento_reclamo"

    # Servicing
    CONSULTA_SALDO = "consulta_saldo"
    CONSULTA_MOVIMIENTO = "consulta_movimiento"
    TARJETA_BLOQUEADA = "tarjeta_bloqueada"
    TARJETA_RECHAZADA = "tarjeta_rechazada"
    ACTUALIZACION_DATOS = "actualizacion_datos"
    CLAVE_ACCESO = "clave_acceso"

    # Venta
    CONSULTA_PRODUCTO = "consulta_producto"
    SOLICITUD_CREDITO = "solicitud_credito"
    AUMENTO_LINEA = "aumento_linea"

    # Retención
    CANCELACION_PRODUCTO = "cancelacion_producto"

    DESCONOCIDA = "desconocida"


class CaseType(StrEnum):
    """Clasificación regulatoria bajo la Ley 31763.

    Distinguir mal un RECLAMO de un REQUERIMIENTO es un incumplimiento frente a
    la SBS, y ocurre con frecuencia bajo presión de AHT. Por eso el copiloto
    propone la clasificación con su justificación y el ejecutivo la confirma.
    """

    RECLAMO = "reclamo"
    """Presunta afectación de un interés legítimo del usuario."""

    REQUERIMIENTO = "requerimiento"
    """Solicitud de una acción de la empresa: consulta, gestión, entrega."""


class CaseStatus(StrEnum):
    BORRADOR = "borrador"
    REGISTRADO = "registrado"
    EN_ANALISIS = "en_analisis"
    RESUELTO = "resuelto"
    CERRADO = "cerrado"


class EmotionLabel(StrEnum):
    """Dimensiones mostradas en el panel en vivo.

    No son las categorías académicas clásicas (ira, alegría, tristeza...): son
    las que un ejecutivo bancario puede accionar durante la llamada.
    """

    FRUSTRACION = "frustracion"
    SATISFACCION = "satisfaccion"
    CONFUSION = "confusion"
    URGENCIA = "urgencia"
    NEUTRAL = "neutral"


class RiskSignalKind(StrEnum):
    """Señales textuales de riesgo de alto valor en banca peruana."""

    MENCION_SBS = "mencion_sbs"
    MENCION_INDECOPI = "mencion_indecopi"
    MENCION_LIBRO_RECLAMACIONES = "mencion_libro_reclamaciones"
    MENCION_ABOGADO = "mencion_abogado"
    MENCION_REDES_SOCIALES = "mencion_redes_sociales"
    AMENAZA_CANCELACION = "amenaza_cancelacion"
    AMENAZA_CAMBIO_BANCO = "amenaza_cambio_banco"
    SOLICITUD_SUPERVISOR = "solicitud_supervisor"


class AuthLevel(StrEnum):
    """Nivel de verificación alcanzado en la llamada.

    La voz se trata como UNA señal de riesgo entre varias, nunca como
    contraseña: el 91% de los bancos de EE.UU. está reconsiderando la biometría
    de voz por el riesgo de clonación con IA.
    """

    NO_VERIFICADO = "no_verificado"
    PARCIAL = "parcial"
    VERIFICADO = "verificado"
    FALLIDO = "fallido"


class VulnerabilityKind(StrEnum):
    """Circunstancias de vulnerabilidad DECLARADAS por el cliente.

    El MVP usa únicamente vulnerabilidad declarada. Inferirla es sensible y
    queda en el backlog con consentimiento, revisión humana y prohibición
    expresa de usarla para precios u ofertas.
    """

    ADULTO_MAYOR = "adulto_mayor"
    DISCAPACIDAD_AUDITIVA = "discapacidad_auditiva"
    DISCAPACIDAD_VISUAL = "discapacidad_visual"
    DIFICULTAD_COMPRENSION = "dificultad_comprension"
    SITUACION_FINANCIERA_CRITICA = "situacion_financiera_critica"
    DUELO_RECIENTE = "duelo_reciente"
    IDIOMA_NO_NATIVO = "idioma_no_nativo"


class PIIKind(StrEnum):
    """Entidades sensibles redactadas antes de persistir y antes del prompt."""

    DNI = "dni"
    RUC = "ruc"
    CCI = "cci"
    NUMERO_TARJETA = "numero_tarjeta"
    CVV = "cvv"
    FECHA_VENCIMIENTO = "fecha_vencimiento"
    NUMERO_CUENTA = "numero_cuenta"
    TELEFONO = "telefono"
    EMAIL = "email"
    DIRECCION = "direccion"
    NOMBRE = "nombre"


class TransactionStatus(StrEnum):
    PENDIENTE = "pendiente"
    LIQUIDADA = "liquidada"
    RECHAZADA = "rechazada"
    REVERTIDA = "revertida"


class Channel(StrEnum):
    APP = "app"
    WEB = "web"
    POS = "pos"
    ATM = "atm"
    ECOMMERCE = "ecommerce"
    IVR = "ivr"
    AGENCIA = "agencia"
    CALL_CENTER = "call_center"
