"""Famous, fast-loading systems for instant demos (AGENTS.md §9.4).

Includes clean planets, a tiny rocky world, multi-planet systems, at least one
known eclipsing binary / false positive (so the demo shows ExoSeer correctly
REJECTING a non-planet), and quiet hosts for the injection sandbox.
"""
from __future__ import annotations

CATALOG: list[dict] = [
    {
        "id": "Kepler-8 b", "mission": "Kepler", "label": "Kepler-8 b",
        "blurb": "A clean hot Jupiter — a deep, obvious transit. The perfect first look.",
        "expected_verdict": "planet_candidate", "kind": "planet",
        "search_target": "Kepler-8",
    },
    {
        "id": "Kepler-10 b", "mission": "Kepler", "label": "Kepler-10 b",
        "blurb": "A tiny rocky world — shows ExoSeer's sensitivity to small planets.",
        "expected_verdict": "planet_candidate", "kind": "small",
        "search_target": "Kepler-10",
    },
    {
        "id": "Kepler-90", "mission": "Kepler", "label": "Kepler-90 (8 planets)",
        "blurb": "A famous multi-planet system — a Solar-System analogue around another star.",
        "expected_verdict": "planet_candidate", "kind": "multi",
        "search_target": "Kepler-90",
    },
    {
        "id": "Kepler-7 b", "mission": "Kepler", "label": "Kepler-7 b",
        "blurb": "A puffy, low-density hot Jupiter with a bright, deep transit.",
        "expected_verdict": "planet_candidate", "kind": "planet",
        "search_target": "Kepler-7",
    },
    {
        "id": "TRAPPIST-1", "mission": "TESS", "label": "TRAPPIST-1",
        "blurb": "Seven Earth-sized planets around a cool dwarf, seen by TESS.",
        "expected_verdict": "planet_candidate", "kind": "multi",
        "search_target": "TRAPPIST-1",
    },
    {
        "id": "KIC 9246715", "mission": "Kepler", "label": "KIC 9246715 (eclipsing binary)",
        "blurb": "A known eclipsing binary — the 'impostor'. Watch ExoSeer say NO.",
        "expected_verdict": "likely_eclipsing_binary", "kind": "eclipsing_binary",
        "search_target": "KIC 9246715",
    },
    {
        "id": "Kepler-16", "mission": "Kepler", "label": "Kepler-16 (quiet host)",
        "blurb": "A quiet star, ideal as a host in the Injection Sandbox.",
        "expected_verdict": "n/a", "kind": "quiet_host",
        "search_target": "Kepler-16",
    },
]

_BY_ID = {e["id"].lower(): e for e in CATALOG}
_BY_ID.update({e["search_target"].lower(): e for e in CATALOG})


def get_catalog() -> list[dict]:
    return [
        {k: v for k, v in e.items() if k != "search_target"}
        for e in CATALOG
    ]


def get_entry(system_id: str) -> dict | None:
    return _BY_ID.get(system_id.strip().lower())


def resolve_target(system_id: str) -> str:
    """Map a catalog id (e.g. 'Kepler-8 b') to a MAST-searchable target ('Kepler-8')."""
    e = get_entry(system_id)
    return e["search_target"] if e else system_id


def quiet_hosts() -> list[dict]:
    return [e for e in CATALOG if e["kind"] == "quiet_host"]
