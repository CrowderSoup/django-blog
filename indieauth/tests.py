import base64
import hashlib
from urllib.parse import parse_qs, urlparse
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import IndieAuthAccessToken, IndieAuthAuthorizationCode, IndieAuthClient
from . import views


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class IndieAuthMetadataTests(TestCase):
    def test_metadata_endpoints(self):
        for name in ("indieauth-metadata", "indieauth-oauth-authorization-server"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIn("authorization_endpoint", payload)
            self.assertIn("token_endpoint", payload)
            self.assertIn("issuer", payload)


class IndieAuthFlowTests(TestCase):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(
            username="author",
            email="author@example.com",
            password="pass1234",
        )
        self.client_id = "https://client.example"
        self.redirect_uri = "https://client.example/callback"
        IndieAuthClient.objects.create(
            client_id=self.client_id,
            name="Client App",
            redirect_uris=[self.redirect_uri],
        )

    def _authorize_url(self, **overrides):
        verifier = overrides.get("code_verifier", "verifier123")
        params = {
            "me": overrides.get("me", "http://testserver/"),
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": "state123",
            "scope": "create update",
            "code_challenge": _code_challenge(verifier),
            "code_challenge_method": "S256",
        }
        params.update({k: v for k, v in overrides.items() if k not in {"code_verifier"}})
        return reverse("indieauth-authorize"), params

    def test_authorize_requires_pkce(self):
        self.client.force_login(self.user)
        url, params = self._authorize_url()
        params.pop("code_challenge")
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "PKCE", status_code=400)

    def test_authorize_and_token_exchange(self):
        self.client.force_login(self.user)
        verifier = "verifier123"
        url, params = self._authorize_url(code_verifier=verifier)
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)

        post_data = {
            "client_id": params["client_id"],
            "redirect_uri": params["redirect_uri"],
            "me": params["me"],
            "scope": params["scope"],
            "state": params["state"],
            "code_challenge": params["code_challenge"],
            "code_challenge_method": "S256",
            "decision": "approve",
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        parsed = urlparse(response["Location"])
        query = parse_qs(parsed.query)
        self.assertIn("code", query)

        token_response = self.client.post(
            reverse("indieauth-token"),
            {
                "grant_type": "authorization_code",
                "code": query["code"][0],
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "code_verifier": verifier,
            },
        )
        self.assertEqual(token_response.status_code, 200)
        payload = token_response.json()
        self.assertEqual(payload["me"], params["me"])
        self.assertIn("access_token", payload)

    def test_code_single_use_and_expiry(self):
        code = "code123"
        IndieAuthAuthorizationCode.objects.create(
            code_hash=hashlib.sha256(code.encode("utf-8")).hexdigest(),
            code_challenge=_code_challenge("verifier123"),
            code_challenge_method="S256",
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            me="http://testserver/",
            scope="create",
            user=self.user,
            expires_at=timezone.now() - timezone.timedelta(minutes=1),
        )
        response = self.client.post(
            reverse("indieauth-token"),
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "code_verifier": "verifier123",
            },
        )
        self.assertEqual(response.status_code, 400)

        fresh_code = "code456"
        IndieAuthAuthorizationCode.objects.create(
            code_hash=hashlib.sha256(fresh_code.encode("utf-8")).hexdigest(),
            code_challenge=_code_challenge("verifier456"),
            code_challenge_method="S256",
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            me="http://testserver/",
            scope="create",
            user=self.user,
            expires_at=timezone.now() + timezone.timedelta(minutes=5),
        )
        good_response = self.client.post(
            reverse("indieauth-token"),
            {
                "grant_type": "authorization_code",
                "code": fresh_code,
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "code_verifier": "verifier456",
            },
        )
        self.assertEqual(good_response.status_code, 200)

        reuse_response = self.client.post(
            reverse("indieauth-token"),
            {
                "grant_type": "authorization_code",
                "code": fresh_code,
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "code_verifier": "verifier456",
            },
        )
        self.assertEqual(reuse_response.status_code, 400)

    def test_introspection_and_revocation(self):
        token_value = "token123"
        IndieAuthAccessToken.objects.create(
            token_hash=hashlib.sha256(token_value.encode("utf-8")).hexdigest(),
            client_id=self.client_id,
            me="http://testserver/",
            scope="read",
            user=self.user,
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
        response = self.client.post(reverse("indieauth-introspect"), {"token": token_value})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["active"])

        revoke_response = self.client.post(
            reverse("indieauth-token"),
            {"action": "revoke", "token": token_value},
        )
        self.assertEqual(revoke_response.status_code, 200)

        inactive_response = self.client.post(reverse("indieauth-introspect"), {"token": token_value})
        self.assertEqual(inactive_response.status_code, 200)
        self.assertFalse(inactive_response.json()["active"])


class IndieAuthSecurityTests(TestCase):
    def test_redirect_uri_path_boundary(self):
        client_id = "https://client.example/app"
        self.assertFalse(
            views._redirect_uri_allowed(client_id, "https://client.example/app-evil", None)
        )
        self.assertTrue(
            views._redirect_uri_allowed(client_id, "https://client.example/app", None)
        )
        self.assertTrue(
            views._redirect_uri_allowed(client_id, "https://client.example/app/sub", None)
        )

    def test_client_metadata_blocks_private_hosts(self):
        with mock.patch("indieauth.views._resolve_host_ips", return_value={"127.0.0.1"}):
            with self.assertRaises(ValueError):
                views._fetch_client_metadata("https://client.example")

    def test_client_metadata_size_cap(self):
        class FakeResponse:
            def __init__(self, body: bytes):
                self._body = body
                self.headers = {"Content-Type": "application/json"}

            def read(self, _size=None):
                return self._body

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeOpener:
            def __init__(self, response):
                self._response = response

            def open(self, request, timeout=10):
                return self._response

        oversized = b"x" * (views.MAX_METADATA_BYTES + 1)
        with (
            mock.patch("indieauth.views._resolve_host_ips", return_value={"8.8.8.8"}),
            mock.patch("indieauth.views.build_opener", return_value=FakeOpener(FakeResponse(oversized))),
        ):
            with self.assertRaises(ValueError):
                views._fetch_client_metadata("https://client.example")
