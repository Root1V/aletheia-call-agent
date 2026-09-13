"""Datos de referencia peruanos.

Faker no tiene locale es_PE: sus nombres españoles ("Segismundo Burgos Pavón")
delatan de inmediato que la demo es sintética ante cualquiera que trabaje en un
banco peruano. Estas listas existen para que los datos suenen reales.
"""

from __future__ import annotations

NOMBRES_M: tuple[str, ...] = (
    "José",
    "Luis",
    "Carlos",
    "Juan",
    "Miguel",
    "Jorge",
    "Víctor",
    "Julio",
    "César",
    "Manuel",
    "Pedro",
    "Alberto",
    "Walter",
    "Édgar",
    "Percy",
    "Wilfredo",
    "Jhonatan",
    "Brayan",
    "Kevin",
    "Diego",
    "Renzo",
    "Gonzalo",
    "Sebastián",
    "Fabrizio",
    "Marco",
    "Álvaro",
    "Christian",
    "Elmer",
    "Nilton",
)

NOMBRES_F: tuple[str, ...] = (
    "María",
    "Rosa",
    "Carmen",
    "Ana",
    "Lucía",
    "Patricia",
    "Gabriela",
    "Claudia",
    "Milagros",
    "Yesenia",
    "Katherine",
    "Fiorella",
    "Jessica",
    "Vanessa",
    "Elizabeth",
    "Roxana",
    "Magaly",
    "Nataly",
    "Andrea",
    "Camila",
    "Valeria",
    "Alessandra",
    "Pierina",
    "Zoila",
    "Bertha",
    "Flor",
)

APELLIDOS: tuple[str, ...] = (
    "Quispe",
    "Mamani",
    "Flores",
    "Huamán",
    "Vásquez",
    "Rojas",
    "Sánchez",
    "Ramos",
    "Castillo",
    "Chávez",
    "Espinoza",
    "Vargas",
    "Torres",
    "Gutiérrez",
    "Díaz",
    "Paredes",
    "Condori",
    "Apaza",
    "Salazar",
    "Pariona",
    "Zapata",
    "Cárdenas",
    "Aguirre",
    "Bernal",
    "Ccahuana",
    "Ticona",
    "Sulca",
    "Yupanqui",
    "Cabrera",
    "Del Águila",
    "Miranda",
    "Peralta",
    "Bardales",
    "Calderón",
)

DISTRITOS_LIMA: tuple[str, ...] = (
    "Miraflores",
    "San Isidro",
    "Santiago de Surco",
    "La Molina",
    "San Borja",
    "Jesús María",
    "Lince",
    "Magdalena del Mar",
    "Pueblo Libre",
    "Barranco",
    "Chorrillos",
    "San Miguel",
    "Los Olivos",
    "San Martín de Porres",
    "Comas",
    "Independencia",
    "Villa El Salvador",
    "Villa María del Triunfo",
    "San Juan de Lurigancho",
    "Ate",
    "Santa Anita",
    "La Victoria",
    "Breña",
    "Rímac",
    "Surquillo",
    "San Juan de Miraflores",
    "Carabayllo",
)

CIUDADES: tuple[tuple[str, float], ...] = (
    ("Lima", 0.45),
    ("Callao", 0.07),
    ("Arequipa", 0.08),
    ("Trujillo", 0.07),
    ("Chiclayo", 0.05),
    ("Piura", 0.05),
    ("Cusco", 0.05),
    ("Huancayo", 0.04),
    ("Iquitos", 0.03),
    ("Tacna", 0.03),
    ("Chimbote", 0.03),
    ("Juliaca", 0.03),
    ("Pucallpa", 0.02),
)

SEGMENTOS: tuple[tuple[str, float], ...] = (
    ("Clásico", 0.52),
    ("Preferente", 0.24),
    ("Exclusivo", 0.12),
    ("Patrimonial", 0.04),
    ("Pequeña Empresa", 0.08),
)

PRODUCTOS: tuple[tuple[str, str, str], ...] = (
    ("CTA_AHO_SOL", "Cuenta de Ahorros Soles", "deposito"),
    ("CTA_AHO_DOL", "Cuenta de Ahorros Dólares", "deposito"),
    ("CTA_SUELDO", "Cuenta Sueldo", "deposito"),
    ("TC_CLASICA", "Tarjeta de Crédito Clásica", "credito"),
    ("TC_ORO", "Tarjeta de Crédito Oro", "credito"),
    ("TC_SIGNATURE", "Tarjeta de Crédito Signature", "credito"),
    ("TD_DEBITO", "Tarjeta de Débito", "debito"),
    ("PREST_PERSONAL", "Préstamo Personal", "credito"),
    ("PREST_VEHIC", "Préstamo Vehicular", "credito"),
    ("HIPOTECARIO", "Crédito Hipotecario", "credito"),
    ("SEG_DESGRAV", "Seguro de Desgravamen", "seguro"),
    ("SEG_VEHIC", "Seguro Vehicular", "seguro"),
    ("PLAZO_FIJO", "Depósito a Plazo Fijo", "deposito"),
)

# ──────────────────────────────────────────────────────────────────────────────
# Catálogo de comercios
# ──────────────────────────────────────────────────────────────────────────────
#
# El campo clave es `descriptors`: el texto que el cliente ve en su estado de
# cuenta. Cuando ese texto es opaco ("DLO*RAPPI PE 55...", "PAYU*ADL", "EBS*")
# nace la disputa por cargo no reconocido, que es el 61% de las disputas y la
# que más insatisfacción genera. Resolverlo es la palanca más alta del flujo.
#
# (nombre, categoría, distrito, descriptores crudos, opacidad 0-1)

CATALOGO_COMERCIOS: tuple[tuple[str, str, str | None, tuple[str, ...], float], ...] = (
    # Delivery y transporte — descriptores notoriamente opacos
    ("Rappi", "Delivery", "Miraflores", ("DLO*RAPPI PE", "RAPPI PERU SAC", "DLOCAL*RAPPI"), 0.9),
    ("PedidosYa", "Delivery", "San Isidro", ("PEDIDOSYA*PE", "PYA*PEDIDOSYA"), 0.7),
    ("Uber", "Transporte", None, ("UBER *TRIP", "UBER* PENDING", "UBER BV"), 0.8),
    ("Cabify", "Transporte", None, ("CABIFY PERU", "CABIFY*RIDE"), 0.5),
    ("inDrive", "Transporte", None, ("INDRIVE*PE", "SUNRISE TECH"), 0.95),
    # Supermercados — descriptores claros
    ("Plaza Vea", "Supermercado", "Surquillo", ("PLAZA VEA 0231", "SPSA PLAZA VEA"), 0.2),
    ("Wong", "Supermercado", "San Isidro", ("WONG 0045", "CENCOSUD WONG"), 0.2),
    ("Metro", "Supermercado", "Los Olivos", ("METRO 1102", "CENCOSUD METRO"), 0.2),
    (
        "Tottus",
        "Supermercado",
        "Santiago de Surco",
        ("TOTTUS 45 SURCO", "HIPERMERCADOS TOTTUS"),
        0.2,
    ),
    ("Tambo+", "Tienda de conveniencia", "Lince", ("TAMBO+ 1023", "TAMBO MAS SAC"), 0.3),
    ("Vivanda", "Supermercado", "Miraflores", ("VIVANDA 012",), 0.2),
    # Farmacias
    ("Inkafarma", "Farmacia", "Jesús María", ("INKAFARMA 2201", "BOTICAS INKAFARMA"), 0.2),
    ("Mifarma", "Farmacia", "Breña", ("MIFARMA 0871", "ALBIS SA"), 0.5),
    # Restaurantes
    ("Bembos", "Restaurante", "Miraflores", ("BEMBOS 021", "BEMBURGER SAC"), 0.4),
    ("Pardos Chicken", "Restaurante", "San Isidro", ("PARDOS CHICKEN 07",), 0.2),
    ("Norky's", "Restaurante", "Los Olivos", ("NORKYS 33",), 0.2),
    ("KFC", "Restaurante", "Ate", ("KFC 0912", "DELOSI SA"), 0.6),
    ("Starbucks", "Cafetería", "San Borja", ("STARBUCKS 8821",), 0.2),
    ("Popeyes", "Restaurante", "Surco", ("POPEYES 14", "DELOSI SA"), 0.6),
    # Grifos
    ("Primax", "Combustible", "La Molina", ("PRIMAX 4410", "COESTI SA"), 0.6),
    ("Repsol", "Combustible", "San Miguel", ("REPSOL 0221",), 0.2),
    # Retail
    (
        "Saga Falabella",
        "Tienda por departamento",
        "San Isidro",
        ("SAGA FALABELLA 12", "FALABELLA PERU"),
        0.2,
    ),
    ("Ripley", "Tienda por departamento", "Santiago de Surco", ("TIENDAS RIPLEY 04",), 0.2),
    ("Oechsle", "Tienda por departamento", "La Victoria", ("OECHSLE 07", "TIENDAS PERUANAS"), 0.5),
    ("Sodimac", "Mejoramiento del hogar", "Ate", ("SODIMAC 1180",), 0.2),
    ("Promart", "Mejoramiento del hogar", "Comas", ("PROMART 0322",), 0.2),
    # Entretenimiento
    ("Cineplanet", "Entretenimiento", "Santiago de Surco", ("CINEPLANET 18", "CINEPLEX SA"), 0.5),
    ("Cinemark", "Entretenimiento", "Jesús María", ("CINEMARK 05",), 0.2),
    # Suscripciones digitales — foco clásico de disputas por olvido
    ("Netflix", "Suscripción digital", None, ("NETFLIX.COM 8664710", "NETFLIX 866-579-7172"), 0.6),
    ("Spotify", "Suscripción digital", None, ("SPOTIFY P05CB1A1BC", "SPOTIFY AB"), 0.85),
    ("Disney+", "Suscripción digital", None, ("DISNEY PLUS", "DISNEYPLUS.COM"), 0.4),
    ("Max", "Suscripción digital", None, ("MAX.COM", "WARNERMEDIA DTC"), 0.8),
    (
        "YouTube Premium",
        "Suscripción digital",
        None,
        ("GOOGLE *YOUTUBEPREMIUM", "GOOGLE *SERVICES"),
        0.85,
    ),
    ("OpenAI", "Suscripción digital", None, ("OPENAI *CHATGPT SUBSCR",), 0.7),
    ("iCloud", "Suscripción digital", None, ("APPLE.COM/BILL", "ITUNES.COM/BILL"), 0.9),
    # E-commerce internacional — el mayor generador de "no reconozco este cargo"
    ("AliExpress", "E-commerce", None, ("ALIEXPRESS*", "EBS*ALIEXPRESS", "PAYU*ALIEXPRESS"), 0.95),
    ("Shein", "E-commerce", None, ("SHEIN.COM", "PAYU*SHEIN", "ROADGET BUSINESS"), 0.9),
    ("Temu", "E-commerce", None, ("TEMU.COM", "WHALECO INC"), 0.95),
    ("Amazon", "E-commerce", None, ("AMZN MKTP US", "AMAZON.COM*M12AB"), 0.7),
    ("Mercado Libre", "E-commerce", None, ("MERPAGO*MERCADOLIBRE", "MERCADOPAGO*"), 0.7),
    # Telecomunicaciones
    ("Movistar", "Telecomunicaciones", None, ("MOVISTAR RECARGA", "TELEFONICA DEL PERU"), 0.4),
    ("Claro", "Telecomunicaciones", None, ("CLARO PERU", "AMERICA MOVIL PERU"), 0.4),
    ("Entel", "Telecomunicaciones", None, ("ENTEL PERU SA",), 0.3),
)

# Motivos de rechazo en lenguaje humano.
#
# El código crudo del autorizador ("05", "51", "N7") no le sirve al ejecutivo ni
# al cliente. Lo que reduce la llamada es la frase que explica qué pasó y qué
# hacer.
MOTIVOS_RECHAZO: tuple[tuple[str, str], ...] = (
    ("fondos_insuficientes", "No había saldo suficiente en la cuenta al momento de la compra."),
    ("limite_internet", "Superó el límite diario que tiene configurado para compras por internet."),
    (
        "compras_internacionales_bloqueadas",
        "El comercio está fuera del país y la tarjeta no tiene habilitadas "
        "las compras internacionales.",
    ),
    ("clave_incorrecta", "La clave ingresada no coincidió con la registrada."),
    (
        "bloqueo_preventivo",
        "Se bloqueó por prevención: el patrón de consumo no coincidía con el habitual del cliente.",
    ),
    ("tarjeta_vencida", "La tarjeta está vencida y la renovación aún no fue activada."),
    ("comercio_no_habilitado", "El rubro del comercio está restringido para esta tarjeta."),
)

DISPOSITIVOS: tuple[str, ...] = (
    "iPhone",
    "Samsung Galaxy",
    "Xiaomi Redmi",
    "Motorola",
    "Huawei",
    "Honor",
)

# Pantallas de la app y opciones del IVR, para el contexto de journey digital.
PANTALLAS_APP: tuple[str, ...] = (
    "inicio",
    "detalle_movimiento",
    "mis_tarjetas",
    "bloquear_tarjeta",
    "reportar_consumo",
    "ayuda_disputas",
    "chat_soporte",
    "estado_cuenta",
    "limites_compra",
    "contacto",
)

OPCIONES_IVR: tuple[tuple[str, str], ...] = (
    ("IVR:1", "Consultas de saldo y movimientos"),
    ("IVR:2", "Reportar un consumo no reconocido"),
    ("IVR:3", "Bloqueo de tarjetas"),
    ("IVR:4", "Préstamos y tarjetas"),
    ("IVR:0", "Hablar con un ejecutivo"),
)
