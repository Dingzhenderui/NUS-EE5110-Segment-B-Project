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


def get_effective_params(params=None):
    """Return effective simulation parameters merging defaults with overrides."""
    effective = {
        "contrast_threshold_pos": float(config.CONTRAST_THRESHOLD_POS),
        "contrast_threshold_neg": float(config.CONTRAST_THRESHOLD_NEG),
        "epsilon": float(config.EPSILON),
        "timestamp_resolution": float(config.TIMESTAMP_RESOLUTION),
        "accumulation_time": float(config.ACCUMULATION_TIME),
        "snapshot_start_time": float(config.SNAPSHOT_START_TIME),
        "snapshot_duration": float(config.SNAPSHOT_DURATION),
        "overlay_playback_fps": float(config.OVERLAY_PLAYBACK_FPS),
        "overlay_event_alpha": float(config.OVERLAY_EVENT_ALPHA),
        "low_fps_warning": float(config.LOW_FPS_WARNING),
        "event_csv_max_events": int(config.EVENT_CSV_MAX_EVENTS),
        "hdf5_chunk_events": int(config.HDF5_CHUNK_EVENTS),
        "progress_interval_frames": int(config.PROGRESS_INTERVAL_FRAMES),
    }
    if params:
        for k, v in params.items():
            if v is not None and k in effective:
                effective[k] = type(effective[k])(v)
    return effective


def build_output_paths(video_path, params=None, start_time=None):
    """Build output paths organized by video material and simulation start time."""
    if start_time is None:
        start_time = datetime.now()
    if isinstance(start_time, datetime):
        time_tag = start_time.strftime("%Y%m%d_%H%M%S")
    else:
        time_tag = str(start_time)

    result_dir = config.OUTPUT_DIR / video_path.stem / time_tag
    return {
        "directory": result_dir,
        "h5": result_dir / "events.h5",
        "h5_partial": result_dir / "events.partial.h5",
        "csv": result_dir / "events_sample.csv",
        "csv_partial": result_dir / "events_sample.partial.csv",
        "overlay": result_dir / "event_overlay.mp4",
        "overlay_partial": result_dir / "event_overlay.partial.mp4",
        "event_only": result_dir / "event_only.mp4",
        "event_only_partial": result_dir / "event_only.partial.mp4",
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
    import time
    partial_path = Path(partial_path)
    final_path = Path(final_path)
    if not partial_path.is_file():
        raise RuntimeError(f"Expected output was not created: {partial_path}")

    # Retry loop with backoff for Windows file locks
    for attempt in range(6):
        try:
            if final_path.is_file():
                try:
                    final_path.unlink()
                except OSError:
                    pass
            os.replace(partial_path, final_path)
            return
        except OSError as exc:
            if attempt == 5:
                try:
                    import shutil
                    shutil.copyfile(str(partial_path), str(final_path))
                    try:
                        partial_path.unlink()
                    except OSError:
                        pass
                    return
                except OSError:
                    raise exc
            time.sleep(0.1)


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
    effective_params=None,
    error=None,
):
    p = get_effective_params(effective_params)
    elapsed = max(float(timings.get("total_seconds", 0.0)), 1e-12)
    try:
        input_rel_path = video_path.relative_to(config.PROJECT_ROOT).as_posix()
    except (ValueError, AttributeError):
        input_rel_path = str(video_path)

    metadata = {
        "status": status,
        "input_video": video_path.name,
        "input_path": input_rel_path,
        "video": info,
        "model": {
            "type": "ideal noise-free contrast-threshold model",
            "interpolation": "linear between consecutive frames",
            "timestamp_unit": "seconds",
            "timestamp_resolution": p["timestamp_resolution"],
            "noise_simulation": False,
        },
        "parameters": {
            "contrast_threshold_pos": p["contrast_threshold_pos"],
            "contrast_threshold_neg": p["contrast_threshold_neg"],
            "epsilon": p["epsilon"],
            "timestamp_resolution": p["timestamp_resolution"],
            "accumulation_time": p["accumulation_time"],
            "snapshot_start_time": p["snapshot_start_time"],
            "snapshot_duration": p["snapshot_duration"],
            "overlay_playback_fps": p["overlay_playback_fps"],
            "overlay_event_alpha": p["overlay_event_alpha"],
            "low_fps_warning_threshold": p["low_fps_warning"],
        },
        "storage": {
            "format": "HDF5",
            "datasets": {
                name: np.dtype(dtype).name for name, dtype in EVENT_DTYPES.items()
            },
            "compression": "LZF with shuffle",
            "chunk_events": p["hdf5_chunk_events"],
            "uncompressed_bytes_per_event": RAW_EVENT_BYTES,
            "hdf5_file_bytes": int(hdf5_size),
        },
        "result": {
            "processed_frames": int(processed_frames),
            "event_count": int(total_events),
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
            "event_overlay": output_paths["overlay"].name,
            "event_only_video": output_paths["event_only"].name,
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


def run(
    video_path,
    params=None,
    max_frames=None,
    progress_callback=None,
    preview_callback=None,
    cancellation_check=None,
):
    """Generate, stream, and visualize events from one selected video."""

    sim_start_time = datetime.now()
    effective_params = get_effective_params(params)
    output_paths = build_output_paths(video_path, effective_params, start_time=sim_start_time)
    output_paths["directory"].mkdir(parents=True, exist_ok=True)
    reader = VideoReader(video_path)
    info = reader.get_info()
    warnings = []
    if info["fps"] < effective_params["low_fps_warning"]:
        warning = (
            f"Input FPS is {info['fps']:.2f}, below the project's "
            f"{effective_params['low_fps_warning']:.0f} FPS warning threshold. Low FPS is "
            "supported, but frame interpolation is less reliable and each frame "
            "may produce a very large event batch."
        )
        warnings.append(warning)

    effective_total_frames = (
        min(info["frame_count"], int(max_frames))
        if max_frames and info["frame_count"] > 0
        else (int(max_frames) if max_frames else info["frame_count"])
    )

    print("======================================")
    print("EE5110 Event Camera Simulator")
    print("======================================")
    print(f"Input:      {video_path}")
    print(f"Output:     {output_paths['directory']}")
    print(f"FPS:        {info['fps']:.2f}")
    print(f"Frames:     {effective_total_frames} (total in file: {info['frame_count']})")
    print(f"Resolution: {info['width']} x {info['height']}")
    for warning in warnings:
        print(f"[WARNING] {warning}")

    simulator = EventSimulator(
        effective_params["contrast_threshold_pos"],
        effective_params["contrast_threshold_neg"],
        effective_params["epsilon"],
        effective_params["timestamp_resolution"],
    )
    sample_parts = {name: [] for name in EVENT_DTYPES}
    sample_count = 0
    processed_frames = 0
    total_events = 0
    total_pos_events = 0
    total_neg_events = 0
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
            effective_params["hdf5_chunk_events"],
            attributes={
                "timestamp_resolution": effective_params["timestamp_resolution"],
                "contrast_threshold_pos": effective_params["contrast_threshold_pos"],
                "contrast_threshold_neg": effective_params["contrast_threshold_neg"],
                "epsilon": effective_params["epsilon"],
                "model": "ideal noise-free contrast-threshold model",
                "source_video": video_path.name,
            },
        )
        visualizer = StreamingEventVisualizer(
            info,
            output_paths["overlay_partial"],
            output_paths["event_only_partial"],
            None,
            effective_params["accumulation_time"],
            effective_params["snapshot_start_time"],
            effective_params["snapshot_duration"],
            effective_params["overlay_playback_fps"],
            effective_params["overlay_event_alpha"],
        )

        while True:
            if cancellation_check is not None and cancellation_check():
                raise KeyboardInterrupt("Simulation cancelled by user")

            if max_frames is not None and processed_frames >= max_frames:
                break

            frame, timestamp = reader.read_frame()
            if frame is None:
                break

            stage_start = perf_counter()
            events = simulator.process_frame(frame, timestamp)
            timings["event_generation_seconds"] += perf_counter() - stage_start
            event_count = len(events["t"])
            pos_count = int(np.sum(events["p"] > 0))
            neg_count = int(np.sum(events["p"] < 0))
            total_pos_events += pos_count
            total_neg_events += neg_count

            stage_start = perf_counter()
            writer.append(events)
            sample_count = _collect_sample(
                sample_parts,
                events,
                sample_count,
                effective_params["event_csv_max_events"],
            )
            timings["event_storage_seconds"] += perf_counter() - stage_start

            stage_start = perf_counter()
            orig_copy = frame.copy() if preview_callback is not None else None
            overlay_frame, event_canvas = visualizer.add_frame(frame, timestamp, events)
            timings["visualization_seconds"] += perf_counter() - stage_start

            total_events += event_count
            processed_frames += 1

            if preview_callback is not None:
                preview_callback(
                    orig_copy,
                    event_canvas,
                    overlay_frame,
                    timestamp,
                    processed_frames,
                )

            if progress_callback is not None:
                elapsed = max(perf_counter() - start_time, 1e-12)
                progress_callback(
                    processed_frames,
                    effective_total_frames,
                    total_events,
                    processed_frames / elapsed,
                    total_pos_events,
                    total_neg_events,
                    output_paths["h5_partial"].stat().st_size if output_paths["h5_partial"].is_file() else 0,
                )

            if processed_frames % effective_params["progress_interval_frames"] == 0:
                writer.flush()
                _print_progress(
                    processed_frames,
                    effective_total_frames,
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
            effective_params=effective_params,
        )
        save_metadata(metadata, output_paths["metadata_partial"])

        for partial_key, final_key in (
            ("h5_partial", "h5"),
            ("csv_partial", "csv"),
            ("overlay_partial", "overlay"),
            ("event_only_partial", "event_only"),
            ("metadata_partial", "metadata"),
        ):
            _replace_output(output_paths[partial_key], output_paths[final_key])

        print(f"Events:     {_format_count(total_events)}")
        print(f"HDF5 size:  {_format_bytes(hdf5_size)}")
        print(f"Time:       {timings['total_seconds']:.2f} s")
        print("\nGenerated files:")
        for key in ("h5", "csv", "overlay", "event_only", "metadata"):
            print(f"- {output_paths[key]}")
        print("======================================")
        print("Finished.")
        return {
            "event_count": total_events,
            "pos_events": total_pos_events,
            "neg_events": total_neg_events,
            "processed_frames": processed_frames,
            "output_directory": str(output_paths["directory"]),
            "output_paths": {k: str(v) for k, v in output_paths.items()},
            "timings": timings.copy(),
            "metadata": metadata,
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
            effective_params=effective_params,
            error=exc,
        )
        try:
            save_metadata(failure_metadata, output_paths["metadata_partial"])
        except OSError:
            pass
        raise
    finally:
        reader.release()
