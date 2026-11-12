# RepoPilot AI Verification Entry
import sys
from pathlib import Path

# Add backend directory to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

print("RepoPilot AI environment configured.")
