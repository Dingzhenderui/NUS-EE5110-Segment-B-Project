"""The complete high-frame-rate-video to events workflow."""

from datetime import datetime
import os
from pathlib import Path
from time import perf_counter

import numpy as np

from . import config
from .events import EVENT_DTYPES, EventSimulator
from .storage import (
    HDF5EventWriter,
    inspect_event_file,
    save_events_csv,
    save_metadata,
)
from .video import VideoReader
from .visualization import StreamingEventVisualizer


RAW_EVENT_BYTES = sum(np.dtype(dtype).itemsize for dtype in EVENT_DTYPES.values())


def _format_parameter(value):
    return format(float(value), ".10g")


def _format_count(value):
    return f"{int(value):,}"


def _format_bytes(value):
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024.0 or unit == "TiB":
            return f"{size:.2f} {unit}"
        size /= 1024.0


def build_output_paths(video_path):
    """Build deterministic paths for one video and parameter combination."""

    parameter_tag = (
        f"pos{_format_parameter(config.CONTRAST_THRESHOLD_POS)}_"
        f"neg{_format_parameter(config.CONTRAST_THRESHOLD_NEG)}_"
        f"eps{_format_parameter(config.EPSILON)}_"
        f"ts{_format_parameter(config.TIMESTAMP_RESOLUTION)}_"
        f"acc{_format_parameter(config.ACCUMULATION_TIME)}_"
        f"snap{_format_parameter(config.SNAPSHOT_START_TIME)}-"
        f"{_format_parameter(config.SNAPSHOT_DURATION)}_"
        f"view{_format_parameter(config.OVERLAY_PLAYBACK_FPS)}_"
        f"alpha{_format_parameter(config.OVERLAY_EVENT_ALPHA)}"
    )
    result_dir = config.OUTPUT_DIR / video_path.stem / parameter_tag
    return {
        "directory": result_dir,
        "h5": result_dir / "events.h5",
        "h5_partial": result_dir / "events.partial.h5",
        "csv": result_dir / "events_sample.csv",
        "csv_partial": result_dir / "events_sample.partial.csv",
        "snapshot": result_dir / "event_snapshot.png",
        "snapshot_partial": result_dir / "event_snapshot.partial.png",
        "overlay": result_dir / "event_overlay.mp4",
        "overlay_partial": result_dir / "event_overlay.partial.mp4",
        "metadata": result_dir / "metadata.json",
        "metadata_partial": result_dir / "metadata.partial.json",
    }


def _collect_sample(sample_parts, events, collected, limit):
    remaining = limit - collected
    sample_count = min(remaining, len(events["t"]))
    if sample_count <= 0:
        return collected
    for name in EVENT_DTYPES:
        sample_parts[name].append(events[name][:sample_count].copy())
    return collected + sample_count


def _combine_sample(sample_parts):
    return {
        name: (
            np.concatenate(parts)
            if parts
            else np.empty(0, dtype=EVENT_DTYPES[name])
        )
        for name, parts in sample_parts.items()
    }


def _replace_output(partial_path, final_path):
    partial_path = Path(partial_path)
    if not partial_path.is_file():
        raise RuntimeError(f"Expected output was not created: {partial_path}")
    os.replace(partial_path, final_path)


def _build_metadata(
    video_path,
    info,
    output_paths,
    status,
    warnings,
    processed_frames,
    total_events,
    timings,
    hdf5_size,
    snapshot_event_count,
    error=None,
):
    elapsed = max(float(timings.get("total_seconds", 0.0)), 1e-12)
    metadata = {
        "status": status,
        "input_video": video_path.name,
        "input_path": video_path.relative_to(config.PROJECT_ROOT).as_posix(),
        "video": info,
        "model": {
            "type": "ideal noise-free contrast-threshold model",
            "interpolation": "linear between consecutive frames",
            "timestamp_unit": "seconds",
            "timestamp_resolution": config.TIMESTAMP_RESOLUTION,
            "noise_simulation": False,
        },
        "parameters": {
            "contrast_threshold_pos": config.CONTRAST_THRESHOLD_POS,
            "contrast_threshold_neg": config.CONTRAST_THRESHOLD_NEG,
            "epsilon": config.EPSILON,
            "timestamp_resolution": config.TIMESTAMP_RESOLUTION,
            "accumulation_time": config.ACCUMULATION_TIME,
            "snapshot_start_time": config.SNAPSHOT_START_TIME,
            "snapshot_duration": config.SNAPSHOT_DURATION,
            "overlay_playback_fps": config.OVERLAY_PLAYBACK_FPS,
            "overlay_event_alpha": config.OVERLAY_EVENT_ALPHA,
            "low_fps_warning_threshold": config.LOW_FPS_WARNING,
        },
        "storage": {
            "format": "HDF5",
            "datasets": {
                name: np.dtype(dtype).name for name, dtype in EVENT_DTYPES.items()
            },
            "compression": "LZF with shuffle",
            "chunk_events": config.HDF5_CHUNK_EVENTS,
            "uncompressed_bytes_per_event": RAW_EVENT_BYTES,
            "hdf5_file_bytes": int(hdf5_size),
        },
        "result": {
            "processed_frames": int(processed_frames),
            "event_count": int(total_events),
            "snapshot_event_count": int(snapshot_event_count),
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        },
        "performance": {
            **{name: float(value) for name, value in timings.items()},
            "frames_per_second": processed_frames / elapsed,
            "events_per_second": total_events / elapsed,
        },
        "warnings": list(warnings),
        "files": {
            "events_hdf5": output_paths["h5"].name,
            "events_csv_sample": output_paths["csv"].name,
            "event_snapshot": output_paths["snapshot"].name,
            "event_overlay": output_paths["overlay"].name,
        },
    }
    if error is not None:
        metadata["error"] = str(error)
    return metadata


def _print_progress(
    processed_frames,
    frame_count,
    total_events,
    start_time,
    partial_h5_path,
):
    elapsed = max(perf_counter() - start_time, 1e-12)
    processing_fps = processed_frames / elapsed
    current_size = partial_h5_path.stat().st_size if partial_h5_path.is_file() else 0
    if frame_count > 0:
        scale = frame_count / processed_frames
        projected_events = int(total_events * scale)
        projected_size = int(current_size * scale)
        projection = (
            f", projected: {_format_count(projected_events)} events / "
            f"{_format_bytes(projected_size)}"
        )
    else:
        projection = ""

    print(
        f"Processed {processed_frames}/{frame_count or '?'} frames, "
        f"events: {_format_count(total_events)}, "
        f"speed: {processing_fps:.2f} frames/s, "
        f"HDF5: {_format_bytes(current_size)}{projection}",
        flush=True,
    )


def run(video_path):
    """Generate, stream, and visualize events from one selected video."""

    output_paths = build_output_paths(video_path)
    output_paths["directory"].mkdir(parents=True, exist_ok=True)
    reader = VideoReader(video_path)
    info = reader.get_info()
    warnings = []
    if info["fps"] < config.LOW_FPS_WARNING:
        warning = (
            f"Input FPS is {info['fps']:.2f}, below the project's "
            f"{config.LOW_FPS_WARNING:.0f} FPS warning threshold. Low FPS is "
            "supported, but frame interpolation is less reliable and each frame "
            "may produce a very large event batch."
        )
        warnings.append(warning)

    print("======================================")
    print("EE5110 Event Camera Simulator")
    print("======================================")
    print(f"Input:      {video_path}")
    print(f"Output:     {output_paths['directory']}")
    print(f"FPS:        {info['fps']:.2f}")
    print(f"Frames:     {info['frame_count']}")
    print(f"Resolution: {info['width']} x {info['height']}")
    for warning in warnings:
        print(f"[WARNING] {warning}")

    simulator = EventSimulator(
        config.CONTRAST_THRESHOLD_POS,
        config.CONTRAST_THRESHOLD_NEG,
        config.EPSILON,
        config.TIMESTAMP_RESOLUTION,
    )
    sample_parts = {name: [] for name in EVENT_DTYPES}
    sample_count = 0
    processed_frames = 0
    total_events = 0
    timings = {
        "event_generation_seconds": 0.0,
        "event_storage_seconds": 0.0,
        "visualization_seconds": 0.0,
        "finalization_seconds": 0.0,
        "total_seconds": 0.0,
    }
    writer = None
    visualizer = None
    start_time = perf_counter()

    try:
        writer = HDF5EventWriter(
            output_paths["h5_partial"],
            config.HDF5_CHUNK_EVENTS,
            attributes={
                "timestamp_resolution": config.TIMESTAMP_RESOLUTION,
                "contrast_threshold_pos": config.CONTRAST_THRESHOLD_POS,
                "contrast_threshold_neg": config.CONTRAST_THRESHOLD_NEG,
                "epsilon": config.EPSILON,
                "model": "ideal noise-free contrast-threshold model",
                "source_video": video_path.name,
            },
        )
        visualizer = StreamingEventVisualizer(
            info,
            output_paths["overlay_partial"],
            output_paths["snapshot_partial"],
            config.ACCUMULATION_TIME,
            config.SNAPSHOT_START_TIME,
            config.SNAPSHOT_DURATION,
            config.OVERLAY_PLAYBACK_FPS,
            config.OVERLAY_EVENT_ALPHA,
        )

        while True:
            frame, timestamp = reader.read_frame()
            if frame is None:
                break

            stage_start = perf_counter()
            events = simulator.process_frame(frame, timestamp)
            timings["event_generation_seconds"] += perf_counter() - stage_start
            event_count = len(events["t"])

            stage_start = perf_counter()
            writer.append(events)
            sample_count = _collect_sample(
                sample_parts,
                events,
                sample_count,
                config.EVENT_CSV_MAX_EVENTS,
            )
            timings["event_storage_seconds"] += perf_counter() - stage_start

            stage_start = perf_counter()
            visualizer.add_frame(frame, timestamp, events)
            timings["visualization_seconds"] += perf_counter() - stage_start

            total_events += event_count
            processed_frames += 1
            if processed_frames % config.PROGRESS_INTERVAL_FRAMES == 0:
                writer.flush()
                _print_progress(
                    processed_frames,
                    info["frame_count"],
                    total_events,
                    start_time,
                    output_paths["h5_partial"],
                )

        if processed_frames == 0:
            raise RuntimeError(f"No frames could be read from: {video_path}")
        if total_events == 0:
            raise RuntimeError(
                "No events were generated; check the video and contrast thresholds"
            )

        finalization_start = perf_counter()
        visualizer.finalize()
        writer.close("complete")
        save_events_csv(_combine_sample(sample_parts), output_paths["csv_partial"])
        inspection = inspect_event_file(output_paths["h5_partial"])
        if inspection["event_count"] != total_events:
            raise RuntimeError("Saved HDF5 event count does not match the simulation")

        hdf5_size = output_paths["h5_partial"].stat().st_size
        timings["finalization_seconds"] = perf_counter() - finalization_start
        timings["total_seconds"] = perf_counter() - start_time
        metadata = _build_metadata(
            video_path,
            info,
            output_paths,
            "complete",
            warnings,
            processed_frames,
            total_events,
            timings,
            hdf5_size,
            visualizer.snapshot_event_count,
        )
        save_metadata(metadata, output_paths["metadata_partial"])

        for partial_key, final_key in (
            ("h5_partial", "h5"),
            ("csv_partial", "csv"),
            ("snapshot_partial", "snapshot"),
            ("overlay_partial", "overlay"),
            ("metadata_partial", "metadata"),
        ):
            _replace_output(output_paths[partial_key], output_paths[final_key])

        print(f"Events:     {_format_count(total_events)}")
        print(f"HDF5 size:  {_format_bytes(hdf5_size)}")
        print(f"Time:       {timings['total_seconds']:.2f} s")
        print("\nGenerated files:")
        for key in ("h5", "csv", "snapshot", "overlay", "metadata"):
            print(f"- {output_paths[key]}")
        print("======================================")
        print("Finished.")
        return {
            "event_count": total_events,
            "processed_frames": processed_frames,
            "output_directory": str(output_paths["directory"]),
            "timings": timings.copy(),
        }

    except (Exception, KeyboardInterrupt) as exc:
        if visualizer is not None:
            visualizer.abort()
        if writer is not None:
            writer.close("incomplete")
        timings["total_seconds"] = perf_counter() - start_time
        hdf5_size = (
            output_paths["h5_partial"].stat().st_size
            if output_paths["h5_partial"].is_file()
            else 0
        )
        failure_metadata = _build_metadata(
            video_path,
            info,
            output_paths,
            "cancelled" if isinstance(exc, KeyboardInterrupt) else "failed",
            warnings,
            processed_frames,
            total_events,
            timings,
            hdf5_size,
            visualizer.snapshot_event_count if visualizer is not None else 0,
            error=exc,
        )
        try:
            save_metadata(failure_metadata, output_paths["metadata_partial"])
        except OSError:
            pass
        raise
    finally:
        reader.release()
