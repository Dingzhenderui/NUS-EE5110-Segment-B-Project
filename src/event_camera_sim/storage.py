"""Streaming persistence helpers for event data."""

import json
from pathlib import Path

import h5py
import numpy as np


EVENT_DTYPES = {
    "x": np.int32,
    "y": np.int32,
    "t": np.float64,
    "p": np.int8,
}


class HDF5EventWriter:
    """Append time-ordered event batches to one compressed HDF5 file."""

    def __init__(self, output_path, chunk_events, attributes=None):
        if chunk_events <= 0:
            raise ValueError("HDF5 chunk size must be greater than zero")

        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = h5py.File(self.output_path, "w")
        self._datasets = {
            name: self._file.create_dataset(
                name,
                shape=(0,),
                maxshape=(None,),
                chunks=(int(chunk_events),),
                dtype=dtype,
                compression="lzf",
                shuffle=True,
            )
            for name, dtype in EVENT_DTYPES.items()
        }
        self.event_count = 0
        self._last_timestamp = None
        self._closed = False

        self._file.attrs["format"] = "EE5110 event list"
        self._file.attrs["time_unit"] = "seconds"
        self._file.attrs["compression"] = "LZF with shuffle"
        self._file.attrs["chunk_events"] = int(chunk_events)
        self._file.attrs["event_count"] = 0
        self._file.attrs["status"] = "incomplete"
        for name, value in (attributes or {}).items():
            if value is not None:
                self._file.attrs[name] = value

    def append(self, events):
        """Append one event batch after checking lengths and time ordering."""

        if self._closed:
            raise RuntimeError("Cannot append to a closed HDF5 event file")
        missing = set(EVENT_DTYPES) - set(events)
        if missing:
            raise ValueError(f"Event batch is missing fields: {sorted(missing)}")

        event_count = len(events["t"])
        if any(len(events[name]) != event_count for name in EVENT_DTYPES):
            raise ValueError("Event fields must all have the same length")
        if event_count == 0:
            return

        timestamps = np.asarray(events["t"], dtype=np.float64)
        if np.any(timestamps[1:] < timestamps[:-1]):
            raise ValueError("Events within each batch must be time ordered")
        if (
            self._last_timestamp is not None
            and timestamps[0] < self._last_timestamp
        ):
            raise ValueError("Event batches must be appended in time order")

        start = self.event_count
        end = start + event_count
        for name, dataset in self._datasets.items():
            dataset.resize((end,))
            dataset[start:end] = np.asarray(events[name], dtype=EVENT_DTYPES[name])

        self.event_count = end
        self._last_timestamp = float(timestamps[-1])

    def flush(self):
        if self._closed:
            return
        self._file.attrs["event_count"] = self.event_count
        self._file.flush()

    def close(self, status="complete"):
        if self._closed:
            return
        self._file.attrs["event_count"] = self.event_count
        self._file.attrs["status"] = status
        self._file.flush()
        self._file.close()
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close("complete" if exc_type is None else "incomplete")


def inspect_event_file(input_path):
    """Check the completed HDF5 file without loading all events into RAM."""

    input_path = Path(input_path)
    if not input_path.is_file():
        raise FileNotFoundError(f"Event file does not exist: {input_path}")

    with h5py.File(input_path, "r") as file:
        missing = set(EVENT_DTYPES) - set(file.keys())
        if missing:
            raise RuntimeError(f"HDF5 event file is missing: {sorted(missing)}")
        lengths = {name: len(file[name]) for name in EVENT_DTYPES}
        if len(set(lengths.values())) != 1:
            raise RuntimeError(f"HDF5 event fields have different lengths: {lengths}")
        event_count = next(iter(lengths.values()))
        if int(file.attrs.get("event_count", -1)) != event_count:
            raise RuntimeError("HDF5 event_count attribute does not match its datasets")
        if file.attrs.get("status") != "complete":
            raise RuntimeError("HDF5 event file is not marked complete")
        return {
            "event_count": event_count,
            "time_unit": str(file.attrs.get("time_unit", "")),
            "compression": str(file.attrs.get("compression", "")),
        }


def iter_event_chunks(input_path, chunk_events=262_144):
    """Yield event dictionaries without loading the complete HDF5 file."""

    if chunk_events <= 0:
        raise ValueError("Read chunk size must be greater than zero")

    input_path = Path(input_path)
    if not input_path.is_file():
        raise FileNotFoundError(f"Event file does not exist: {input_path}")

    with h5py.File(input_path, "r") as file:
        missing = set(EVENT_DTYPES) - set(file.keys())
        if missing:
            raise RuntimeError(f"HDF5 event file is missing: {sorted(missing)}")
        event_count = len(file["t"])
        for start in range(0, event_count, chunk_events):
            end = min(start + chunk_events, event_count)
            yield {name: file[name][start:end] for name in EVENT_DTYPES}


def save_events_csv(events, output_path):
    """Save the collected human-readable event sample to CSV."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sample = np.column_stack(
        (events["x"], events["y"], events["t"], events["p"])
    )
    np.savetxt(
        output_path,
        sample,
        delimiter=",",
        header="x,y,t,p",
        comments="",
        fmt=["%d", "%d", "%.9f", "%d"],
    )


def load_events_npz(input_path):
    """Load a legacy NPZ output created by an earlier project version."""

    input_path = Path(input_path)
    if not input_path.is_file():
        raise FileNotFoundError(f"Event file does not exist: {input_path}")

    with np.load(input_path) as data:
        return {name: data[name].copy() for name in EVENT_DTYPES}


def save_metadata(metadata, output_path):
    """Save human-readable information about one experiment."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)
        file.write("\n")
