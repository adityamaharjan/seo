#!/usr/bin/env python
"""Command-line user administration.

Exists mainly to create the first administrator: the admin API needs an admin
to call it, so the very first one has to be made from the server.

    python -m scripts.manage_users list
    python -m scripts.manage_users promote alice@example.com
    python -m scripts.manage_users demote alice@example.com
    python -m scripts.manage_users disable alice@example.com
    python -m scripts.manage_users enable alice@example.com
"""
import argparse
import asyncio
import sys

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.user import User, UserRole


async def _find(db, email: str) -> User | None:
    res = await db.execute(select(User).where(User.email == email))
    return res.scalar_one_or_none()


async def cmd_list() -> int:
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).order_by(User.id))
        users = list(res.scalars().all())

    if not users:
        print("No users yet.")
        return 0

    print(f"{'ID':>4}  {'USERNAME':<20} {'EMAIL':<32} {'ROLE':<6} STATUS")
    for user in users:
        status = "active" if user.is_active else "disabled"
        print(
            f"{user.id:>4}  {user.username:<20} {user.email:<32} "
            f"{user.role.value:<6} {status}"
        )
    return 0


async def _set(email: str, *, role: UserRole | None = None, active: bool | None = None) -> int:
    async with AsyncSessionLocal() as db:
        user = await _find(db, email)
        if user is None:
            print(f"No user with email {email!r}.", file=sys.stderr)
            return 1
        if role is not None:
            user.role = role
        if active is not None:
            user.is_active = active
        await db.commit()
        state = "active" if user.is_active else "disabled"
        print(f"{user.email} is now role={user.role.value} status={state}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List every account")
    for name, help_text in [
        ("promote", "Grant the admin role"),
        ("demote", "Return the account to a normal user"),
        ("disable", "Block sign-in for the account"),
        ("enable", "Allow sign-in again"),
    ]:
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("email")

    args = parser.parse_args()

    if args.command == "list":
        return asyncio.run(cmd_list())
    if args.command == "promote":
        return asyncio.run(_set(args.email, role=UserRole.admin))
    if args.command == "demote":
        return asyncio.run(_set(args.email, role=UserRole.user))
    if args.command == "disable":
        return asyncio.run(_set(args.email, active=False))
    return asyncio.run(_set(args.email, active=True))


if __name__ == "__main__":
    raise SystemExit(main())
