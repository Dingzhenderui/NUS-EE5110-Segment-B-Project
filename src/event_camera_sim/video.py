"""High-frame-rate video input."""

from pathlib import Path

import cv2


def list_input_videos(input_dir, supported_extensions):
    """Return supported videos directly inside ``input_dir``."""

    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input folder does not exist: {input_dir}")

    return sorted(
        (
            path
            for path in input_dir.iterdir()
            if path.is_file() and path.suffix.lower() in supported_extensions
        ),
        key=lambda path: path.name.casefold(),
    )


def resolve_input_video(input_dir, supported_extensions, filename):
    """Resolve an exact filename while keeping selection inside ``input_dir``."""

    requested = Path(filename)
    if requested.is_absolute() or requested.name != filename:
        raise ValueError("--video must be a filename directly inside input/")
    if requested.suffix.lower() not in supported_extensions:
        supported = ", ".join(sorted(supported_extensions))
        raise ValueError(f"Unsupported video extension; expected one of: {supported}")

    video_path = input_dir / requested.name
    if not video_path.is_file():
        raise FileNotFoundError(f"Input video does not exist: {video_path}")
    return video_path


def select_input_video(input_dir, supported_extensions, requested_name=None):
    """Select one video by argument, automatic choice, or numbered menu."""

    if requested_name is not None:
        video_path = resolve_input_video(
            input_dir,
            supported_extensions,
            requested_name,
        )
        print(f"Selected video: {video_path.name}")
        return video_path

    videos = list_input_videos(input_dir, supported_extensions)
    if not videos:
        supported = ", ".join(sorted(supported_extensions))
        raise FileNotFoundError(
            f"No input videos found in {input_dir}; supported: {supported}"
        )
    if len(videos) == 1:
        print(f"Selected only input video: {videos[0].name}")
        return videos[0]

    print("Available input videos:")
    for index, video_path in enumerate(videos, start=1):
        print(f"  {index}. {video_path.name}")

    while True:
        try:
            choice = input("Select a video number, or q to cancel: ").strip()
        except EOFError as exc:
            raise RuntimeError(
                "Interactive input is unavailable; run again with --video FILENAME"
            ) from exc
        if choice.casefold() == "q":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(videos):
            video_path = videos[int(choice) - 1]
            print(f"Selected video: {video_path.name}")
            return video_path
        print(f"Please enter a number from 1 to {len(videos)}, or q.")


class VideoReader:
    """Read video frames sequentially and derive timestamps from the FPS."""

    def __init__(self, video_path):
        self.video_path = str(video_path)
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            raise FileNotFoundError(f"Cannot open input video: {self.video_path}")

        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.frame_index = 0

        if self.fps <= 0:
            self.release()
            raise RuntimeError(f"Video reports an invalid FPS: {self.video_path}")
        if self.width <= 0 or self.height <= 0:
            self.release()
            raise RuntimeError(f"Video reports an invalid resolution: {self.video_path}")

    def get_info(self):
        return {
            "fps": self.fps,
            "frame_count": self.frame_count,
            "width": self.width,
            "height": self.height,
            "duration": self.frame_count / self.fps,
        }

    def read_frame(self):
        success, frame = self.cap.read()
        if not success:
            return None, None

        timestamp = self.frame_index / self.fps
        self.frame_index += 1
        return frame, timestamp

    def release(self):
        self.cap.release()
