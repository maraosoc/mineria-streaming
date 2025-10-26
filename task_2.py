import json
import os
import time
from typing import Dict, Any, Generator, List, Tuple
from datetime import datetime, timedelta
# Asumo que domain.py está en el mismo directorio (src)
from domain import Result 
import pathlib
import threading

# The sliding window is 60 seconds (1 minute)
SLIDING_WINDOW_SECONDS = 60


def is_failure(log_event: Dict[str, Any]) -> bool:
    """Checks if a log event represents a failure (i.e., not a 200 HTTP status)."""
    message = log_event.get("message", "")
    return "HTTP Status Code: 200" not in message


# Define un tipo para las métricas:
# {service_name: [(timestamp, log_event), ...]}
ServiceMetrics = Dict[str, List[Tuple[float, Dict[str, Any]]]]


def compute(data_path: str, stop_event: threading.Event, **kwargs) -> Generator[Result, None, None]:
    """
    Computes the number of 'monitoring' service failures in a 60-second sliding window 
    by continuously watching for new log files.
    
    Note: The original implementation lacked the 'stop_event' argument 
    required by the main application logic. It has been added here.
    """
    failure_window: ServiceMetrics = {}
    processed_files = set()
    newest_timestamp = 0.0
    
    # Inicializa oldest_timestamp solo si es necesario, 
    # pero para el cálculo de la ventana, solo necesitamos newest_timestamp.

    while not stop_event.is_set():
        # Get list of files in directory
        try:
            current_files = set(os.listdir(data_path))
        except FileNotFoundError:
            print(f"Error: Directory not found at {data_path}")
            time.sleep(1)
            continue
            
        new_files = sorted(list(current_files - processed_files))

        if new_files:
            new_data_processed = False
            for file_name in new_files:
                file_path = os.path.join(data_path, file_name)

                try:
                    with open(file_path, 'r') as f:
                        log_events = json.load(f)
                except Exception as e:
                    # Ignorar archivos que no son JSON válidos o no se pueden abrir
                    print(f"Skipping file {file_name} due to error: {e}")
                    continue

                if not isinstance(log_events, list):
                    log_events = [log_events]

                # 1. Process events and update metrics
                for event in log_events:
                    ts = event.get("timestamp", 0.0)
                    service_name = event.get("service")

                    # Update newest considered timestamp
                    if ts > newest_timestamp:
                        newest_timestamp = ts
                        new_data_processed = True
                        
                    if service_name and is_failure(event):
                        if service_name not in failure_window:
                            failure_window[service_name] = []
                        failure_window[service_name].append((ts, event))

                processed_files.add(file_name)
            
            # 2. Compute sliding window statistics only if new data was processed
            if new_data_processed and newest_timestamp > 0.0:
                window_end_time = newest_timestamp
                window_start_time = window_end_time - SLIDING_WINDOW_SECONDS
                
                # Prune old events and count failures in the window
                for service in list(failure_window.keys()): # Iterate over a copy to allow deletion
                    failure_window[service] = [
                        (ts, event)
                        for ts, event in failure_window[service]
                        if ts >= window_start_time
                    ]
                    if not failure_window[service]:
                        del failure_window[service]

                # Calculate the metric (failures in 'monitoring' service)
                monitoring_failures_count = len(failure_window.get("monitoring", []))
                average_value = float(monitoring_failures_count) 

                # Prepare the result timestamps
                newest_dt = datetime.fromtimestamp(newest_timestamp)
                oldest_dt = datetime.fromtimestamp(window_start_time)

                # 3. Yield the result
                yield Result(
                    value=average_value,
                    newest_considered=newest_dt,
                    oldest_considered=oldest_dt,
                )
            
            # Add a small delay to prevent high CPU usage when no new files are found
            if not new_files:
                time.sleep(0.1)
                
        else:
            # If no new files, wait a bit before checking again
            time.sleep(0.5)

# --- Bloque de Prueba (Descomentar para ejecutar task_2.py directamente) ---

if __name__ == "__main__":
    # Configuración para la prueba local
    DATA_DIRECTORY = pathlib.Path(__file__).parent / "data_logs_stream_test"
    DATA_DIRECTORY.mkdir(exist_ok=True)
    basetime = datetime.now()
    stop_event = threading.Event()
    generator = compute(str(DATA_DIRECTORY), stop_event)

    # Batch 1: Una falla dentro de la ventana (t=90)
    batch_1_data = [
        {"service": "monitoring", "timestamp": (basetime + timedelta(seconds=30)).timestamp(), "message": "HTTP Status Code: 200"}, 
        {"service": "monitoring", "timestamp": (basetime + timedelta(seconds=90)).timestamp(), "message": "HTTP Status Code: 500"}, # Failure 1
    ]
    with open(os.path.join(DATA_DIRECTORY, "batch_1.json"), "w") as f:
        json.dump(batch_1_data, f)

    first_result = next(generator) 
    
    # La ventana es [90-60=30, 90]. 1 falla.
    print(f"Run 1: {int(first_result.value)} failures in the last minute. (Expected: 1)")
    
    # Batch 2: Una nueva falla (t=100)
    batch_2_data = [
        {"service": "monitoring", "timestamp": (basetime + timedelta(seconds=100)).timestamp(), "message": "HTTP Status Code: 503"}, # Failure 2
    ]
    with open(os.path.join(DATA_DIRECTORY, "batch_2.json"), "w") as f:
        json.dump(batch_2_data, f)
        
    second_result = next(generator) 
    
    # La ventana es [100-60=40, 100]. Fallas en 90 y 100. 2 fallas.
    print(f"Run 2: {int(second_result.value)} failures in the last minute. (Expected: 2)") 

    # Limpieza
    os.remove(os.path.join(DATA_DIRECTORY, "batch_1.json"))
    os.remove(os.path.join(DATA_DIRECTORY, "batch_2.json"))
    os.rmdir(DATA_DIRECTORY)