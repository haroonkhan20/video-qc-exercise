"""Import shared packaged definitions; no web-specific policy registry."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from qc.rulebook import section
from qc.reasons import group,REGISTRY
