"""Canonical digest for independently attested cleanup observation receipts.

A digest is NOT a signature or an authentication decision. Only an external,
trusted receipt registry may authorize a digest for use in conservative queries.
"""

import hashlib
import json

from .models import Observation


def closure_digest(observation: Observation) -> str:
    """Bind a receipt to the entire observation, not a spoofable source/ID label.

    Reject non-JSON or non-finite metadata rather than silently changing the
    canonical representation. This function does not validate a signature.
    """
    canonical = json.dumps(
        observation.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
