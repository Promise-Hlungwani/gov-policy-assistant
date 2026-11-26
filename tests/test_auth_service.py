import unittest
from types import SimpleNamespace

from models.access import DocumentClassification, UserRole
from services.auth_service import AuthService


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

        with self.assertRaises(PermissionError):
            self.auth.require_upload_permission(
                citizen, DocumentClassification.CONFIDENTIAL
            )
        with self.assertRaises(PermissionError):
            self.auth.require_view_permission(
                citizen, DocumentClassification.INTERNAL
            )


if __name__ == "__main__":
    unittest.main()
