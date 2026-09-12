"""Command-line entry point for ``python -m event_camera_sim``."""

import argparse
import sys

from . import config
from .pipeline import run
from .video import select_input_video


def main():
    parser = argparse.ArgumentParser(
        prog="python -m event_camera_sim",
        description="Generate events from the configured high-frame-rate video.",
    )
    subparsers = parser.add_subparsers(dest="command")

    gui_parser = subparsers.add_parser(
        "gui",
        help="launch the modern graphical interface (default)",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="select one input video and run the complete simulation via CLI",
    )
    run_parser.add_argument(
        "--video",
        metavar="FILENAME",
        help="video filename directly inside input/; omit to use the menu",
    )
    args = parser.parse_args()

    if args.command is None or args.command == "gui":
        from .gui.app import main as gui_main
        return gui_main()

    try:
        video_path = select_input_video(
            config.INPUT_DIR,
            config.SUPPORTED_VIDEO_EXTENSIONS,
            args.video,
        )
        if video_path is None:
            print("Operation cancelled.")
            return 0
        run(video_path)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        return 130
    except (OSError, RuntimeError, ValueError, MemoryError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
