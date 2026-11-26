import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from models.access import DocumentClassification, UserRole
from services.auth_service import (
    ACCESS_DENIED_MESSAGE,
    AccountPendingError,
    AuthService,
)
from utils.passwords import hash_password, verify_password


class AuthServiceRBACTests(unittest.TestCase):
    def setUp(self) -> None:
        self.auth = AuthService()

    def test_allowed_classifications_match_role_matrix(self) -> None:
        expected = {
            UserRole.CITIZEN: {DocumentClassification.PUBLIC},
            UserRole.GOVERNMENT_OFFICER: {
                DocumentClassification.PUBLIC,
                DocumentClassification.INTERNAL,
            },
            UserRole.DEPARTMENT_MANAGER: {
                DocumentClassification.PUBLIC,
                DocumentClassification.INTERNAL,
                DocumentClassification.RESTRICTED,
            },
            UserRole.ADMINISTRATOR: set(DocumentClassification),
        }

        for role, classifications in expected.items():
            with self.subTest(role=role):
                user = SimpleNamespace(role=role, is_active=True)
                self.assertEqual(
                    set(self.auth.allowed_classifications(user)),
                    classifications,
                )

    def test_unauthorized_upload_and_view_are_denied(self) -> None:
        citizen = SimpleNamespace(role=UserRole.CITIZEN, is_active=True)

        with self.assertRaisesRegex(PermissionError, ACCESS_DENIED_MESSAGE):
            self.auth.require_upload_permission(
                citizen, DocumentClassification.CONFIDENTIAL
            )
        with self.assertRaisesRegex(PermissionError, ACCESS_DENIED_MESSAGE):
            self.auth.require_view_permission(
                citizen, DocumentClassification.INTERNAL
            )

    def test_authenticates_active_user_by_email_and_password(self) -> None:
        user = SimpleNamespace(
            id="user-id",
            email="admin@demo.gov.za",
            password_hash=hash_password("a-secure-demo-password"),
            is_active=True,
        )
        session = Mock()
        session.scalar.return_value = user

        self.assertIs(
            self.auth.authenticate(
                session,
                " ADMIN@DEMO.GOV.ZA ",
                "a-secure-demo-password",
            ),
            user,
        )

    def test_rejects_unknown_inactive_and_wrong_password_users(self) -> None:
        session = Mock()
        session.scalar.return_value = None
        self.assertIsNone(self.auth.authenticate(session, "missing@example.com", "x"))

        user = SimpleNamespace(
            password_hash=hash_password("a-secure-demo-password"),
            is_active=False,
        )
        session.scalar.return_value = user
        with self.assertRaisesRegex(
            AccountPendingError, "awaiting administrator approval"
        ):
            self.auth.authenticate(
                session, "admin@demo.gov.za", "a-secure-demo-password"
            )

        user.is_active = True
        self.assertIsNone(
            self.auth.authenticate(session, "admin@demo.gov.za", "wrong-password")
        )

    def test_password_hashes_are_salted_and_require_minimum_length(self) -> None:
        password = "a-secure-demo-password"
        first_hash = hash_password(password)
        second_hash = hash_password(password)

        self.assertTrue(first_hash.startswith("$2b$"))
        self.assertNotEqual(first_hash, second_hash)
        self.assertTrue(verify_password(password, first_hash))
        self.assertFalse(verify_password("different-password", first_hash))
        self.assertFalse(verify_password(password, None))
        with self.assertRaises(ValueError):
            hash_password("too-short")
        with self.assertRaises(ValueError):
            hash_password("é" * 37)


if __name__ == "__main__":
    unittest.main()
