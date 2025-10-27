import polars as pl
from typing import Optional
import argparse
import sys
import os # Importamos os para manejar rutas

# Expresión regular para extraer el código HTTP del mensaje
_STATUS_RE = r'HTTP Status Code:\s*(\d+)'

def process_data_lazy(
    source_folder: str, # Cambiamos el nombre del parámetro para mayor claridad
    *,
    window_duration: str,
    slide_duration: Optional[str] = None,
    watermark: Optional[str] = None, 
    max_files_per_trigger: Optional[int] = None,
) -> pl.LazyFrame:
    """
    Procesa logs de servicios para calcular la tasa de éxito en ventanas de tiempo.
    El 'source_folder' es una carpeta que contiene múltiples archivos JSON.
    """
    
    # --- Cambio clave aquí: Construir el patrón glob ---
    # Polars necesita un patrón glob (ej: 'data/*.json') para leer múltiples archivos.
    # El método os.path.join() crea la ruta de forma segura en cualquier sistema operativo.
    # Si la carpeta es '.', el patrón será './*.json'
    # Si la carpeta es 'data', el patrón será 'data/*.json'
    json_pattern = os.path.join(source_folder, "*.json")
    
    print(f"Buscando archivos con el patrón: {json_pattern}")
    
    # 1. Carga de datos de forma Lazy
    try:
        # Usamos el patrón glob para escanear todos los archivos JSON en la carpeta
        raw_lf = pl.scan_json(json_pattern)
    except Exception as e:
        # Capturamos errores si no encuentra archivos o hay un error de I/O
        print(f"Error: No se pudo escanear archivos JSON en '{json_pattern}'. Asegúrate de que la ruta de la carpeta es correcta y contiene archivos JSON. Detalles: {e}", file=sys.stderr)
        sys.exit(1)

    # El resto de la lógica de Polars permanece igual...
    
    slide = slide_duration if slide_duration is not None else window_duration
    
    parsed_lf = (
        raw_lf
        .with_columns([
            pl.col('message')
              .str.extract(pattern=_STATUS_RE, group_index=1)
              .cast(pl.Int32)
              .alias('status'),
            
            pl.from_epoch(pl.col('timestamp'), time_unit='s')
              .alias('event_time'),
        ])
        .drop_nulls(subset=['service', 'status', 'event_time'])
        
        .with_columns([
            (pl.col('status') < 400).cast(pl.Int32).alias('is_success'),
        ])
    )

    windowed_lf = (
        parsed_lf
        .group_by_dynamic(
            index="event_time",
            every=slide,
            period=window_duration,
            closed='left',
            group_by=['service'],
        )
        .agg([
            pl.count().alias('total'),
            pl.sum('is_success').alias('successes'),
        ])
        .with_columns([
            (pl.col('successes') / pl.col('total')).cast(pl.Float64).alias('success_rate'),
            pl.col('event_time').alias('window_start'),
            (pl.col('event_time') + pl.duration(window_duration)).alias('window_end')
        ])
        .select([
            'service', 
            'window_start', 
            'window_end', 
            'total', 
            'successes', 
            'success_rate'
        ])
        .sort(['window_start', 'service'])
    )

    return windowed_lf

# ---------------------------------------------
# PARTE DE EJECUCIÓN DEL SCRIPT
# ---------------------------------------------

def main():
    """Configura el analizador de argumentos y ejecuta el plan Lazy de Polars."""
    parser = argparse.ArgumentParser(
        description="Calcula la tasa de éxito de servicios en ventanas de tiempo usando Polars LazyFrame."
    )
    
    # Argumento posicional obligatorio para la ruta de la CARPETA
    parser.add_argument(
        'source_folder', # Renombrado para claridad
        type=str,
        help='Ruta de la carpeta que contiene los archivos JSON de log. Polars buscará todos los archivos "*.json" dentro.'
    )
    
    # Argumentos opcionales con valores predeterminados
    parser.add_argument(
        '--window_duration',
        type=str,
        default='10s',
        help='Duración de la ventana de tiempo (ej: "10s", "1m"). Valor predeterminado: 10s.'
    )
    parser.add_argument(
        '--slide_duration',
        type=str,
        default='10s',
        help='El paso o "slide" de la ventana. Valor predeterminado: 10s.'
    )
    
    args = parser.parse_args()

    # 1. Definir el plan de ejecución Lazy
    print(f"Procesando archivos en la carpeta: {args.source_folder}")
    
    lazy_plan = process_data_lazy(
        args.source_folder, # Pasamos la carpeta
        window_duration=args.window_duration,
        slide_duration=args.slide_duration
    )

    # 2. Ejecutar el plan y obtener el resultado
    try:
        df_result = lazy_plan.collect()
        
        # 3. Mostrar los resultados
        print("\n--- Resultados (Tasa de Éxito por Ventana) ---")
        print(df_result)
        
    except Exception as e:
        print(f"\nError durante la ejecución del plan de Polars: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()