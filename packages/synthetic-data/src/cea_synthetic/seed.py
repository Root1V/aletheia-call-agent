"""Carga del dataset sintético en Postgres.

El seeder es idempotente: vacía y recarga. No está pensado para producción,
sino para que `make seed` deje siempre la misma base reproducible a partir de
una semilla, que es lo que necesitan la demo y el golden set.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import psycopg
from cea_contracts import Customer, Merchant

from .generator import PeruBankGenerator, Scenario
from .scenarios import build_all

DEFAULT_DSN = os.environ.get("CEA_DATABASE_URL", "postgresql://cea:cea_dev@localhost:5432/cea")

# Orden inverso al de las dependencias: los hijos primero.
_TABLAS_EN_ORDEN_DE_BORRADO = (
    "seed_info",
    "demo_scenarios",
    "audit_log",
    "emotion_timeline",
    "call_events",
    "calls",
    "cases",
    "digital_journey_events",
    "account_events",
    "transactions",
    "product_holdings",
    "customers",
    "merchant_descriptors",
    "merchants",
)


@dataclass(slots=True)
class SeedReport:
    merchants: int = 0
    customers: int = 0
    transactions: int = 0
    account_events: int = 0
    journey_events: int = 0
    cases: int = 0
    scenarios: int = 0

    def __str__(self) -> str:
        return (
            f"comercios={self.merchants} clientes={self.customers} "
            f"transacciones={self.transactions} eventos_cuenta={self.account_events} "
            f"journey={self.journey_events} casos={self.cases} escenarios={self.scenarios}"
        )


def _insert_merchants(cur: psycopg.Cursor, merchants: tuple[Merchant, ...]) -> int:
    cur.executemany(
        """
        INSERT INTO merchants
            (merchant_id, display_name, legal_name, category, logo_url, district, city, country)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [
            (
                m.merchant_id,
                m.display_name,
                m.legal_name,
                m.category,
                m.logo_url,
                m.district,
                m.city,
                m.country,
            )
            for m in merchants
        ],
    )
    cur.executemany(
        "INSERT INTO merchant_descriptors (merchant_id, pattern) VALUES (%s, %s)",
        [(m.merchant_id, p) for m in merchants for p in m.descriptor_patterns],
    )
    return len(merchants)


def _insert_customer(cur: psycopg.Cursor, c: Customer) -> None:
    cur.execute(
        """
        INSERT INTO customers
            (customer_id, full_name, document_type, document_masked, segment,
             customer_since, birth_date, city, district, phone_masked, email_masked,
             nps, preferred_language, vulnerabilities)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (customer_id) DO NOTHING
        """,
        (
            c.customer_id,
            c.full_name,
            c.document_type,
            c.document_masked,
            c.segment,
            c.customer_since,
            c.birth_date,
            c.city,
            c.district,
            c.phone_masked,
            c.email_masked,
            c.nps,
            c.preferred_language,
            [v.value for v in c.vulnerabilities],
        ),
    )
    cur.executemany(
        """
        INSERT INTO product_holdings
            (holding_id, customer_id, product_code, product_name, opened_at,
             balance, credit_limit, currency, status, masked_number)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (holding_id) DO NOTHING
        """,
        [
            (
                h.holding_id,
                c.customer_id,
                h.product_code,
                h.product_name,
                h.opened_at,
                h.balance,
                h.credit_limit,
                h.currency,
                h.status,
                h.masked_number,
            )
            for h in c.holdings
        ],
    )


def _insert_scenario(cur: psycopg.Cursor, sc: Scenario, report: SeedReport) -> None:
    _insert_customer(cur, sc.customer)
    report.customers += 1

    cur.executemany(
        """
        INSERT INTO transactions
            (transaction_id, account_id, customer_id, occurred_at, amount, currency,
             status, channel, raw_descriptor, merchant_id, device_label,
             decline_reason, prior_purchases_90d, is_recurring)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (transaction_id) DO NOTHING
        """,
        [
            (
                t.transaction_id,
                t.account_id,
                sc.customer.customer_id,
                t.occurred_at,
                t.amount,
                t.currency,
                t.status.value,
                t.channel.value,
                t.raw_descriptor,
                t.merchant.merchant_id if t.merchant else None,
                t.device_label,
                t.decline_reason,
                t.prior_purchases_90d,
                t.is_recurring,
            )
            for t in sc.transactions
        ],
    )
    report.transactions += len(sc.transactions)

    cur.executemany(
        """
        INSERT INTO account_events
            (customer_id, occurred_at, kind, summary, related_transaction_id, severity)
        VALUES (%s,%s,%s,%s,%s,%s)
        """,
        [
            (
                sc.customer.customer_id,
                e.occurred_at,
                e.kind,
                e.summary,
                e.related_transaction_id,
                e.severity,
            )
            for e in sc.account_events
        ],
    )
    report.account_events += len(sc.account_events)

    cur.executemany(
        """
        INSERT INTO digital_journey_events
            (customer_id, occurred_at, channel, screen, action, succeeded, detail)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        """,
        [
            (
                sc.customer.customer_id,
                j.occurred_at,
                j.channel.value,
                j.screen,
                j.action,
                j.succeeded,
                j.detail,
            )
            for j in sc.journey
        ],
    )
    report.journey_events += len(sc.journey)

    cur.executemany(
        """
        INSERT INTO cases
            (case_id, folio, customer_id, case_type, status, opened_at, due_at,
             subject, summary, related_transaction_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (case_id) DO NOTHING
        """,
        [
            (
                k.case_id,
                k.folio,
                sc.customer.customer_id,
                k.case_type.value,
                k.status.value,
                k.opened_at,
                k.due_at,
                k.subject,
                k.summary,
                k.related_transaction_id,
            )
            for k in sc.open_cases
        ],
    )
    report.cases += len(sc.open_cases)

    cur.execute(
        """
        INSERT INTO demo_scenarios
            (scenario_id, customer_id, expected_intent, focus_transaction_id,
             narrative, expected_case_type, expects_case, ordinal)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            sc.scenario_id,
            sc.customer.customer_id,
            sc.intent.value,
            sc.focus_transaction_id,
            sc.narrative,
            sc.expected_case_type.value if sc.expected_case_type else None,
            sc.expects_case,
            report.scenarios,
        ),
    )
    report.scenarios += 1


def seed(
    dsn: str = DEFAULT_DSN, *, extra_customers: int = 150, seed_value: int = 2026
) -> SeedReport:
    """Vacía y recarga la base con un dataset reproducible."""
    report = SeedReport()
    gen = PeruBankGenerator(seed=seed_value)
    scenarios = build_all(seed=seed_value)

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(f"TRUNCATE {', '.join(_TABLAS_EN_ORDEN_DE_BORRADO)} RESTART IDENTITY CASCADE")

        report.merchants = _insert_merchants(cur, gen.merchants)

        # Los escenarios primero: son los clientes que la demo usa y deben
        # existir aunque se reduzca el volumen de relleno.
        for sc in scenarios:
            _insert_scenario(cur, sc, report)

        # Clientes de relleno, para que las pantallas de búsqueda y los
        # agregados no se vean vacíos.
        for i in range(1000, 1000 + extra_customers):
            cliente = gen.customer(i)
            _insert_customer(cur, cliente)
            report.customers += 1
            historial = gen.history(cliente, days=60, per_day=0.6)[:40]
            if historial:
                cur.executemany(
                    """
                    INSERT INTO transactions
                        (transaction_id, account_id, customer_id, occurred_at, amount,
                         currency, status, channel, raw_descriptor, merchant_id,
                         device_label, decline_reason, prior_purchases_90d, is_recurring)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (transaction_id) DO NOTHING
                    """,
                    [
                        (
                            t.transaction_id,
                            t.account_id,
                            cliente.customer_id,
                            t.occurred_at,
                            t.amount,
                            t.currency,
                            t.status.value,
                            t.channel.value,
                            t.raw_descriptor,
                            t.merchant.merchant_id if t.merchant else None,
                            t.device_label,
                            t.decline_reason,
                            t.prior_purchases_90d,
                            t.is_recurring,
                        )
                        for t in historial
                    ],
                )
                report.transactions += len(historial)

        cur.execute(
            "INSERT INTO seed_info (seeded_at, seed_value) VALUES (now(), %s)",
            (seed_value,),
        )
        conn.commit()

    return report
