import sys
from pathlib import Path

# Let tests import the `scripts` and `src` packages from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
