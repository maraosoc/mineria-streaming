import json
import pathlib
import datetime
import threading
import time
from src.task_2 import compute # Asume que src/task_2.py es el módulo de tu función compute

# Define la constante que se usa en task_2.py para la ventana
WINDOW_SECONDS = 60

def test_task_2_sliding_window(tmp_path: pathlib.Path) -> None:
    """
    Prueba que la función compute de task_2 calcule correctamente el número
    de fallas en el servicio 'monitoring' dentro de una ventana deslizante de 60 segundos.
    """
    
    # 1. Setup: Crear directorio de logs y tiempo base
    source = tmp_path / "source"
    source.mkdir(parents=True, exist_ok=True)
    basetime = datetime.datetime.now()
    
    # Crea un stop_event para simular la ejecución continua y evitar el TypeError
    stop_event = threading.Event()

    # 2. Inicializar el Generador (La llamada corregida)
    # Llama a compute() pasando el stop_event para satisfacer la firma de la función.
    generator = compute(str(source), stop_event)
    
    # --- Batch 1: T=30 (OK), T=90 (FAIL) ---
    # newest_timestamp = 90.0
    # Ventana esperada: [30.0, 90.0] -> 1 falla
    with open(source / "batch_1.json", "w") as file:
        json.dump(
            [
                # Evento 1: OK, T=30
                {
                    "service": "monitoring",
                    "timestamp": (
                        basetime + datetime.timedelta(seconds=30)
                    ).timestamp(),
                    "message": "HTTP Status Code: 200",
                },
                # Evento 2: FAIL, T=90
                {
                    "service": "monitoring",
                    "timestamp": (
                        basetime + datetime.timedelta(seconds=90)
                    ).timestamp(),
                    "message": "HTTP Status Code: 500",
                },
            ],
            file,
        )

    # Consumir el primer resultado
    result_1 = next(generator)
    
    # Asertos para la primera corrida
    assert result_1.value == 1.0, "Debe haber 1 falla en la ventana [30, 90]"
    # Verificamos que el inicio de la ventana sea 90 - 60 = 30 segundos después del basetime
    expected_oldest_1 = basetime + datetime.timedelta(seconds=90 - WINDOW_SECONDS)
    # Comparamos solo la diferencia temporal, permitiendo una pequeña tolerancia de segundos
    assert (result_1.oldest_considered - expected_oldest_1).total_seconds() < 1 
    
    # --- Batch 2: T=100 (FAIL) ---
    # newest_timestamp = 100.0
    # Ventana esperada: [40.0, 100.0] -> Fallas en T=90 y T=100. 2 fallas
    with open(source / "batch_2.json", "w") as file:
        json.dump(
            [
                # Evento 3: FAIL, T=100
                {
                    "service": "monitoring",
                    "timestamp": (
                        basetime + datetime.timedelta(seconds=100)
                    ).timestamp(),
                    "message": "HTTP Status Code: 503",
                },
            ],
            file,
        )

    # Consumir el segundo resultado
    result_2 = next(generator)
    
    # Asertos para la segunda corrida
    assert result_2.value == 2.0, "Debe haber 2 fallas en la ventana [40, 100]"
    # Verificamos que el inicio de la ventana sea 100 - 60 = 40 segundos después del basetime
    expected_oldest_2 = basetime + datetime.timedelta(seconds=100 - WINDOW_SECONDS)
    assert (result_2.oldest_considered - expected_oldest_2).total_seconds() < 1
    
    # --- Batch 3: T=155 (FAIL) ---
    # newest_timestamp = 155.0
    # Ventana esperada: [95.0, 155.0] -> Falla en T=100. La falla de T=90 queda fuera. 1 falla
    with open(source / "batch_3.json", "w") as file:
        json.dump(
            [
                # Evento 4: FAIL, T=155
                {
                    "service": "monitoring",
                    "timestamp": (
                        basetime + datetime.timedelta(seconds=155)
                    ).timestamp(),
                    "message": "HTTP Status Code: 504",
                },
            ],
            file,
        )
        
    # Consumir el tercer resultado
    result_3 = next(generator)
    
    # Asertos para la tercera corrida
    assert result_3.value == 2.0, "Debe haber 2 fallas en la ventana [95, 155] (T=100 y T=155)"
    # Verificamos que el inicio de la ventana sea 155 - 60 = 95 segundos después del basetime
    expected_oldest_3 = basetime + datetime.timedelta(seconds=155 - WINDOW_SECONDS)
    assert (result_3.oldest_considered - expected_oldest_3).total_seconds() < 1
    
    # Detener el generador para una salida limpia, aunque pytest lo manejará.
    stop_event.set()