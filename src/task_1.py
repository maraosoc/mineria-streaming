import json
import pathlib
import threading
import queue
import time
from typing import Dict, Any, Iterator, List, Optional
from datetime import datetime

# ---------------------------------------------------------------------
# Importación robusta de Result
# ---------------------------------------------------------------------
try:
    from src.domain import Result  # Para entorno de paquete
except ModuleNotFoundError:
    from domain import Result  # Para ejecución directa (modo script)

# ---------------------------------------------------------------------
# Funciones de utilidad
# ---------------------------------------------------------------------
def extract_http_status_code(message: str) -> Optional[str]:
    """Extrae el código de estado HTTP (ej. '200') de un mensaje de log."""
    tag = "HTTP Status Code: "
    if tag in message:
        code_part = message.split(tag, 1)[-1]
        if code_part:
            return code_part.split()[0]
    return None


def is_successful_status(code: str) -> bool:
    """Verifica si un código de estado es de éxito (2xx)."""
    return code.startswith("2")


def get_service_metrics(service_metrics: Dict[str, Dict[str, int]], service_name: str) -> Dict[str, int]:
    """Inicializa y retorna el diccionario de métricas para un servicio dado."""
    if service_name not in service_metrics:
        service_metrics[service_name] = {"success_count": 0, "log_count": 0}
    return service_metrics[service_name]


def process_event(log_event: Dict[str, Any], service_metrics: Dict[str, Dict[str, int]]) -> None:
    """Procesa un evento, actualizando las métricas por servicio."""
    service_name = log_event.get("service", "unknown_service")
    message = log_event.get("message", "")

    metrics = get_service_metrics(service_metrics, service_name)

    status_code = extract_http_status_code(message)
    if status_code:
        if is_successful_status(status_code):
            metrics["success_count"] += 1
        metrics["log_count"] += 1


def get_service_success_rate(service_metrics: Dict[str, Dict[str, int]], service_name: str) -> float:
    """Calcula la tasa de éxito para un servicio específico."""
    metrics = service_metrics.get(service_name)
    if not metrics:
        return 0.0

    count = metrics["log_count"]
    successes = metrics["success_count"]
    return (successes / count) if count > 0 else 0.0


# ---------------------------------------------------------------------
# Productor (monitoreo de archivos nuevos)
# ---------------------------------------------------------------------
def producer(source: str, q: queue.Queue, stop: threading.Event) -> None:
    """Monitorea un directorio para archivos JSON nuevos y los pone en la cola."""
    path = pathlib.Path(source)
    seen = set()

    print(f"[PRODUCER] Monitoreando: {path.resolve()}", flush=True)

    while not stop.is_set():
        if not path.is_dir():
            print(f"[PRODUCER] Error: Directorio no encontrado: {source}", flush=True)
            time.sleep(1)
            continue

        for file in path.glob("*.json"):
            if file.name in seen or not file.is_file():
                continue

            try:
                with open(file, "r") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                print(f"[PRODUCER] Archivo no JSON válido o vacío: {file.name}", flush=True)
                seen.add(file.name)
                continue
            except Exception as e:
                print(f"[PRODUCER] Error leyendo {file.name}: {e}", flush=True)
                seen.add(file.name)
                continue

            if not isinstance(data, list):
                data = [data]

            if data:
                q.put(data)
                seen.add(file.name)

        time.sleep(1)


# ---------------------------------------------------------------------
# Consumidor / Procesamiento de datos
# ---------------------------------------------------------------------
def compute(source: str, stop: threading.Event, data_dir: str | None = None, **_: Any) -> Iterator[Result]:
    """
    Procesa lotes de la cola, actualiza métricas acumuladas
    y emite resultados (Result) con ventana temporal global.
    """
    q: queue.Queue = queue.Queue()
    service_metrics: Dict[str, Dict[str, int]] = {}

    global_newest_timestamp = 0.0
    global_oldest_timestamp = float("inf")

    producer_thread = threading.Thread(target=producer, args=(source, q, stop), daemon=True)
    producer_thread.start()

    try:
        while not stop.is_set():
            try:
                batch: List[Dict[str, Any]] = q.get(timeout=0.1)
            except queue.Empty:
                continue

            newest_timestamp = 0.0
            oldest_timestamp = float("inf")

            for event in batch:
                process_event(event, service_metrics)
                ts = event.get("timestamp", 0.0)
                if ts > newest_timestamp:
                    newest_timestamp = ts
                if ts < oldest_timestamp and ts != 0.0:
                    oldest_timestamp = ts

            if newest_timestamp > global_newest_timestamp:
                global_newest_timestamp = newest_timestamp
            if oldest_timestamp < global_oldest_timestamp and oldest_timestamp != float("inf"):
                global_oldest_timestamp = oldest_timestamp

            if global_newest_timestamp > 0.0 and global_oldest_timestamp != float("inf"):
                target_service = "monitoring"
                average_value = get_service_success_rate(service_metrics, target_service)

                yield Result(
                    value=average_value,
                    newest_considered=datetime.fromtimestamp(global_newest_timestamp),
                    oldest_considered=datetime.fromtimestamp(global_oldest_timestamp),
                )

            q.task_done()

    finally:
        # Aseguramos que el productor se detenga correctamente
        stop.set()
        producer_thread.join(timeout=1)


# ---------------------------------------------------------------------
# Bloque de ejemplo de ejecución directa
# ---------------------------------------------------------------------
if __name__ == "__main__":
    DATA_DIRECTORY = pathlib.Path(__file__).parent / "data_logs_stream_test"
    DATA_DIRECTORY.mkdir(exist_ok=True)

    stop_event = threading.Event()

    print(f"Iniciando procesamiento en: {DATA_DIRECTORY.resolve()}")

    generator = compute(str(DATA_DIRECTORY), stop_event)

    try:
        for i in range(10):
            result = next(generator)
            print("---------------------------------------")
            print(f"Resultado {i+1}: Tasa de éxito 'monitoring': {result.value * 100:.2f}%")
            print(f"Ventana: {result.oldest_considered.strftime('%H:%M:%S')} - "
                  f"{result.newest_considered.strftime('%H:%M:%S')}")
            time.sleep(2)
    finally:
        stop_event.set()
        print("Proceso de streaming detenido.")
