"""Local researcher profiles & extensible identity provider interface.

For Bachelor's thesis studies and local peer dual-reviews, UX-mAInd Studio operates
100% offline without cloud accounts or login walls: a reviewer profile requires only
a display name or short code (`display_name`, optional `short_code` and `role`).

Future institutional or team deployments can attach an authenticated identity provider
(e.g. university SSO / OIDC / SAML) by implementing `ReviewerIdentityProvider` without
altering `ux_decisions`, `dual_review`, or export schemas.
"""

from __future__ import annotations

import re
import secrets
from typing import Protocol, runtime_checkable

DEFAULT_RESEARCHER = {
    "id": "default",
    "display_name": "Standard-Prüfer",
    "short_code": "SP",
    "role": "UX-Forscher",
    "auth_mode": "local",
}


def _slug_id(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_-]+", "-", text.strip().lower()).strip("-")
    return cleaned[:48] or f"reviewer-{secrets.token_hex(3)}"


def _derive_short_code(name: str, explicit: str = "") -> str:
    code = re.sub(r"[^A-Za-z0-9ÄÖÜäöü_-]+", "", (explicit or "").strip()).upper()[:12]
    if code:
        return code
    parts = [p for p in re.split(r"[\s._-]+", name.strip()) if p]
    if len(parts) >= 2:
        return "".join(p[0] for p in parts[:4]).upper()
    cleaned = re.sub(r"[^A-Za-z0-9ÄÖÜäöü]+", "", name.strip()).upper()
    return cleaned[:4] or "PR"


@runtime_checkable
class ReviewerIdentityProvider(Protocol):
    """Architectural extension hook for pluggable reviewer authentication."""

    mode: str

    def list_identities(self, workspace) -> dict: ...

    def active_stamp(self, workspace) -> dict: ...


class LocalProfileIdentityProvider:
    """Default local SQLite-backed reviewer profile store (name or short code only)."""

    mode = "local"

    def list_identities(self, workspace) -> dict:
        stored = workspace.setting("researcher_profiles")
        profiles = []
        if isinstance(stored, list):
            for raw in stored:
                if isinstance(raw, dict) and raw.get("id") and raw.get("display_name"):
                    entry = {
                        "id": str(raw["id"]),
                        "display_name": str(raw["display_name"]),
                        "short_code": _derive_short_code(
                            str(raw["display_name"]), str(raw.get("short_code") or "")
                        ),
                        "role": str(raw.get("role") or "UX-Forscher"),
                        "auth_mode": str(raw.get("auth_mode") or "local"),
                    }
                    profiles.append(entry)
        if not any(p["id"] == "default" for p in profiles):
            profiles.insert(0, dict(DEFAULT_RESEARCHER))
        active_id = str(workspace.setting("active_researcher_id") or "default")
        active = next((p for p in profiles if p["id"] == active_id), profiles[0])
        return {
            "active": active,
            "profiles": profiles,
            "identity_mode": self.mode,
            "extension_point": "ReviewerIdentityProvider",
        }

    def active_stamp(self, workspace) -> dict:
        active = self.list_identities(workspace)["active"]
        stamp = {
            "id": active["id"],
            "name": active["display_name"],
            "short_code": active.get("short_code")
            or _derive_short_code(active["display_name"]),
            "auth_mode": active.get("auth_mode") or self.mode,
        }
        if active.get("role"):
            stamp["role"] = active["role"]
        return stamp


_PROVIDER: ReviewerIdentityProvider = LocalProfileIdentityProvider()


def set_identity_provider(provider: ReviewerIdentityProvider) -> None:
    """Register a custom `ReviewerIdentityProvider` (e.g. university SSO/OIDC)."""
    global _PROVIDER
    _PROVIDER = provider


def list_profiles(workspace) -> dict:
    """Return all saved local researcher profiles and the currently active reviewer."""
    return _PROVIDER.list_identities(workspace)


def active_reviewer_stamp(workspace) -> dict:
    """Compact immutable audit stamp embedded into `ux_decisions.payload.reviewer`."""
    return _PROVIDER.active_stamp(workspace)


def ensure_profile(
    workspace,
    *,
    display_name: str,
    short_code: str = "",
    role: str = "UX-Forscher",
    profile_id: str = "",
    activate: bool = False,
) -> dict:
    """Ensure a local researcher profile exists without clobbering active reviewer unless requested."""
    name = str(display_name or "").strip()
    if not name or len(name) > 80:
        raise ValueError("Anzeigename oder Kürzel des Prüfers erforderlich (max. 80 Zeichen)")
    clean_role = str(role or "UX-Forscher").strip()[:60]
    prof_id = str(profile_id or "").strip() or _slug_id(name)
    code = _derive_short_code(name, short_code)

    state = list_profiles(workspace)
    existing = next((p for p in state["profiles"] if p["id"] == prof_id), None)
    profiles = [p for p in state["profiles"] if p["id"] != prof_id]
    entry = {
        "id": prof_id,
        "display_name": name,
        "short_code": code,
        "role": clean_role or (existing or {}).get("role") or "UX-Forscher",
        "auth_mode": "local",
    }
    profiles.append(entry)
    workspace.set_setting("researcher_profiles", profiles)
    if activate:
        workspace.set_setting("active_researcher_id", prof_id)
    return entry


def save_profile(workspace, body: dict) -> dict:
    """Create or update a local researcher profile and activate it."""
    if not isinstance(body, dict):
        raise ValueError("Forscher-Profil als JSON-Objekt angeben")
    ensure_profile(
        workspace,
        display_name=str(body.get("display_name") or ""),
        short_code=str(body.get("short_code") or ""),
        role=str(body.get("role") or "UX-Forscher"),
        profile_id=str(body.get("id") or ""),
        activate=True,
    )
    return list_profiles(workspace)


def select_profile(workspace, profile_id: str) -> dict:
    """Switch the active researcher profile for subsequent review decisions."""
    target = str(profile_id or "").strip()
    state = list_profiles(workspace)
    if not any(p["id"] == target for p in state["profiles"]):
        raise ValueError("Unbekanntes Forscher-Profil")
    workspace.set_setting("active_researcher_id", target)
    return list_profiles(workspace)


def delete_profile(workspace, profile_id: str) -> dict:
    """Remove a custom local researcher profile (keeping 'default')."""
    target = str(profile_id or "").strip()
    if target == "default":
        raise ValueError("Das Standard-Prüferprofil kann nicht gelöscht werden")
    state = list_profiles(workspace)
    remaining = [p for p in state["profiles"] if p["id"] != target]
    workspace.set_setting("researcher_profiles", remaining)
    if state["active"]["id"] == target:
        workspace.set_setting("active_researcher_id", "default")
    return list_profiles(workspace)
