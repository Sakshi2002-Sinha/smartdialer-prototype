from sqlalchemy import text
import pytest

from smartdialer.db import SessionLocal


@pytest.mark.asyncio
async def test_required_tables_exist():
    expected_tables = {
        "campaigns",
        "agents",
        "borrowers",
        "calls",
        "provider_events",
        "campaign_metrics",
    }

    async with SessionLocal() as session:
        result = await session.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                """
            )
        )

        actual_tables = {row[0] for row in result}

    assert expected_tables.issubset(actual_tables)