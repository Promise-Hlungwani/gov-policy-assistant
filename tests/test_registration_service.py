import unittest
from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from database.base import Base
from database.models import AuditEventORM, UserORM
from models.access import UserRole
from services.registration_service import RegistrationService
from utils.passwords import verify_password


class RegistrationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.service = RegistrationService()
        self.admin_id = uuid4()
        self.admin = UserORM(
            id=self.admin_id,
            auth_subject="local:admin@demo.gov.za",
            email="admin@demo.gov.za",
            display_name="Demo Administrator",
            role=UserRole.ADMINISTRATOR,
            is_active=True,
        )
        self.session.add(self.admin)
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_registration_creates_inactive_user_with_bcrypt_hash(self) -> None:
        user_id = self.service.register(
            self.session,
            email="  NEW.USER@EXAMPLE.GOV.ZA ",
            display_name=" New User ",
            password="a-strong-password",
        )
        user = self.session.get(UserORM, user_id)

        self.assertEqual(user.email, "new.user@example.gov.za")
        self.assertEqual(user.display_name, "New User")
        self.assertEqual(user.role, UserRole.CITIZEN)
        self.assertFalse(user.is_active)
        self.assertTrue(user.password_hash.startswith("$2b$"))
        self.assertTrue(verify_password("a-strong-password", user.password_hash))
        self.assertNotEqual(user.password_hash, "a-strong-password")
        audit_event = self.session.scalar(select(AuditEventORM))
        self.assertIsNone(audit_event.actor_id)
        self.assertEqual(audit_event.action, "user.registration.requested")
        self.assertEqual(audit_event.details, {"email": user.email})

    def test_duplicate_registration_is_rejected_case_insensitively(self) -> None:
        self.service.register(
            self.session,
            email="new.user@example.gov.za",
            display_name="New User",
            password="a-strong-password",
        )
        self.session.rollback()

        with self.assertRaisesRegex(ValueError, "already exists"):
            self.service.register(
                self.session,
                email="NEW.USER@EXAMPLE.GOV.ZA",
                display_name="Another User",
                password="another-strong-password",
            )

        self.session.rollback()
        count = self.session.scalar(
            select(func.count())
            .select_from(UserORM)
            .where(UserORM.email == "new.user@example.gov.za")
        )
        self.assertEqual(count, 1)

    def test_administrator_approval_assigns_role_and_activates_user(self) -> None:
        user_id = self.service.register(
            self.session,
            email="new.user@example.gov.za",
            display_name="New User",
            password="a-strong-password",
        )
        self.session.rollback()

        self.service.approve(
            self.session,
            user_id=user_id,
            role=UserRole.DEPARTMENT_MANAGER,
            approver_id=self.admin_id,
        )
        user = self.session.get(UserORM, user_id)

        self.assertEqual(user.role, UserRole.DEPARTMENT_MANAGER)
        self.assertTrue(user.is_active)
        approval_event = self.session.scalar(
            select(AuditEventORM).where(
                AuditEventORM.action == "user.registration.approved"
            )
        )
        self.assertEqual(approval_event.actor_id, self.admin_id)
        self.assertEqual(
            approval_event.details["assigned_role"],
            UserRole.DEPARTMENT_MANAGER.value,
        )

    def test_approval_of_missing_account_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "no longer awaiting approval"):
            self.service.approve(
                self.session,
                user_id=uuid4(),
                role=UserRole.CITIZEN,
                approver_id=self.admin_id,
            )

    def test_non_administrator_cannot_approve_account(self) -> None:
        user_id = self.service.register(
            self.session,
            email="new.user@example.gov.za",
            display_name="New User",
            password="a-strong-password",
        )
        citizen_id = uuid4()
        citizen = UserORM(
            id=citizen_id,
            auth_subject="local:citizen@demo.gov.za",
            email="citizen@demo.gov.za",
            display_name="Demo Citizen",
            role=UserRole.CITIZEN,
            is_active=True,
        )
        self.session.add(citizen)
        self.session.commit()

        with self.assertRaises(PermissionError):
            self.service.approve(
                self.session,
                user_id=user_id,
                role=UserRole.ADMINISTRATOR,
                approver_id=citizen_id,
            )


if __name__ == "__main__":
    unittest.main()
