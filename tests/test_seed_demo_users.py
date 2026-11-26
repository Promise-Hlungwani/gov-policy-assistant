import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from database.base import Base
from database.models import UserORM
from scripts.seed_demo_users import DEMO_USERS, _upsert_demo_users
from utils.passwords import hash_password


class SeedDemoUsersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def _password_hashes(self, suffix: str) -> dict[str, str]:
        return {
            email: hash_password(f"{email.split('@')[0]}-{suffix}-password")
            for email, _, _ in DEMO_USERS
        }

    def test_rerun_updates_fixed_accounts_without_duplicates(self) -> None:
        original_hashes = self._password_hashes("original")
        with self.session.begin():
            created = _upsert_demo_users(self.session, original_hashes)

        updated_hashes = self._password_hashes("updated")
        with self.session.begin():
            updated = _upsert_demo_users(self.session, updated_hashes)

        users = self.session.scalars(
            select(UserORM).order_by(UserORM.email)
        ).all()
        self.assertEqual(created, [("Created", email) for email, _, _ in DEMO_USERS])
        self.assertEqual(updated, [("Updated", email) for email, _, _ in DEMO_USERS])
        self.assertEqual(len(users), len(DEMO_USERS))
        for user, (email, display_name, role) in zip(users, sorted(DEMO_USERS)):
            self.assertEqual(user.email, email)
            self.assertEqual(user.display_name, display_name)
            self.assertEqual(user.role, role)
            self.assertEqual(user.password_hash, updated_hashes[email])
            self.assertTrue(user.is_active)


if __name__ == "__main__":
    unittest.main()
