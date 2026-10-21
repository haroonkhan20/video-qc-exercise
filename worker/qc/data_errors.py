"""Known malformed-container errors; runtime and unsupported-feature errors propagate."""
from mcap.exceptions import InvalidMagic, EndOfFile
from mcap.stream_reader import CRCValidationError
DATA_READ_ERRORS = (InvalidMagic, EndOfFile, CRCValidationError)
