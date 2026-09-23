"""
Normalizer — Stage 2.

Converts a raw source record (any schema) into a canonical record
with well-known field names, using the FieldDef mappings in PipelineConfig.

This is the only stage that knows about source field names.
All downstream stages work exclusively with canonical names.
"""
from typing import Any, Dict, List, Union

from ..config import FieldDef, PipelineConfig


def normalize(raw: Dict, config: PipelineConfig) -> Dict:
    """
    Extract canonical fields from `raw` using the mapping in `config.fields`.
    Returns a dict whose keys are the canonical names defined in config.
    """
    record: Dict[str, Any] = {}

    for canonical_name, field_def in config.fields.items():
        record[canonical_name] = _extract(raw, field_def)

    return record


def normalize_batch(records: List[Dict], config: PipelineConfig) -> List[Dict]:
    return [normalize(r, config) for r in records]


# ── private ───────────────────────────────────────────────────────────────────

def _extract(raw: Dict, field_def: FieldDef) -> Any:
    """
    Try each source field name in order until a non-empty value is found.
    Apply transform if defined; fall back to default otherwise.
    """
    sources: List[str] = (
        [field_def.source]
        if isinstance(field_def.source, str)
        else field_def.source
    )

    value = None
    for src in sources:
        v = raw.get(src)
        if _has_value(v):
            value = v
            break

    if not _has_value(value):
        default = field_def.default
        value = default() if callable(default) else default

    if value is not None and field_def.transform is not None:
        try:
            value = field_def.transform(value)
        except Exception:
            pass  # leave value as-is if transform fails

    return value


def _has_value(v: Any) -> bool:
    """Return True when v is a meaningful (non-absent) value."""
    if v is None:
        return False
    if isinstance(v, str) and not v.strip():
        return False
    if isinstance(v, (list, dict)) and len(v) == 0:
        return False
    return True
