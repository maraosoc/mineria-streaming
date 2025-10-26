import datetime
import json
import pathlib
import threading
import time
from typing import TYPE_CHECKING, Any

# Importaciones del código fuente
from src.task_1 import compute

# Para asegurar el tipado correcto de Result
if TYPE_CHECKING:
    from src.domain import Result
else:
    from src.domain import Result


# ---------------------------------------------------------------------
# Test principal
# ---------------------------------------------------------------------
def test_streaming_log_aggregator(tmp_path: pathlib.Path) -> None:
    """
    Prueba el procesamiento incremental de logs de streaming.
    Valida la métrica (tasa de éxito) y los límites de tiempo de la ventana acumulada.
    """
    source = tmp_path / "source_logs"
    source.mkdir(parents=True, exist_ok=True)

    # Establecemos una fecha/hora fija para evitar inconsistencias con datetime.now()
    basetime = datetime.datetime(2025, 10, 26, 17, 0, 0)

    # --- SETUP BATCH 1 ---
    t1_oldest_ts = (basetime + datetime.timedelta(seconds=48)).timestamp()
    t2_newest_ts = (basetime + datetime.timedelta(seconds=96)).timestamp()

    with open(source / "batch_1.json", "w") as file:
        json.dump(
            [
                {
                    "service": "monitoring",
                    "timestamp": t1_oldest_ts,
                    "message": "HTTP Status Code: 200",
                },
                {
                    "service": "monitoring",
                    "timestamp": t2_newest_ts,
                    "message": "HTTP Status Code: 500",
                },
            ],
            file,
        )

    # Inicializar el procesador de streaming
    stop = threading.Event()
    generator = compute(str(source), stop=stop)

    # Espera para permitir que el productor cargue el primer batch
    print("[TEST] Esperando 1.5s para que el Productor cargue el Batch 1...")
    time.sleep(1.5)

    # Procesar BATCH 1
    first_result = next(generator)

    # --- SETUP BATCH 2 ---
    t3_newest_ts = (basetime + datetime.timedelta(seconds=144)).timestamp()

    with open(source / "batch_2.json", "w") as file:
        json.dump(
            [
                {
                    "service": "monitoring",
                    "timestamp": t3_newest_ts,
                    "message": "HTTP Status Code: 200",
                },
            ],
            file,
        )

    # Espera para permitir que el productor cargue el segundo batch
    print("[TEST] Esperando 2.5s para que el Productor cargue el Batch 2...")
    time.sleep(2.5)

    # Procesar BATCH 2
    second_result = next(generator)

    # -----------------------------------------------------------------
    # VALIDACIONES
    # -----------------------------------------------------------------

    # Resultado 1: Solo Batch 1 procesado
    assert first_result == Result(
        value=0.5,
        newest_considered=datetime.datetime.fromtimestamp(t2_newest_ts),
        oldest_considered=datetime.datetime.fromtimestamp(t1_oldest_ts),
    ), "El primer resultado no refleja la tasa y ventana de tiempo correctas del Batch 1."

    # Resultado 2: Batch 1 + Batch 2 (acumulado)
    assert second_result == Result(
        value=(2 / 3),
        newest_considered=datetime.datetime.fromtimestamp(t3_newest_ts),
        oldest_considered=datetime.datetime.fromtimestamp(t1_oldest_ts),
    ), "El segundo resultado no refleja la tasa y ventana de tiempo correctas de la acumulación."

    # Detener el generador
    stop.set()
