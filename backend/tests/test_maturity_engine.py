from app.services.maturity_engine import classify_tier, STATUS_WEIGHT


def test_classify_tier():
    assert classify_tier(0) == "Bronze"
    assert classify_tier(25) == "Bronze"
    assert classify_tier(26) == "Prata"
    assert classify_tier(50) == "Prata"
    assert classify_tier(51) == "Ouro"
    assert classify_tier(75) == "Ouro"
    assert classify_tier(76) == "Platina"
    assert classify_tier(100) == "Platina"


def test_status_weights():
    assert STATUS_WEIGHT["OFICIAL"] == 1.0
    assert STATUS_WEIGHT["LACUNA"] == 0.0
