"""Decoupled researcher identity & optional OIDC / Google OAuth 2.0 adapter (`US-74`).

Local loopback workspaces operate 100% offline with zero login wall using switchable
local researcher profiles. When `UX_MAIND_OIDC_CLIENT_ID` is configured in the server
environment (e.g. Google OAuth 2.0 or university Keycloak/Shibboleth OIDC), standard
OpenID Connect Discovery + Authorization Code flow is available without vendor lock-in.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
from urllib.parse import urlencode
import urllib.request

DEFAULT_RESEARCHER = {
    "id": "default",
    "display_name": "Standard-Prüfer",
    "role": "UX-Forscher",
    "auth_mode": "local",
}


def _slug_id(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_-]+", "-", text.strip().lower()).strip("-")
    return cleaned[:48] or f"reviewer-{secrets.token_hex(3)}"


def oidc_env_config() -> dict:
    """Inspect environment for optional OIDC / Google OAuth configuration without exposing secrets."""
    client_id = (os.environ.get("UX_MAIND_OIDC_CLIENT_ID") or "").strip()
    client_secret = (os.environ.get("UX_MAIND_OIDC_CLIENT_SECRET") or "").strip()
    issuer = (
        os.environ.get("UX_MAIND_OIDC_ISSUER") or "https://accounts.google.com"
    ).strip().rstrip("/")
    provider_label = (
        "Google OAuth 2.0 / OIDC"
        if "accounts.google.com" in issuer
        else f"OIDC ({issuer})"
    )
    return {
        "enabled": bool(client_id and client_secret),
        "issuer": issuer,
        "provider_label": provider_label,
        "client_id_configured": bool(client_id),
        "client_secret_configured": bool(client_secret),
    }


def list_profiles(workspace) -> dict:
    """Return all saved researcher profiles and the currently active reviewer."""
    stored = workspace.setting("researcher_profiles")
    profiles = (
        [p for p in stored if isinstance(p, dict) and p.get("id") and p.get("display_name")]
        if isinstance(stored, list)
        else []
    )
    if not any(p["id"] == "default" for p in profiles):
        profiles.insert(0, dict(DEFAULT_RESEARCHER))
    active_id = str(workspace.setting("active_researcher_id") or "default")
    active = next((p for p in profiles if p["id"] == active_id), profiles[0])
    return {
        "active": active,
        "profiles": profiles,
        "oidc": oidc_env_config(),
    }


def active_reviewer_stamp(workspace) -> dict:
    """Compact immutable audit stamp embedded into `ux_decisions.payload.reviewer`."""
    active = list_profiles(workspace)["active"]
    stamp = {
        "id": active["id"],
        "name": active["display_name"],
        "auth_mode": active.get("auth_mode") or "local",
    }
    if active.get("role"):
        stamp["role"] = active["role"]
    if active.get("email"):
        stamp["email"] = active["email"]
    return stamp


def save_profile(workspace, body: dict) -> dict:
    """Create or update a researcher profile and activate it."""
    if not isinstance(body, dict):
        raise ValueError("Forscher-Profil als JSON-Objekt angeben")
    name = str(body.get("display_name") or "").strip()
    if not name or len(name) > 80:
        raise ValueError("Anzeigename des Prüfers erforderlich (max. 80 Zeichen)")
    role = str(body.get("role") or "UX-Forscher").strip()[:60]
    email = str(body.get("email") or "").strip()[:120]
    prof_id = str(body.get("id") or "").strip() or _slug_id(name)

    state = list_profiles(workspace)
    profiles = [p for p in state["profiles"] if p["id"] != prof_id]
    entry = {
        "id": prof_id,
        "display_name": name,
        "role": role,
        "auth_mode": "oidc" if body.get("auth_mode") == "oidc" else "local",
    }
    if email:
        entry["email"] = email
    profiles.append(entry)
    workspace.set_setting("researcher_profiles", profiles)
    workspace.set_setting("active_researcher_id", prof_id)
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


def build_oidc_authorize_url(workspace, redirect_uri: str) -> dict:
    """Build standard OIDC Authorization Code + PKCE URL when OIDC env vars are configured."""
    cfg = oidc_env_config()
    if not cfg["enabled"]:
        raise ValueError(
            "Optionale OIDC-/Google-Anmeldung ist nicht konfiguriert "
            "(UX_MAIND_OIDC_CLIENT_ID und UX_MAIND_OIDC_CLIENT_SECRET setzen)."
        )
    disc_url = f"{cfg['issuer']}/.well-known/openid-configuration"
    with urllib.request.urlopen(disc_url, timeout=10) as resp:
        disc = json.loads(resp.read().decode("utf-8"))
    auth_endpoint = disc.get("authorization_endpoint")
    if not auth_endpoint:
        raise ValueError("OIDC-Discovery enthält keinen authorization_endpoint")

    state_tok = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .decode("ascii")
        .rstrip("=")
    )
    workspace.set_setting(
        "oidc_pending_flow",
        {"state": state_tok, "code_verifier": verifier, "redirect_uri": redirect_uri},
    )
    params = {
        "client_id": os.environ["UX_MAIND_OIDC_CLIENT_ID"].strip(),
        "response_type": "code",
        "scope": "openid email profile",
        "redirect_uri": redirect_uri,
        "state": state_tok,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return {"authorize_url": f"{auth_endpoint}?{urlencode(params)}", "state": state_tok}
