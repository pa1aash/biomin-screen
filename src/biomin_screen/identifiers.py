"""DOI normalisation used by the evidence table."""
import re

_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.I)
_DOI_BODY = re.compile(r"^10\.\d{4,9}/\S+$")


def normalize_doi(value):
    if not value:
        return None
    s = _DOI_PREFIX.sub("", str(value).strip()).strip().rstrip(".,;").lower()
    return s if _DOI_BODY.match(s) else None
