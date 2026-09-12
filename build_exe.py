"""Automated build script for packaging EE5110 Event Camera Simulator into a standalone Windows EXE."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def build():
    root_dir = Path(__file__).resolve().parent
    dist_dir = root_dir / "dist"
    build_dir = root_dir / "build"
    app_name = "EventCameraSimulator"
    output_bundle_dir = dist_dir / app_name

    print("==================================================")
    print(" Event Camera Simulator - Packaging EXE")
    print("==================================================")
    print(f"Project directory: {root_dir}")
    print(f"Python executable: {sys.executable}")

    # Ensure no running instance is locking files in dist/
    try:
        subprocess.run(["taskkill", "/F", "/IM", f"{app_name}.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    # Build PyInstaller command using the customized spec file
    pyinstaller_cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(root_dir / "EE5110_EventCameraSimulator.spec"),
        "--clean",
        "--noconfirm",
    ]

    print("\n[1/3] Running PyInstaller...")
    print("Command:", " ".join(str(x) for x in pyinstaller_cmd))

    ret = subprocess.run(pyinstaller_cmd, cwd=root_dir)
    if ret.returncode != 0:
        print(f"\n[ERROR] PyInstaller build failed with exit code: {ret.returncode}")
        sys.exit(ret.returncode)

    print("\n[2/3] Copying sample input videos and auxiliary files to dist...")
    dest_input_dir = output_bundle_dir / "input"
    dest_input_dir.mkdir(parents=True, exist_ok=True)

    src_input_dir = root_dir / "input"
    if src_input_dir.is_dir():
        for item in src_input_dir.iterdir():
            if item.is_file():
                dest_file = dest_input_dir / item.name
                shutil.copy2(item, dest_file)
                print(f"  Copied sample: {item.name}")

    src_assets_dir = root_dir / "assets"
    dest_assets_dir = output_bundle_dir / "assets"
    if src_assets_dir.is_dir():
        shutil.copytree(src_assets_dir, dest_assets_dir, dirs_exist_ok=True)
        print(f"  Copied assets to {dest_assets_dir}")

    # Create README_Instructions.txt in distribution directory
    readme_content = """================================================================================
  EE5110 / EE6110 Event Camera Simulator - User Guide & Documentation
  National University of Singapore (NUS) - Continuous Assessment Project
================================================================================

1. QUICK START GUIDE
--------------------------------------------------------------------------------
1. Launch the application:
   Double-click `EventCameraSimulator.exe` in this folder. No Python installation
   or external dependencies are required.

2. Select a Video Input:
   - Sample Dropdown: Choose from 8 curated high-speed datasets (e.g.,
     hummingbird @ 2000 FPS, clock gear @ 960 FPS, lightning @ 240 FPS).
   - Browse Button: Select any standard video file (.mp4, .avi, .webm, .mov)
     from your computer.

3. Fast Demo Mode (Recommended for Presentation / PPT Live Demos):
   - Check "Limit Frames (Fast Demo)" with the default 150 frames.
   - This completes the end-to-end simulation in 1-2 seconds, providing instant
     interactive visualization and stats without presentation lag.
   - Uncheck to process the entire video file.

4. Adjust Parameters:
   Configure the 4 simulation parameters on the left panel (detailed below),
   then click "▶ Start Simulation".

5. View & Replay Results:
   - Toggle between "Event Overlay" (red/blue events over original video) and
     "Event-Only" (isolated neuromorphic pulse display).
   - Use the timeline scrubber, Play/Pause button, and speed selector
     (0.25x, 0.5x, 1.0x, 2.0x) to analyze dynamic event generation.
   - Click "📁 Open Output Folder" to inspect generated data files.


================================================================================
2. DETAILED EXPLANATION OF THE FOUR PARAMETERS
================================================================================

[1] Positive Threshold (C_pos)
--------------------------------------------------------------------------------
- Default: 0.40  |  Range: [0.05, 1.00]  |  Step: 0.05
- Physics & Model:
  Defines the contrast threshold for triggering a POSITIVE polarity event (p = +1,
  represented in RED). Whenever the temporal change in logarithmic brightness
  at pixel (x, y) reaches or exceeds this positive threshold:
      Δ ln(I) = ln(I_new) - ln(I_last) >= +C_pos
  an ON event is recorded with an interpolated microsecond-precision timestamp.
- Practical Effect:
  * Lower C_pos (e.g. 0.10 - 0.20): Higher sensitivity. Captures subtle brightening
    edges, fine feathers, and micro-movements, but is more susceptible to sensor/
    compression noise in flat regions (e.g., sky).
  * Higher C_pos (e.g. 0.60 - 0.80): Lower sensitivity. Produces a very clean,
    sparse event stream containing only high-contrast brightening contours.


[2] Negative Threshold (C_neg)
--------------------------------------------------------------------------------
- Default: 0.40  |  Range: [0.05, 1.00]  |  Step: 0.05
- Physics & Model:
  Defines the contrast threshold for triggering a NEGATIVE polarity event (p = -1,
  represented in BLUE). Whenever the temporal decrease in logarithmic brightness
  at pixel (x, y) reaches or exceeds this negative threshold:
      Δ ln(I) = ln(I_new) - ln(I_last) <= -C_neg
  an OFF event is recorded with an interpolated microsecond-precision timestamp.
- Practical Effect:
  * Lower C_neg: Increases sensitivity to darkening edges and trailing shadows.
  * Asymmetric Thresholding (C_pos ≠ C_neg): Real neuromorphic silicon sensors
    (e.g., DAVIS, Prophesee) often exhibit asymmetric sensitivity between ON and
    OFF channels due to transistor mismatch. Setting e.g. C_pos=0.20 and C_neg=0.40
    allows studying polarity balance and asymmetric contrast dynamics.


[3] Accumulation Time (ms)
--------------------------------------------------------------------------------
- Default: 2.0 ms  |  Range: [0.5 ms, 20.0 ms]  |  Step: 0.5 ms
- Physics & Model:
  The temporal integration window (Δt_acc) for human visual inspection. Because
  biological human vision cannot resolve individual microsecond event spikes, events
  occurring within [t - Δt_acc, t] are integrated into each rendered display frame.
- CRITICAL SCIENTIFIC DISTINCTION:
  This parameter ONLY controls visualization rendering (the overlay and event-only
  display frames). It does NOT alter, drop, or affect the underlying raw event
  stream, timestamps, or count saved in the HDF5 archive (events.h5).
- Practical Effect:
  * Smaller Δt_acc (e.g. 0.5 - 1.0 ms): Shows thin, crisp, instantaneous edge events
    frozen in time, ideal for precise high-speed edge localization.
  * Larger Δt_acc (e.g. 5.0 - 10.0 ms): Accumulates motion history into a dynamic
    streak/halo, revealing the full trajectory of fast movements (e.g. bird wings).


[4] Overlay Alpha
--------------------------------------------------------------------------------
- Default: 0.45  |  Range: [0.10, 1.00]  |  Step: 0.05
- Physics & Model:
  The blending opacity weight (α) used to composite event polarity markers onto
  the underlying grayscale video frame:
      I_rendered = (1 - α) * I_frame + α * I_event_color
- Practical Effect:
  * Lower Alpha (e.g. 0.20 - 0.30): Makes event dots subtle and semi-transparent,
    keeping the original background texture clearly visible underneath.
  * Higher Alpha (e.g. 0.70 - 1.00): Highlights ON (Red) and OFF (Blue) events
    with high contrast and vivid neon saturation, ideal for presentation slides
    where event activity needs to be prominently visible from a distance.


================================================================================
3. RECOMMENDED PRESENTATION DEMONSTRATIONS
================================================================================
- Recommended Sample: `hummingbird_2000fps_648x360.mp4` (2000 FPS)
  Features two hummingbirds battling in mid-air with ~50 Hz wingbeats. Provides
  exceptional spatial separation of events and dual moving targets.
- Threshold Contrast Experiment:
  Run once with C_pos=0.4 / C_neg=0.4, then run with C_pos=0.1 / C_neg=0.1 to
  demonstrate how lower thresholds capture detailed wing feather texture at the
  cost of increased background compression noise.
- Extreme Lighting Experiment: `lightning_240fps_360x640.mp4`
  Demonstrates extreme instantaneous brightness transitions triggering massive
  synchronized threshold crossings.


================================================================================
4. DATA STORAGE & OUTPUT ARCHITECTURE
================================================================================
All simulation outputs are automatically organized and archived by material
name and timestamp under the `output/` directory:
  output/<video_material_name>/<YYYYMMDD_HHMMSS>/

Each folder contains:
1. `events.h5`           - Complete, lossless HDF5 container storing the 4 arrays:
                           't' (timestamps, uint64 in μs), 'x' (uint16),
                           'y' (uint16), 'p' (int8: +1 for ON, -1 for OFF).
2. `event_overlay.mp4`   - MP4 video with events overlaid on original video.
3. `event_only.mp4`      - Standalone MP4 video showing only neuromorphic events.
4. `events_sample.csv`   - Human-readable CSV snapshot of the first 50,000 events.
5. `metadata.json`       - Full reproducibility report containing exact parameters,
                           processing timings, event throughput, and dataset stats.
================================================================================
"""
    readme_path = output_bundle_dir / "README_Instructions.txt"
    with readme_path.open("w", encoding="utf-8") as f:
        f.write(readme_content)
    print("  Created README_Instructions.txt")

    exe_path = output_bundle_dir / f"{app_name}.exe"

    # Notify Windows Shell to refresh icon cache
    try:
        import ctypes
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    except Exception:
        pass

    print("\n[3/3] Verification...")
    if exe_path.is_file():
        print(f"\n[SUCCESS] Package built successfully!")
        print(f"Target executable: {exe_path}")
        print(f"File size: {exe_path.stat().st_size / (1024 * 1024):.2f} MB")
        print(f"Distribution folder: {output_bundle_dir}")
        print("Ready for distribution!")
    else:
        print(f"[ERROR] Target executable not found: {exe_path}")
        sys.exit(1)


if __name__ == "__main__":
    build()
