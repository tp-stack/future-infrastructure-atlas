"""Commercial data-rights policy.

The policy is intentionally fail-closed: missing rights metadata is treated as
not sellable until a reviewed grant explicitly approves commercial API use.
"""

from __future__ import annotations

from typing import Any


SAFE_ALLOWED_USAGES = {
    "commercial_api_allowed",
    "redistribution_safe",
    "licensed_redistribution_only",
    "permissioned_redistribution_only",
    "owned",
    "public_domain",
    "cc_by_commercial",
}

BLOCKED_ALLOWED_USAGES = {
    "metadata_registry_only_until_license_verified",
    "internal_prototype_pending_license_review",
    "licensed_redistribution_only_without_permission",
    "permissioned_redistribution_only_without_permission",
    "non_commercial_only",
}

BLOCKED_LICENSE_VALUES = {"", "to_verify", "unknown", "non_commercial"}


def is_commercial_source_allowed(
    source: dict[str, Any],
    rights_grant: dict[str, Any] | None,
    *,
    require_redistribution: bool = False,
) -> bool:
    """Return whether a source may be served through paid endpoints."""

    if not rights_grant:
        return False

    license_value = str(source.get("license") or "").strip().lower()
    allowed_usage = str(source.get("allowed_usage") or "").strip()

    if license_value in BLOCKED_LICENSE_VALUES:
        return False
    if allowed_usage in BLOCKED_ALLOWED_USAGES:
        return False
    if allowed_usage not in SAFE_ALLOWED_USAGES:
        return False
    if rights_grant.get("license_review_status") != "approved":
        return False
    if not rights_grant.get("commercial_api_allowed"):
        return False
    if rights_grant.get("share_alike_risk"):
        return False
    if require_redistribution and not rights_grant.get("redistribution_allowed"):
        return False
    return True


def sql_commercial_rights_predicate(alias: str = "s", grant_alias: str = "g", *, require_redistribution: bool = False) -> str:
    """Return SQL conditions matching the in-process commercial rights policy."""

    redistribution_clause = f" AND {grant_alias}.redistribution_allowed = true" if require_redistribution else ""
    safe_values = ", ".join(f"'{value}'" for value in sorted(SAFE_ALLOWED_USAGES))
    blocked_licenses = ", ".join(f"'{value}'" for value in sorted(BLOCKED_LICENSE_VALUES))
    return (
        f"{grant_alias}.commercial_api_allowed = true"
        f"{redistribution_clause}"
        f" AND {grant_alias}.license_review_status = 'approved'"
        f" AND {grant_alias}.share_alike_risk = false"
        f" AND lower(coalesce({alias}.license, '')) NOT IN ({blocked_licenses})"
        f" AND {alias}.allowed_usage IN ({safe_values})"
    )
