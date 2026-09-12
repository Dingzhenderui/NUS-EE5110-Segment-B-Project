"""Direct entry point for EE5110 Event Camera Simulator GUI application."""

import sys
import os
from pathlib import Path

# On Windows, explicitly register DLL search paths for PySide6 and shiboken6
if sys.platform == "win32":
    if getattr(sys, "frozen", False):
        # In PyInstaller --onedir mode, sys._MEIPASS is the _internal directory
        base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    else:
        base_dir = Path(__file__).resolve().parent

    for sub in ["PySide6", "shiboken6", ""]:
        d = base_dir / sub
        if d.is_dir():
            try:
                os.add_dll_directory(str(d))
            except (OSError, AttributeError):
                pass
            os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")

# Ensure src is in sys.path when running as script
current_dir = Path(__file__).resolve().parent
src_dir = current_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from event_camera_sim.gui.app import main


if __name__ == "__main__":
    sys.exit(main())
