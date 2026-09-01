from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://smartdialer:smartdialer_dev@localhost:55432/smartdialer",
    )

    agent_reservation_ttl_sec: int = 5
    call_setup_ttl_sec: int = 8
    reaper_interval_sec: int = 2
    worker_tick_interval_sec: float = 1.0

    pacing_window_sec: int = 30
    min_answer_rate_floor: float = 0.05
    ewma_alpha: float = 0.2

    min_provider_health: float = 0.5
    max_abandon_risk: int = 3

    heartbeat_stale_sec: int = 5
    max_overdial_cap: int = 50
    borrower_max_attempts: int = 3


settings = Settings()