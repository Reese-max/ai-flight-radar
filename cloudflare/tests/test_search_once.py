import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace


def test_search_execution_uses_provider_chain(monkeypatch, capsys):
    script = Path(__file__).resolve().parents[1] / "scripts" / "search_once.py"
    spec = importlib.util.spec_from_file_location("radar_search_once", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    task = {
        "id": "a" * 64,
        "lease_token": "00000000-0000-4000-8000-000000000001",
        "origin": "TPE",
        "destination": "NRT",
        "depart_date": "2027-02-01",
        "return_date": "2027-02-05",
    }
    offer = SimpleNamespace(
        price_twd=5000,
        origin=task["origin"],
        destination=task["destination"],
        depart_date=task["depart_date"],
        return_date=task["return_date"],
        trip_type="round-trip",
        is_direct=True,
        stops=0,
        primary_airline="Test Air",
    )
    calls = []

    monkeypatch.setitem(sys.modules, "collector", SimpleNamespace(validate_task=lambda value: value))
    monkeypatch.setitem(
        sys.modules,
        "providers.selector",
        SimpleNamespace(search_with_provider_chain=lambda *args, **kwargs: calls.append((args, kwargs)) or [offer]),
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(task)))

    module.main()

    result = json.loads(capsys.readouterr().out)
    assert result["outcome"] == "ok"
    assert result["price_twd"] == 5000
    assert calls == [
        (("TPE", "NRT", "2027-02-01", "2027-02-05"), {"max_stops": 0})
    ]
