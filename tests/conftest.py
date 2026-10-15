import sys
from pathlib import Path

# Testler `scripts` ve `src` paketlerini proje kökünden import edebilsin.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
