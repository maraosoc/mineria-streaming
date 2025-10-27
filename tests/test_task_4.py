# tests/test_task_4.py
import datetime
import json
import pathlib
import threading

from src.task_4 import compute

def test_task_4_bloom(tmp_path: pathlib.Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    patterns = tmp_path / "patterns.txt"
    patterns.write_text("HTTP Status Code: 500\nSomething else\n")

    t0 = datetime.datetime(2025, 1, 1, 0, 0, 0)

    # batch con 2 eventos, 1 matchea el patrón 500
    with open(source / "b1.json", "w") as f:
        json.dump([
            {"service": "s", "timestamp": t0.timestamp(), "message": "HTTP Status Code: 200"},
            {"service": "s", "timestamp": t0.timestamp(), "message": "HTTP Status Code: 500"},
        ], f)

    stop = threading.Event()
    gen = compute(str(source), stop=stop, filter_file=str(patterns), m_bits=1024*8, k_hashes=3)
    r1 = next(gen)
    assert abs(r1.value - 0.5) < 1e-9
    stop.set()
