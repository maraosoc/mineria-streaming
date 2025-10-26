# src/task_4.py
import datetime
import hashlib
import json
import math
import pathlib
import threading
import time
from typing import Any, Iterator

from . import domain

class BloomFilter:
    def __init__(self, m_bits: int, k: int):
        self.m = m_bits
        self.k = k
        self.bits = bytearray((m_bits + 7) // 8)

    def _set_bit(self, idx: int) -> None:
        byte_i = idx // 8
        bit_i = idx % 8
        self.bits[byte_i] |= (1 << bit_i)

    def _get_bit(self, idx: int) -> bool:
        byte_i = idx // 8
        bit_i = idx % 8
        return (self.bits[byte_i] >> bit_i) & 1 == 1

    def _hashes(self, s: str) -> list[int]:
        res = []
        for i in range(self.k):
            h = hashlib.sha256((str(i) + "|" + s).encode("utf-8")).digest()
            # usa 4 bytes para entero
            val = int.from_bytes(h[:4], byteorder="big", signed=False)
            res.append(val % self.m)
        return res

    def add(self, s: str) -> None:
        for h in self._hashes(s):
            self._set_bit(h)

    def __contains__(self, s: str) -> bool:
        return all(self._get_bit(h) for h in self._hashes(s))


def _load_filter(filter_file: pathlib.Path, m_bits: int, k_hashes: int) -> BloomFilter:
    bf = BloomFilter(m_bits, k_hashes)
    with open(filter_file, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            bf.add(line)
    return bf


def compute(
    source: str,
    stop: threading.Event,
    filter_file: str,
    m_bits: int = 1_000_000,  # ~122KB
    k_hashes: int = 7,
    **_: Any,
) -> Iterator[domain.Result]:
    """
    value = ratio reenviados (Bloom-hit) en el último batch.
    """
    q: "queue.Queue[list[dict]]"
    import queue
    q = queue.Queue()

    bf = _load_filter(pathlib.Path(filter_file), m_bits, k_hashes)

    producer_thread = threading.Thread(target=producer, args=(source, q, stop))
    producer_thread.start()

    while not stop.is_set():
        batch = q.get()
        if not batch:
            q.task_done()
            continue

        fwd = 0
        newest_ts = max(float(e["timestamp"]) for e in batch)
        oldest_ts = min(float(e["timestamp"]) for e in batch)

        for e in batch:
            msg = str(e["message"])
            if msg in bf:
                fwd += 1

        value = fwd / len(batch)
        yield domain.Result(
            value=value,
            newest_considered=datetime.datetime.fromtimestamp(newest_ts),
            oldest_considered=datetime.datetime.fromtimestamp(oldest_ts),
        )
        q.task_done()


def producer(source: str, queue: "queue.Queue[list[dict]]", stop: threading.Event) -> None:
    path = pathlib.Path(source)
    seen: set[str] = set()
    while not stop.is_set():
        for file in path.glob("*.json"):
            if file.name in seen:
                continue
            seen.add(file.name)
            with open(file) as f:
                data = json.load(f)
            if isinstance(data, dict):
                data = [data]
            queue.put(data)
        time.sleep(1)
