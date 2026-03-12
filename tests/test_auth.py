"""Tests for core.auth module — covers C-01, H-01, and general auth logic."""

from __future__ import annotations

import base64
import json
import os
import pathlib
import sys
from unittest import mock

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import auth
from core.auth import (
    AuthError,
    _canonicalize_role,
    _canonicalize_roles,
    _normalise_role_token,
    get_user_id,
    get_user_roles,
    is_authenticated_user,
    is_authorized,
    parse_client_principal,
    require_role,
    verify_jwt,
)


# ---------------------------------------------------------------------------
# Role normalisation helpers
# ---------------------------------------------------------------------------

class TestNormaliseRoleToken:
    def test_basic(self):
        assert _normalise_role_token("Admin") == "admin"

    def test_with_spaces(self):
        assert _normalise_role_token("  Sanmar Naming Reader ") == "sanmar-naming-reader"

    def test_underscores(self):
        assert _normalise_role_token("sanmar_naming_admin") == "sanmar-naming-admin"

    def test_dots(self):
        assert _normalise_role_token("sanmar.naming.contributor") == "sanmar-naming-contributor"

    def test_empty(self):
        assert _normalise_role_token("") == ""


class TestCanonicalizeRole:
    def test_direct_match(self):
        assert _canonicalize_role("admin") == "admin"

    def test_alias(self):
        assert _canonicalize_role("sanmar-naming-reader") == "reader"

    def test_unknown_role(self):
        assert _canonicalize_role("unknown_role") is None

    def test_empty(self):
        assert _canonicalize_role("") is None


class TestCanonicalizeRoles:
    def test_multiple_roles(self):
        result = _canonicalize_roles(["reader", "sanmar.naming.admin", "bogus"])
        assert result == ["reader", "admin"]

    def test_deduplication(self):
        result = _canonicalize_roles(["admin", "sanmar-naming-admin"])
        assert result == ["admin"]

    def test_empty(self):
        assert _canonicalize_roles([]) == []


# ---------------------------------------------------------------------------
# parse_client_principal
# ---------------------------------------------------------------------------

class TestParseClientPrincipal:
    def test_valid_principal(self):
        principal_data = {"userId": "u123", "claims": []}
        encoded = base64.b64encode(json.dumps(principal_data).encode()).decode()
        result = parse_client_principal({"x-ms-client-principal": encoded})
        assert result["userId"] == "u123"

    def test_missing_header(self):
        with pytest.raises(ValueError, match="Missing client principal"):
            parse_client_principal({})


# ---------------------------------------------------------------------------
# verify_jwt
# ---------------------------------------------------------------------------

class TestVerifyJwt:
    def test_missing_auth_header(self):
        with pytest.raises(AuthError, match="Missing bearer token"):
            verify_jwt({})

    def test_non_bearer_header(self):
        with pytest.raises(AuthError, match="Missing bearer token"):
            verify_jwt({"Authorization": "Basic abc"})

    def test_no_jwks_url(self, monkeypatch):
        monkeypatch.setattr(auth, "JWKS_URL", "")
        with pytest.raises(AuthError, match="Tenant ID not configured"):
            verify_jwt({"Authorization": "Bearer some.token.here"})

    @mock.patch.object(auth, "PyJWKClient")
    def test_invalid_token(self, mock_cls, monkeypatch):
        from jwt import InvalidTokenError

        monkeypatch.setattr(auth, "JWKS_URL", "https://login.microsoftonline.com/t/discovery/v2.0/keys")
        mock_cls.return_value.get_signing_key_from_jwt.side_effect = InvalidTokenError("bad")
        with pytest.raises(AuthError) as exc_info:
            verify_jwt({"Authorization": "Bearer bad.token.here"})
        assert exc_info.value.status == 401

    @mock.patch("jwt.decode")
    @mock.patch.object(auth, "PyJWKClient")
    def test_successful_verify(self, mock_cls, mock_decode, monkeypatch):
        monkeypatch.setattr(auth, "JWKS_URL", "https://login.microsoftonline.com/t/discovery/v2.0/keys")
        mock_key = mock.MagicMock()
        mock_cls.return_value.get_signing_key_from_jwt.return_value = mock_key
        mock_decode.return_value = {"oid": "user-123", "roles": ["admin"]}
        claims = verify_jwt({"Authorization": "Bearer valid.token.here"})
        assert claims["oid"] == "user-123"


# ---------------------------------------------------------------------------
# require_role
# ---------------------------------------------------------------------------

class TestRequireRole:
    def test_invalid_role_config(self):
        with pytest.raises(AuthError, match="Invalid role configuration"):
            require_role({}, min_role="nonexistent")

    @mock.patch("core.auth.LOCAL_AUTH_BYPASS", True)
    @mock.patch("core.auth.LOCAL_BYPASS_ROLES", ["contributor", "admin"])
    @mock.patch("core.auth.LOCAL_BYPASS_USER_ID", "local-dev-user")
    def test_local_bypass_allowed(self):
        user_id, roles = require_role({}, min_role="contributor")
        assert user_id == "local-dev-user"
        assert "contributor" in roles

    @mock.patch("core.auth.LOCAL_AUTH_BYPASS", True)
    @mock.patch("core.auth.LOCAL_BYPASS_ROLES", ["reader"])
    @mock.patch("core.auth.LOCAL_BYPASS_USER_ID", "local-dev-user")
    def test_local_bypass_forbidden(self):
        with pytest.raises(AuthError, match="Forbidden"):
            require_role({}, min_role="admin")

    @mock.patch("core.auth.LOCAL_AUTH_BYPASS", False)
    @mock.patch.object(auth, "verify_jwt")
    def test_jwt_role_check_pass(self, mock_verify):
        mock_verify.return_value = {"oid": "u1", "roles": ["admin"]}
        user_id, roles = require_role({"Authorization": "Bearer x"}, min_role="reader")
        assert user_id == "u1"
        assert "admin" in roles

    @mock.patch("core.auth.LOCAL_AUTH_BYPASS", False)
    @mock.patch.object(auth, "verify_jwt")
    def test_jwt_role_check_forbidden(self, mock_verify):
        mock_verify.return_value = {"oid": "u1", "roles": ["reader"]}
        with pytest.raises(AuthError, match="Forbidden"):
            require_role({"Authorization": "Bearer x"}, min_role="admin")

    @mock.patch("core.auth.LOCAL_AUTH_BYPASS", False)
    @mock.patch.object(auth, "verify_jwt")
    def test_jwt_roles_as_string(self, mock_verify):
        mock_verify.return_value = {"oid": "u1", "roles": "admin"}
        user_id, roles = require_role({"Authorization": "Bearer x"}, min_role="admin")
        assert user_id == "u1"
        assert "admin" in roles


# ---------------------------------------------------------------------------
# get_user_id / get_user_roles
# ---------------------------------------------------------------------------

class TestGetUserId:
    def test_found(self):
        principal = {
            "claims": [
                {"typ": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier", "val": "u1"}
            ]
        }
        assert get_user_id(principal) == "u1"

    def test_not_found(self):
        assert get_user_id({"claims": []}) == ""


class TestGetUserRoles:
    @mock.patch.dict(auth.ROLE_GROUPS, {"admin": "group-1"})
    def test_matching_group(self):
        principal = {"claims": [{"typ": "groups", "val": "group-1"}]}
        assert "admin" in get_user_roles(principal)

    @mock.patch.dict(auth.ROLE_GROUPS, {"admin": "group-1"})
    def test_no_matching_group(self):
        principal = {"claims": [{"typ": "groups", "val": "group-other"}]}
        assert get_user_roles(principal) == []


# ---------------------------------------------------------------------------
# is_authenticated_user / is_authorized
# ---------------------------------------------------------------------------

class TestIsAuthenticatedUser:
    def test_reader(self):
        assert is_authenticated_user(["reader"]) is True

    def test_no_roles(self):
        assert is_authenticated_user([]) is False

    def test_unknown_role(self):
        assert is_authenticated_user(["unknown"]) is False


class TestIsAuthorized:
    def test_admin_always(self):
        assert is_authorized(["admin"], "u1", "u2", "u3") is True

    def test_manager_always(self):
        assert is_authorized(["manager"], "u1", "u2", "u3") is True

    def test_claimed_by_self(self):
        assert is_authorized(["reader"], "u1", "u1", "") is True

    def test_released_by_self(self):
        assert is_authorized(["reader"], "u1", "", "u1") is True

    def test_not_authorized(self):
        assert is_authorized(["reader"], "u1", "u2", "u3") is False

    def test_case_insensitive(self):
        assert is_authorized(["reader"], "User1", "user1", "") is True


# ---------------------------------------------------------------------------
# _load_role_groups
# ---------------------------------------------------------------------------

class TestLoadRoleGroups:
    def test_load_from_env(self, monkeypatch):
        monkeypatch.setenv("AZURE_ROLE_GROUP_ADMIN", "group-admin-id")
        groups = auth._load_role_groups()
        assert groups.get("admin") == "group-admin-id"
