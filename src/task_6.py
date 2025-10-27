from __future__ import annotations
import queue as _q
import threading
from typing import Optional
from pyspark.sql import SparkSession, DataFrame, functions as F, types as T
import datetime
from typing import NamedTuple, TypedDict


class Result(NamedTuple):
    value: float
    newest_considered: datetime.datetime
    oldest_considered: datetime.datetime


class Events(TypedDict):
    service: str
    timestamp: float
    message: str


def compute(
    source: str,
    stop: threading.Event,
    *,
    checkpoint: str,
    processing_time: str = '1 second',
    window_duration: str = '10 seconds',
    slide_duration: str = '10 seconds',
    watermark: str = '30 seconds',
    max_files_per_trigger: int = 10
):
    spark = (
        SparkSession.builder
        .appName('task_6.compute_success_rate')
        .config('spark.sql.session.timeZone', 'UTC')
        .getOrCreate()
    )

    outbox: _q.Queue = _q.Queue()

    def _foreach_batch(df, batch_id):
        if df.rdd.isEmpty():
            return

        rows = df.select(
            'service', 'window_start', 'window_end', 'total', 'successes', 'success_rate'
        ).collect()

        for r in rows:
            outbox.put(
                Result(
                    value=float(r['success_rate']) if r['success_rate'] is not None else 0.0,
                    newest_considered=r['window_end'],
                    oldest_considered=r['window_start'],
                )
            )

    try:
        sdf = producer(
            spark,
            source,
            window_duration=window_duration,
            slide_duration=slide_duration,
            watermark=watermark,
            max_files_per_trigger=max_files_per_trigger,
        )

        query = (
            sdf.writeStream
            .foreachBatch(_foreach_batch)
            .outputMode('complete')
            .option('checkpointLocation', checkpoint)
            .trigger(processingTime=processing_time)
            .start()
        )

        while True:
            if stop.is_set() and outbox.empty():
                break
            try:
                item = outbox.get(timeout=0.25)
                yield item
            except _q.Empty:
                pass

        query.stop()
        query.awaitTermination(5)

    finally:
        spark.stop()


# =====================
#   CONFIGURACIÓN BASE
# =====================

_STATUS_RE = r'HTTP Status Code:\s*(\d+)'

_SCHEMA = T.StructType([
    T.StructField('service', T.StringType(), nullable=False),
    T.StructField('timestamp', T.DoubleType(), nullable=False),
    T.StructField('message', T.StringType(), nullable=False),
])


def producer(
    spark: SparkSession,
    source: str,
    *,
    window_duration: str,
    slide_duration: Optional[str],
    watermark: str,
    max_files_per_trigger: int,
) -> DataFrame:
    raw = (
        spark.readStream.format('json')
        .schema(_SCHEMA)
        .option('maxFilesPerTrigger', max_files_per_trigger)
        .option('pathGlobFilter', '*.json')
        .option('recursiveFileLookup', 'true')
        .load(source)
    )

    parsed = (
        raw.withColumn('status', F.regexp_extract('message', _STATUS_RE, 1).cast('int'))
        .withColumn('event_time', F.to_timestamp(F.from_unixtime(F.col('timestamp'))))
        .dropna(subset=['service', 'status', 'event_time'])
        .withColumn('is_success', (F.col('status') < 400).cast('int'))
    )

    windowed = (
        parsed.withWatermark('event_time', watermark)
        .groupBy(
            F.window(F.col('event_time'), window_duration, slide_duration),
            F.col('service'),
        )
        .agg(
            F.count(F.lit(1)).alias('total'),
            F.sum('is_success').alias('successes'),
        )
        .withColumn('success_rate', (F.col('successes') / F.col('total')).cast('double'))
        .select(
            F.col('window.start').alias('window_start'),
            F.col('window.end').alias('window_end'),
            'service',
            'total',
            'successes',
            'success_rate',
        )
        .orderBy(F.col('window_start').asc(), F.col('service').asc())
    )

    return windowed


# =====================
#  EJECUCIÓN DIRECTA
# =====================
if __name__ == "__main__":
    import time
    import os

    # Ruta de prueba: cambia esto por la carpeta donde tienes tus JSONs
    SOURCE_DIR = os.path.abspath("data/input")
    CHECKPOINT_DIR = os.path.abspath("data/checkpoint")

    os.makedirs(SOURCE_DIR, exist_ok=True)
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)

    stop_event = threading.Event()

    print("🚀 Iniciando streaming... Ctrl+C para detener.\nLeyendo JSONs desde:", SOURCE_DIR)

    try:
        for result in compute(SOURCE_DIR, stop_event, checkpoint=CHECKPOINT_DIR):
            print(f"✅ Service success rate: {result.value:.2%} | Window: {result.oldest_considered} - {result.newest_considered}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Deteniendo el streaming...")
        stop_event.set()
