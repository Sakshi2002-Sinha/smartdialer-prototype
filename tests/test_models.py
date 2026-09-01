from smartdialer.models import (
    Agent,
    Base,
    Borrower,
    Call,
    Campaign,
    CampaignMetrics,
    ProviderEvent,
)


def test_all_models_are_registered():
    expected_tables = {
        "campaigns",
        "agents",
        "borrowers",
        "calls",
        "provider_events",
        "campaign_metrics",
    }

    actual_tables = set(Base.metadata.tables.keys())

    assert expected_tables == actual_tables


def test_model_classes_exist():
    assert Campaign.__tablename__ == "campaigns"
    assert Agent.__tablename__ == "agents"
    assert Borrower.__tablename__ == "borrowers"
    assert Call.__tablename__ == "calls"
    assert ProviderEvent.__tablename__ == "provider_events"
    assert CampaignMetrics.__tablename__ == "campaign_metrics"