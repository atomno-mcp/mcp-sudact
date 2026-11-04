import pytest
from pydantic import ValidationError

from atomno_mcp_sudact.contracts import Citation, Search


@pytest.mark.parametrize(
    "change",
    [
        {"instance": "first"},
        {"source": "fas"},
        {"collegium": "civil"},
        {"date_from": "2026-02-30"},
        {"date_from": "2026-1-01"},
        {"date_from": "2026-02-02", "date_to": "2026-01-01"},
        {"limit": True},
        {"limit": 51},
        {"page": 1},
        {"court_type": "fas", "page": 1},
        {"court_type": "vs", "page": 5, "limit": 11},
        {"court_type": "vs", "fas_body": "УФАС"},
        {"fas_law": "999-ФЗ"},
        {"fas_act_type": "любое"},
    ],
)
def test_invalid(change):
    with pytest.raises(ValidationError):
        Search.model_validate({"query": "тест", **change})


@pytest.mark.parametrize("section", ["vs", "arbitr", "soyu"])
def test_native_page(section):
    assert Search(query="тест", court_type=section, page=5, limit=10).page == 5


def test_fas_normalization():
    r = Search(
        query="тест", court_type="fas", fas_body=" УФАС ", fas_law="223 FZ", fas_act_type="штраф"
    )
    assert (r.fas_body, r.fas_law, r.fas_act_type) == ("УФАС", "223-ФЗ", "постановление о штрафе")
    assert Search(query="тест", fas_body=" ").fas_body is None


def test_citation():
    assert Citation(case_id="fas:test").case_id == "fas:test"
    with pytest.raises(ValidationError):
        Citation(url=" ")
