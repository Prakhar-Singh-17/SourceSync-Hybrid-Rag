"""Tests for session handling and the HTTP surface.

These run without credentials: the app starts without its lifespan, so no
pipeline is attached and the endpoints that need one report 503. That is
deliberate -- it lets the routing, authentication and error mapping be tested
with no Qdrant cluster and no API key.
"""

import unittest
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.schemas import QueryRequest
from app.sessions import COOKIE_NAME, Session, decode, encode, new_session

SECRET = "test-secret"


class SessionTokenTests(unittest.TestCase):
    def test_round_trip_preserves_identity_and_expiry(self) -> None:
        original = new_session(ttl_minutes=60)
        restored = decode(encode(original, SECRET), SECRET)
        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(restored.id, original.id)
        self.assertEqual(restored.expires_at_unix, original.expires_at_unix)

    def test_a_tampered_session_id_is_rejected(self) -> None:
        token = encode(new_session(60), SECRET)
        session_id, expiry, signature = token.rsplit(".", 2)
        forged = f"{session_id[:-1]}x.{expiry}.{signature}"
        self.assertIsNone(decode(forged, SECRET))

    def test_extending_the_expiry_is_rejected(self) -> None:
        session = new_session(60)
        token = encode(session, SECRET)
        session_id, _, signature = token.rsplit(".", 2)
        far_future = int((datetime.now(UTC) + timedelta(days=365)).timestamp())
        self.assertIsNone(decode(f"{session_id}.{far_future}.{signature}", SECRET))

    def test_a_token_signed_with_another_secret_is_rejected(self) -> None:
        self.assertIsNone(decode(encode(new_session(60), "other-secret"), SECRET))

    def test_an_expired_token_is_rejected(self) -> None:
        expired = Session(id="abc", expires_at=datetime.now(UTC) - timedelta(seconds=1))
        self.assertIsNone(decode(encode(expired, SECRET), SECRET))

    def test_missing_and_malformed_tokens_are_rejected(self) -> None:
        for token in (None, "", "not-a-token", "a.b"):
            with self.subTest(token=token):
                self.assertIsNone(decode(token, SECRET))


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_always_answers(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "sourcesync-api")

    def test_starting_a_session_sets_a_cookie(self) -> None:
        response = self.client.post("/api/session")
        self.assertEqual(response.status_code, 200)
        self.assertIn(COOKIE_NAME, response.cookies)
        self.assertIn("expires_at", response.json())

    def test_reading_a_session_without_a_cookie_is_unauthorised(self) -> None:
        self.assertEqual(self.client.get("/api/session").status_code, 401)

    def test_separate_clients_get_separate_sessions(self) -> None:
        other = TestClient(app)
        self.assertEqual(self.client.post("/api/session").status_code, 200)
        self.assertEqual(other.post("/api/session").status_code, 200)
        self.assertNotEqual(
            self.client.cookies.get(COOKIE_NAME),
            other.cookies.get(COOKIE_NAME),
        )

    def test_an_existing_session_is_reused_rather_than_replaced(self) -> None:
        first = self.client.post("/api/session").json()["expires_at"]
        second = self.client.post("/api/session").json()["expires_at"]
        self.assertEqual(first, second)

    def test_querying_without_a_session_is_unauthorised(self) -> None:
        response = self.client.post("/api/query", json={"question": "what is this?"})
        self.assertEqual(response.status_code, 401)

    def test_querying_with_a_session_but_no_backend_reports_unavailable(self) -> None:
        self.client.post("/api/session")
        response = self.client.post("/api/query", json={"question": "what is this?"})
        self.assertEqual(response.status_code, 503)

    def test_short_questions_are_rejected_by_validation(self) -> None:
        # Asserted against the schema rather than the endpoint: FastAPI resolves
        # dependencies before validating the body, so on a server with no
        # credentials the 503 from the pipeline dependency arrives first.
        with self.assertRaises(ValidationError):
            QueryRequest(question="hi")
        self.assertEqual(QueryRequest(question="what is this?").question, "what is this?")


if __name__ == "__main__":
    unittest.main()
