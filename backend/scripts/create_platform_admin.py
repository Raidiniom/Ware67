"""Create a WARE67 platform admin (the team that manages companies and API keys).

Run from backend/, against whatever DATABASE_URL backend/.env points at:

    python scripts/create_platform_admin.py --email platform_dev1@ware67.com --name "Platform Dev 1"

The password is asked for interactively and never echoed, so it doesn't end up
in shell history or in the repository.
"""
import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.models  # noqa: E402,F401 - registers all SQLAlchemy models
from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.audit_log import AuditLog  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402

MIN_PASSWORD_LENGTH = 8


def read_password() -> str:
    while True:
        password = getpass.getpass("Password: ")
        if len(password) < MIN_PASSWORD_LENGTH:
            print(f"Must be at least {MIN_PASSWORD_LENGTH} characters.")
            continue
        if password != getpass.getpass("Repeat password: "):
            print("Passwords don't match.")
            continue
        return password


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    email = args.email.strip().lower()

    db = SessionLocal()
    try:
        if db.query(User.id).filter(User.email == email).first():
            print(f"An account with {email} already exists; nothing changed.")
            return 1

        user = User(
            name=args.name.strip(),
            email=email,
            password=hash_password(read_password()),
            # role is a company role and means nothing without a company;
            # GUEST is just the column's harmless default.
            role=UserRole.GUEST,
            company_id=None,
            is_platform_admin=True,
        )
        db.add(user)
        db.flush()
        db.add(AuditLog(user_id=user.id, action="CREATE_PLATFORM_ADMIN", entity="USER",
                        entity_id=user.id, details={"email": email, "via": "create_platform_admin.py"}))
        db.commit()
        print(f"Created platform admin {email}.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
