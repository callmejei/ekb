"""Pure-logic tests: security filters, chunking, entity grounding. Run: make test"""

from datetime import date

from app.pipeline.chunk import MAX_TOKENS, chunk_elements, n_tokens
from app.pipeline.enrich import QA, Enrichment, Entity, Relation, ground, grounded
from app.pipeline.extract import Element
from app.retrieval.hybrid import rrf
from app.security import User, cypher_params, cypher_visible, es_mandatory_filter

ERIN = User("erin", "Erin", ("VIEWER",), ("RETAIL_PRODUCTS",))


def test_es_filter_has_all_mandatory_clauses():
    f = es_mandatory_filter(ERIN, date(2026, 10, 13))
    assert {"term": {"is_active": True}} in f
    assert {"range": {"effective_date": {"lte": "2026-10-13"}}} in f
    assert {"terms": {"access_group": ["RETAIL_PRODUCTS"]}} in f
    expiry = next(c for c in f if "bool" in c)
    assert {"range": {"expiry_date": {"gte": "2026-10-13"}}} in expiry["bool"]["should"]


def test_cypher_filter_and_params():
    clause = cypher_visible("c")
    for part in ("c.is_active = true", "c.access_group IN $groups", "c.effective_date <= $today", "c.expiry_date"):
        assert part in clause
    assert cypher_params(ERIN, date(2026, 1, 2)) == {"groups": ["RETAIL_PRODUCTS"], "today": "2026-01-02"}


def test_tables_are_never_split_and_chunks_bounded():
    long_para = " ".join(["word"] * 2000)
    table = {"header": ["a", "b"], "rows": [["1", "2"]] * 200, "markdown": "| a | b |\n" + "| 1 | 2 |\n" * 200, "caption": "Rates"}
    elements = [
        Element(1, "heading", "Section", level=1),
        Element(1, "text", long_para),
        Element(2, "table", table["markdown"], table=table),
        Element(3, "heading", "Other", level=1),
        Element(3, "text", "short"),
    ]
    chunks = chunk_elements(elements, "Doc")
    tables = [c for c in chunks if c.chunk_type == "table"]
    assert len(tables) == 1 and tables[0].text.count("| 1 | 2 |") == 200
    assert all(n_tokens(c.text) <= MAX_TOKENS + 150 for c in chunks if c.chunk_type == "text")
    assert chunks[-1].heading_path == "Doc > Other"
    assert tables[0].page == 2


def test_grounding_drops_invented_entities():
    e = Enrichment(
        summary="A car loan product disclosure sheet.",
        sample_qa=[QA(question="q", answer="a")],
        entities=[Entity(name="Car Loan", type="Product"), Entity(name="Responsible Lending Policy", type="Policy")],
        relations=[Relation(source="Responsible Lending Policy", type="GOVERNS", target="Car Loan")],
    )
    g = ground(e, "The Sample Bank Car Loan finances vehicles.")
    assert [x.name for x in g.entities] == ["Car Loan"]
    assert g.relations == []
    assert grounded("TDSR (Total Debt Servicing Ratio)", "assessed under the TDSR framework")


def test_rrf_rewards_agreement():
    a = [{"_id": "x", "_source": {}}, {"_id": "y", "_source": {}}]
    b = [{"_id": "y", "_source": {}}, {"_id": "z", "_source": {}}]
    top = rrf(a, b)[0]
    assert top["ranks"] == {"bm25": 2, "knn": 1}  # "y" appears in both lists, so it wins
