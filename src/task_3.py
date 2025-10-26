import time
import uuid
import json
import pathlib
import threading
import queue
import datetime
import numpy as np
from collections import Counter
from typing import Iterator, Any

try:
    from . import domain
except ImportError:
    import domain


def compute (source: str, stop: threading.Event, reservoir_size: int = 10, **_: Any) -> Iterator[domain.Result]:
    sample : list[str] = []
    newest = datetime.datetime(datetime.MINYEAR, 1, 1, 0, 0, 0)
    oldest = datetime.datetime(9999, 1, 1, 0, 0, 0)
    condition = threading.Condition()
    last_count = 0  # Para rastrear cuándo hay nuevos datos

    q: queue.Queue[list[domain.Events]] = queue.Queue()
    producer_thread = threading.Thread(target=producer, args=(pathlib.Path(source), stop, q), daemon=True)
    producer_thread.start()

    def helper()-> None:
        nonlocal sample, newest, oldest, last_count
        count = 0

        while not stop.is_set():
            try:
                batch = q.get(timeout=0.1)
            except queue.Empty:
                continue
                
            with condition:
                for event in batch:
                    code = event["message"].split(": ")[-1]
                    timestamp = datetime.datetime.fromtimestamp(event["timestamp"])
                    if len(sample) < reservoir_size:
                        sample.append(code)
                    else:
                        j = np.random.randint(0, count)
                        if j < reservoir_size:
                            sample[j] = code
                    count += 1

                    newest = max(newest, timestamp)
                    oldest = min(oldest, timestamp)

                # Visualizar el estado actual del reservorio
                print(f"[Reservoir Update] Size: {len(sample)}/{reservoir_size} | Content: {sample} | Total events: {count}")
                
                last_count = count  # Actualizar el contador
                condition.notify_all()

            q.task_done()

    helper_thread = threading.Thread(target=helper, daemon=True)
    helper_thread.start()

    prev_count = 0
    while not stop.is_set():
        with condition:
            # Esperar hasta que haya nuevos datos o timeout
            if not sample:
                condition.wait(timeout=0.5)
                if not sample:
                    continue
            
            # Si hay nuevos datos, actualizar prev_count
            if last_count != prev_count:
                prev_count = last_count
            
            most_common = Counter(sample).most_common(1)[0][0]
            
            # Visualizar análisis del reservorio
            counter = Counter(sample)
            # print(f"\n{'='*60}")
            # print(f"[Reservoir Analysis]")
            # print(f"  Sample content: {sample}")
            # print(f"  Frequency distribution: {dict(counter)}")
            # print(f"  Most common code: {most_common}")
            # print(f"  Time range: {oldest} to {newest}")
            # print(f"{'='*60}\n")
            
            yield domain.Result(
                value=float(most_common),
                newest_considered=newest,
                oldest_considered=oldest,
            )

def producer(path: pathlib.Path, stop: threading.Event, q: queue.Queue[list[domain.Events]]) -> None:
    seen = set()
    while not stop.is_set():
        found_new = False
        for file_path in path.glob("*.json"):
            if file_path in seen:
                continue
            else:
                seen.add(file_path)
                batch = json.loads(file_path.read_text())
                q.put(batch)
                found_new = True
        
        # Si no se encontraron archivos nuevos, esperar un poco antes de revisar de nuevo
        if not found_new:
            time.sleep(0.5)

if __name__ == "__main__":
    import tempfile
    import os
    
    # Prueba local creando archivos
    # Crear directorio data/task_3 si no existe
    os.makedirs("data/task_3", exist_ok=True)
    
    with tempfile.TemporaryDirectory(dir="data/task_3") as tmp_dir:
        path = pathlib.Path(tmp_dir)
        for _ in range(2):
            with open(path / f"{uuid.uuid4()}.json", "w") as file:
                json.dump(
                    [
                        {
                            "service": "training",
                            "timestamp": datetime.datetime.now().timestamp(),
                            "message": f"HTTP Status Code: {np.random.choice([200, 400, 500, 202, 404, 503])}",
                        },
                    ],
                    file,
                )
        for _ in range(2):
            with open(path / f"{uuid.uuid4()}.json", "w") as file:
                json.dump(
                    [
                        {
                            "service": "monitoring",
                            "timestamp": datetime.datetime.now().timestamp(),
                            "message": f"HTTP Status Code: {np.random.choice([200, 400, 500, 202, 404, 503])}",
                        },
                    ],
                    file,
                )
        stop = threading.Event()

        try: 
            generator = compute(tmp_dir, stop, reservoir_size=2)
            for result in generator:
                print(f"Result: {result}")
                time.sleep(2)
        finally:
            print("Stopping producer...")
            stop.set()