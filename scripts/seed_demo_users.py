import sys
from getpass import getpass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.models import UserORM
from database.session import get_session, initialize_database
from models.access import UserRole
from utils.passwords import hash_password

DEMO_USERS = (
    ("citizen@demo.gov.za", "Demo Citizen", UserRole.CITIZEN),
    (
        "officer@demo.gov.za",
        "Demo Government Officer",
        UserRole.GOVERNMENT_OFFICER,
    ),
    (
        "manager@demo.gov.za",
        "Demo Department Manager",
        UserRole.DEPARTMENT_MANAGER,
    ),
    ("admin@demo.gov.za", "Demo Administrator", UserRole.ADMINISTRATOR),
)


def _prompt_password(email: str, used_passwords: set[str]) -> str:
    while True:
        password = getpass(f"Set password for {email} (12+ characters): ")
        confirmation = getpass("Confirm password: ")
        if password != confirmation:
            print("Passwords do not match. Try again.")
            continue
        if password in used_passwords:
            print("Each account must have a unique password. Try again.")
            continue
        if len(password) < 12:
            print("Passwords must be at least 12 characters long.")
            continue
        if len(password.encode("utf-8")) > 72:
            print("Passwords must be 72 UTF-8 bytes or fewer for bcrypt.")
            continue
        return password


def _upsert_demo_users(
    session: Session,
    password_hashes: dict[str, str],
) -> list[tuple[str, str]]:
    results = []
    for email, display_name, role in DEMO_USERS:
        user = session.scalar(
            select(UserORM).where(func.lower(UserORM.email) == email)
        )
        action = "Updated"
        if user is None:
            user = UserORM(
                auth_subject=f"local:{email}",
                email=email,
                display_name=display_name,
                password_hash=password_hashes[email],
                role=role,
                is_active=True,
            )
            action = "Created"
        else:
            user.email = email
            user.display_name = display_name
            user.password_hash = password_hashes[email]
            user.role = role
            user.is_active = True
        session.add(user)
        results.append((action, email))
    session.flush()
    return results


def main() -> None:
    initialize_database()
    used_passwords: set[str] = set()
    password_hashes: dict[str, str] = {}
    for email, _, _ in DEMO_USERS:
        password = _prompt_password(email, used_passwords)
        used_passwords.add(password)
        password_hashes[email] = hash_password(password)
    used_passwords.clear()
    password = ""

    with get_session() as session, session.begin():
        results = _upsert_demo_users(session, password_hashes)
    for action, email in results:
        print(f"{action} {email} successfully.")


if __name__ == "__main__":
    main()
