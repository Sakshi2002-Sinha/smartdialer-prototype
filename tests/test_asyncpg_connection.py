import asyncpg
import pytest


@pytest.mark.asyncio
async def test_asyncpg_direct_connection():
    conn = await asyncpg.connect(
        user="smartdialer",
        password="smartdialer_dev",
        database="smartdialer",
        host="127.0.0.1",
        port=55432,
    )

    try:
        result = await conn.fetchval("SELECT 1")
        assert result == 1
    finally:
        await conn.close()