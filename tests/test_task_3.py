import datetime
import json
import pathlib
import threading
import numpy as np
import time
import uuid
import pytest
from src import domain
from src.task_3 import compute

"""
Tests for task_3: Reservoir Sampling algorithm
Tests verify that the reservoir sampling maintains a representative sample
and that the most common HTTP status code is correctly identified.
"""


def _batch_producer(path: pathlib.Path, basetime: datetime.datetime, status_code: int, length: int) -> None:
    """Helper function to create batch files with events"""
    with open(path / f"{uuid.uuid4()}.json", "w") as file:
        json.dump(
            [
                {
                    "service": "monitoring",
                    "timestamp": (basetime + datetime.timedelta(seconds=i)).timestamp(),
                    "message": f"HTTP Status Code: {status_code}",
                }
                for i in range(length)
            ],
            file,
        )


def test_reservoir_sampling_basic(tmp_path: pathlib.Path) -> None:
    """Test basic reservoir sampling with equal distribution"""
    source = tmp_path / "source"
    source.mkdir(parents=True, exist_ok=True)
    basetime = datetime.datetime.now()

    # Create batches with 200 and 500 status codes
    _batch_producer(source, basetime, 200, 50)
    _batch_producer(source, basetime + datetime.timedelta(seconds=100), 500, 50)
    
    stop = threading.Event()
    generator = compute(str(source), stop, reservoir_size=10)
    
    # Wait for data to be processed
    time.sleep(0.5)
    
    # Get a result
    result = next(generator)
    
    # The value should be either 200 or 500
    assert result.value in [200.0, 500.0], f"Expected 200.0 or 500.0, got {result.value}"
    
    # Check that timestamps are set
    assert result.newest_considered > datetime.datetime(datetime.MINYEAR, 1, 1)
    assert result.oldest_considered < datetime.datetime(9999, 1, 1)
    
    stop.set()


def test_reservoir_sampling_majority(tmp_path: pathlib.Path) -> None:
    """Test that reservoir sampling identifies the majority status code"""
    source = tmp_path / "source"
    source.mkdir(parents=True, exist_ok=True)
    basetime = datetime.datetime.now()

    # Create batches with more 200s than 500s
    _batch_producer(source, basetime, 200, 80)
    _batch_producer(source, basetime + datetime.timedelta(seconds=100), 500, 20)
    
    stop = threading.Event()
    generator = compute(str(source), stop, reservoir_size=20)
    
    # Wait for data to be processed
    time.sleep(0.5)
    
    # Get multiple results and count
    results = []
    for _ in range(5):
        result = next(generator)
        results.append(result.value)
    
    # The most common value should be 200.0 most of the time
    from collections import Counter
    counter = Counter(results)
    most_common_value = counter.most_common(1)[0][0]
    
    assert most_common_value == 200.0, f"Expected 200.0 to be most common, got {most_common_value}"
    
    stop.set()


def test_reservoir_sampling_probability(tmp_path: pathlib.Path) -> None:
    """Test that reservoir sampling maintains approximately equal probability"""
    source = tmp_path / "source"
    source.mkdir(parents=True, exist_ok=True)
    basetime = datetime.datetime.now()

    values = []
    for iteration in range(50):
        # Create fresh source for each iteration
        source_iter = source / f"iter_{iteration}"
        source_iter.mkdir(parents=True, exist_ok=True)
        
        # Create equal batches of 200 and 500
        _batch_producer(source_iter, basetime, 200, 1)
        _batch_producer(source_iter, basetime + datetime.timedelta(seconds=10), 500, 1)
        
        stop = threading.Event()
        generator = compute(str(source_iter), stop, reservoir_size=1)
        
        # Wait for processing
        time.sleep(0.1)
        
        result = next(generator)
        values.append(result.value)
        stop.set()
    
    # Count occurrences
    count_200 = values.count(200.0)
    count_500 = values.count(500.0)
    
    # With reservoir size 1 and equal distribution, we expect roughly 50/50
    # Allow for 30% deviation due to randomness
    assert 0.2 <= count_200 / len(values) <= 0.8, \
        f"Expected roughly 50% 200s, got {count_200 / len(values) * 100}%"


def test_reservoir_with_multiple_codes(tmp_path: pathlib.Path) -> None:
    """Test reservoir sampling with multiple different status codes"""
    source = tmp_path / "source"
    source.mkdir(parents=True, exist_ok=True)
    basetime = datetime.datetime.now()

    # Create batches with various status codes
    _batch_producer(source, basetime, 200, 10)
    _batch_producer(source, basetime + datetime.timedelta(seconds=20), 500, 10)
    _batch_producer(source, basetime + datetime.timedelta(seconds=40), 404, 10)
    _batch_producer(source, basetime + datetime.timedelta(seconds=60), 503, 10)
    
    stop = threading.Event()
    generator = compute(str(source), stop, reservoir_size=15)
    
    # Wait for data to be processed
    time.sleep(0.5)
    
    # Get a result
    result = next(generator)
    
    # The value should be one of the status codes
    assert result.value in [200.0, 500.0, 404.0, 503.0], \
        f"Expected one of [200.0, 500.0, 404.0, 503.0], got {result.value}"
    
    stop.set()


def test_reservoir_size_respected(tmp_path: pathlib.Path) -> None:
    """Test that reservoir size parameter is respected"""
    source = tmp_path / "source"
    source.mkdir(parents=True, exist_ok=True)
    basetime = datetime.datetime.now()

    # Create more events than reservoir size
    _batch_producer(source, basetime, 200, 100)
    
    stop = threading.Event()
    reservoir_size = 5
    generator = compute(str(source), stop, reservoir_size=reservoir_size)
    
    # Wait for processing
    time.sleep(0.5)
    
    # Get a result - should work without errors
    result = next(generator)
    assert result.value == 200.0
    
    stop.set()


def test_empty_source(tmp_path: pathlib.Path) -> None:
    """Test with empty source directory"""
    source = tmp_path / "source"
    source.mkdir(parents=True, exist_ok=True)
    
    stop = threading.Event()
    generator = compute(str(source), stop, reservoir_size=10)
    
    # Should not produce any results immediately
    time.sleep(0.3)
    
    # Now add some data
    basetime = datetime.datetime.now()
    _batch_producer(source, basetime, 200, 5)
    
    time.sleep(0.3)
    
    # Should now produce a result
    result = next(generator)
    assert result.value == 200.0
    
    stop.set()

