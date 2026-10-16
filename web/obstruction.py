"""Shared snapshot screening; the worker and dashboard use the same detector."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
from qc.obstruction import VERSION,SETTINGS,provenance,inspect_image,summarize
