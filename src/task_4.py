# src/task_4.py
import datetime
import hashlib
import json
import pathlib
import time
import queue
import concurrent.futures
from typing import Any, Iterator
import domain


class BloomFilter:
    """Implementación ligera de un filtro de Bloom en memoria."""

    def __init__(self, bit_count: int, hash_count: int):
        self.bit_count = bit_count
        self.hash_count = hash_count
        self._bit_array = bytearray((bit_count + 7) // 8)

    def _bit_index(self, index: int) -> tuple[int, int]:
        return index // 8, index % 8

    def _set_bit(self, index: int) -> None:
        byte_idx, bit_idx = self._bit_index(index)
        self._bit_array[byte_idx] |= (1 << bit_idx)

    def _get_bit(self, index: int) -> bool:
        byte_idx, bit_idx = self._bit_index(index)
        return bool(self._bit_array[byte_idx] & (1 << bit_idx))

    def _hash_indices(self, value: str) -> list[int]:
        """Genera los índices de hash que se utilizarán para marcar bits."""
        encoded = value.encode("utf-8")
        indices = []
        for i in range(self.hash_count):
            digest = hashlib.sha256(i.to_bytes(2, "big") + encoded).digest()
            indices.append(int.from_bytes(digest[:4], "big") % self.bit_count)
        return indices

    def add(self, value: str) -> None:
        for idx in self._hash_indices(value):
            self._set_bit(idx)

    def __contains__(self, value: str) -> bool:
        return all(self._get_bit(idx) for idx in self._hash_indices(value))


def load_bloom_filter(path: pathlib.Path, bit_count: int, hash_count: int) -> BloomFilter:
    """Carga un filtro de Bloom con las cadenas contenidas en un archivo."""
    bf = BloomFilter(bit_count, hash_count)
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    bf.add(line)
    except FileNotFoundError:
        raise RuntimeError(f"No se encontró el archivo de filtro: {path}")
    return bf


def producer(source_dir: str, output_queue: queue.Queue, stop_signal: Any) -> None:
    """Lee archivos JSON nuevos del directorio y los envía por la cola."""
    path = pathlib.Path(source_dir)
    processed_files: set[str] = set()

    while not stop_signal.is_set():
        for file in path.glob("*.json"):
            if file.name in processed_files:
                continue

            processed_files.add(file.name)
            try:
                with file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    data = [data]
                output_queue.put(data)
            except (json.JSONDecodeError, OSError):
                
                continue

        time.sleep(0.5)


def compute(
    source: str,
    stop: Any,
    filter_file: str,
    m_bits: int = 1_000_000,
    k_hashes: int = 7,
    **_: Any,
) -> Iterator[domain.Result]:

    data_queue: queue.Queue[list[dict]] = queue.Queue()
    bloom_filter = load_bloom_filter(pathlib.Path(filter_file), m_bits, k_hashes)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(producer, source, data_queue, stop)

        while not stop.is_set():
            try:
                batch = data_queue.get(timeout=1)
            except queue.Empty:
                continue

            if not batch:
                continue

            timestamps = [float(e["timestamp"]) for e in batch if "timestamp" in e]
            if not timestamps:
                continue

            fwd_hits = sum(1 for e in batch if str(e.get("message", "")) in bloom_filter)
            ratio = fwd_hits / len(batch)

            yield domain.Result(
                value=ratio,
                newest_considered=datetime.datetime.fromtimestamp(max(timestamps)),
                oldest_considered=datetime.datetime.fromtimestamp(min(timestamps)),
            )
