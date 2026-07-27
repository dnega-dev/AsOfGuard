"""AsOfGuard: temporal contamination verification for observable AI traces."""

from .models import Trace, TraceFormatError, Verdict, VerdictStatus
from .parser import load_trace, loads_trace, parse_trace
from .verifier import TemporalVerifier, verify_trace

__all__ = [
    "TemporalVerifier",
    "Trace",
    "TraceFormatError",
    "Verdict",
    "VerdictStatus",
    "load_trace",
    "loads_trace",
    "parse_trace",
    "verify_trace",
]

__version__ = "0.1.0"
