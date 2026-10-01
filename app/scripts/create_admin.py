import argparse
import asyncio
from getpass import getpass

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, select

from app.core.database import AsyncSessionFactory, close_database
from app.core.security import hash_password
from app.modules.airports.models import Status
from app.modules.users.models import Role, User, UserRole


async def create_user(
    username: str,
    email: str,
    first_name: str,
    last_name: str,
    role_code: str,
) -> None:
    try:
        email = validate_email(email, check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise ValueError(str(exc)) from exc

    password = getpass("Password: ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise ValueError("Passwords do not match")
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters")

    async with AsyncSessionFactory() as session:
        duplicate = await session.scalar(
            select(User.USER_ID).where(
                (func.lower(User.USERNAME) == username.lower())
                | (func.lower(User.EMAIL) == email.lower())
            )
        )
        if duplicate is not None:
            raise ValueError("A user with this username or email already exists")

        active_status_id = await session.scalar(
            select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME) == "active")
        )
        role_id = await session.scalar(
            select(Role.ROLE_ID).where(Role.CODE == role_code)
        )
        if active_status_id is None or role_id is None:
            raise RuntimeError("Run database migrations before creating a user")

        user = User(
            USERNAME=username,
            EMAIL=email,
            PASSWORD_HASH=hash_password(password),
            FIRST_NAME=first_name,
            LAST_NAME=last_name,
            STATUS_ID=active_status_id,
        )
        session.add(user)
        await session.flush()
        session.add(UserRole(USER_ID=user.USER_ID, ROLE_ID=role_id))
        await session.commit()
        print(f"User '{username}' created with role {role_code}.")


async def async_main(args: argparse.Namespace) -> None:
    try:
        await create_user(
            args.username,
            args.email,
            args.first_name,
            args.last_name,
            args.role,
        )
    finally:
        await close_database()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an Airport GIS user")
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--first-name", required=True)
    parser.add_argument("--last-name", required=True)
    parser.add_argument(
        "--role",
        choices=("ADMIN", "EDITOR", "VIEWER"),
        default="ADMIN",
    )
    args = parser.parse_args()

    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
