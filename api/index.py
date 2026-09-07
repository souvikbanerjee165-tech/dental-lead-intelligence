import sys
import os
from pathlib import Path

# Add project root to sys.path so app modules import properly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app import app
