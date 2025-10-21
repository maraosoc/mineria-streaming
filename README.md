# Streaming Data Processing Lab
> Realizado por: Manuela Ramos Ospina, Paula Andrea Pirela Rios y Carlos Eduardo Baez Coronado
Este proyecto implementa diferentes enfoques para procesar flujos de datos (streams) en tiempo real, simulando un sistema que recibe logs de múltiples microservicios.
Cada tarea implementa una técnica distinta de análisis incremental o probabilístico sobre datos en continuo crecimiento.
## Estructura del Repositorio

```
├── data/                    # Carpeta donde se almacenan los datos JSON de entrada
│
├── scripts/
│   └── generator.py         # Generador de archivos JSON simulando streams de logs
│
├── src/                     # Código fuente principal
│   ├── __init__.py
│   ├── domain.py            # Definición de entidades y lógica compartida
│   ├── main.py              # Script principal para ejecutar las tareas
│   ├── task_1.py            # Tarea 1: Promedios acumulados (Running Averages)
│   ├── task_2.py            # Tarea 2: Ventanas deslizantes (Sliding Windows)
│   ├── task_3.py            # Tarea 3: Muestreo aleatorio (Reservoir Sampling)
│   └── task_4.py            # Tarea 4: Filtro de Bloom (Bloom Filter)
│
├── tests/                   # Pruebas unitarias para cada tarea
│   ├── __init__.py
│   ├── test_task_1.py
│   ├── test_task_2.py
│   ├── test_task_3.py
│   └── test_task_4.py
│
├── compose.yml              # Configuración para ejecución en contenedores
├── Dockerfile               # Imagen base del proyecto
├── script.Dockerfile        # Imagen secundaria para generación o pruebas
├── pyproject.toml           # Dependencias y configuración del proyecto
├── uv.lock                  # Archivo de bloqueo de dependencias
└── README.md                # Este archivo
```
## Resumen de Tareas
| Tarea | Descripción                                                                                  | Archivo fuente  | Prueba unitaria        |
| :---- | :------------------------------------------------------------------------------------------- | :-------------- | :--------------------- |
| **1** | Cálculo incremental del promedio de peticiones exitosas por servicio.                        | `src/task_1.py` | `tests/test_task_1.py` |
| **2** | Cómputo de la tasa de errores en ventanas deslizantes de 1 minuto.                           | `src/task_2.py` | `tests/test_task_2.py` |
| **3** | Implementación del algoritmo *Reservoir Sampling* para identificar el código HTTP más común. | `src/task_3.py` | `tests/test_task_3.py` |
| **4** | Implementación de un *Bloom Filter* para filtrar mensajes de interés en flujos masivos.      | `src/task_4.py` | `tests/test_task_4.py` |

## Instrucciones de ejecución
1. Crear entorno virtual e instalar dependencias:
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Generar datos de prueba:
   ```bash
   python scripts/generator.py --output_dir data/ --num_files 10 --events_per_file 1000
   ```
3. Ejecutar las tareas:
   ```bash
   python src/main.py --task 1 --data_dir data/
   ```
## Pruebas unitarias
Cada tarea incluye su propio módulo de test.
Ejecuta todos los tests con:
```bash
pytest -v
```
O para una tarea especifica:
```bash
pytest tests/test_task_1.py -v
```
## Docker
Compila y ejecuta el proyecto usando Docker:
```bash
docker compose up --build
```
Para levantar los servicios definidos en `compose.yml`.
---
# Streaming Data Analysis - Teacher explanation

## Introduction

You are working on a system that aggregates logs from multiple microservices. For each log is registered as an event containing the following information:

* The service name
* The timestamp when it occurred
* An *almost* arbitrary message about what happened.

In principle, the message can be arbitrary, the developer picks the message they want to log at anytime to help them debug. However, logging the status code of the response of any microservice is standarized so that they all look like HTTP Status Code: XXX. This way you can easily compare different services and see which one has more errors.

The data source for the task is going to be a directory in which JSON files are stored. Each JSON file looks like:

```json
{"service": "monitoring", "timestamp": 1745319168.057018, "message": "HTTP Status Code: 200"}
```

## Task 1: Running Averages

This is the simplest way to compute statistics overan ever growing dataset. You need to figure out a way to compute statistics about your data by delaying the execution of formulas that require information about a dataset. Recall that the formular for computing an average is:

$$
\bar{x} = \frac{1}{n} \sum_{i=1}^{n} x_i
$$

Where $n$ is the number of elements in the dataset and $x_i$ is the $i$-th element in the dataset. Now, you could keep two counters, one for the number of elements and one for the sum of the elements. Then, you could compute the average by dividing the sum by the number of elements at that point in time, the formula would be like:

$$
\bar{x}_t = \frac{1}{n_t} \sum_{i=1}^{n_t} x_i
$$

It is important to highlight that you compute statistics up to a point with this method.

For this task you need to implement an algorithm that allows you to compute the average number of successful requests per service.


## Task 2: Sliding Windows

There are some statistics that are relevant over a certain period of time. For example, you might want to compute the average number of unsuccessful requests over the last 10 minutes. To do this, you can use a sliding window: keep track of records over a fixed period of time and compute the statistics over those records that you allow yourself to keep in memory.

Implement an sliding window algorithm that allows you to compute the **rate of unsuccessful requests** over the last minute.


## Task 3: Sampling

There are situations in which we need to take samples of the data to be able to compute any statistic. However, when working with streaming data, you need to keep into account that the full set of elements for which you want to compute statistics is not available. Let's say you want need a sample and you want to make sure that the sample is representative of the full dataset; how do you ensure that the samples are chosen in a truly random way?

Your task now is to implement the Reservoir Sampling algorithm to figure out *the most commong HTTP Status Code in the dataset*. Here is another reference: https://medium.com/pythoneers/dipping-into-data-streams-the-magic-of-reservoir-sampling-762f41b78781


## Task 4: Filtering

Our system is connected to a lot of services, all of them generating a lot of logs. However, there are some type of messages in the logs, for which we are specially interested. Those messages for which we are interested, should be sent to another system (e.g. a database).

Let's say we have a list of messages that we are interested in and they are stored in a file, but the file is too big to fit in memmory. Use the [Bloom Filter](https://en.wikipedia.org/wiki/Bloom_filter) technique to decide whether those messages should be forwarded to antoher system or not.

## Task 5: Polars Streaming

Polars can handle streaming data by using the LazyFrame interface. Read its documentation and propose some statistics that you can compute with its API. Feel free to decide which set of statistics are interesting to compute with this approach and explain why you chose those. References:

* https://docs.pola.rs/user-guide/concepts/streaming/ 
* https://urbandataengineer.substack.com/p/big-data-small-machine-the-magic/
* https://www.rhosignal.com/posts/streaming-in-polars/
* https://www.rhosignal.com/posts/streaming-operations-in-polars/ 

## Task 6: Spark Streaming

Spark can handle streaming data by using the Structured Streaming API. Read its documentation and propose some statistics that you can compute with its API. Feel free to decide which set of statistics are interesting to compute with this approach and explain why you chose those. References:
* https://spark.apache.org/docs/latest/streaming-programming-guide.html
* https://spark.apache.org/docs/latest/streaming/getting-started.html 
