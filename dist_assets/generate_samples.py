"""Generate sample .blu project files for distribution.

Run as a standalone script:
    python dist_assets/generate_samples.py [output_dir]

If output_dir is omitted, files are written to the current directory.
"""

import sys
from pathlib import Path

# Add project root to path so we can import backlight_sim from the source tree
# (not needed when run from within the frozen executable context)
_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backlight_sim.io.presets import (
    preset_simple_box,
    preset_automotive_cluster,
    preset_edge_lit_lgp,
)
from backlight_sim.io.project_io import save_project


SAMPLES = [
    ("Simple_Box_Demo.blu", preset_simple_box),
    ("Automotive_Cluster_Demo.blu", preset_automotive_cluster),
    ("Edge_Lit_LGP_Demo.blu", preset_edge_lit_lgp),
]


def main():
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    output_dir.mkdir(parents=True, exist_ok=True)

    for filename, factory in SAMPLES:
        try:
            project = factory()
            out_path = output_dir / filename
            save_project(project, str(out_path))
            print(f"  Created {filename}")
        except Exception as exc:
            print(f"  WARNING: Could not create {filename}: {exc}")


if __name__ == "__main__":
    main()
