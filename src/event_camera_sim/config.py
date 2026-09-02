"""Settings that students are expected to adjust for each experiment."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}

# Event-camera parameters.
CONTRAST_THRESHOLD_POS = 0.2
CONTRAST_THRESHOLD_NEG = 0.2
EPSILON = 1e-3
TIMESTAMP_RESOLUTION = 1e-6

# Videos below this value remain supported, but the program prints a warning.
LOW_FPS_WARNING = 120.0

# Visualization parameters.
ACCUMULATION_TIME = 0.01
SNAPSHOT_START_TIME = 0.5
SNAPSHOT_DURATION = 0.02

# Output settings.
EVENT_CSV_MAX_EVENTS = 100_000
HDF5_CHUNK_EVENTS = 262_144
PROGRESS_INTERVAL_FRAMES = 50
