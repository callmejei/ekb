"""Identity and security trimming.

Local auth is the X-User header resolved against the users table — behind `current_user` so
Keycloak (OIDC) can replace it. Every retrieval builds its filters here; no store query runs
without the caller's access groups applied.
"""

from dataclasses import dataclass
from datetime import date

from fastapi import Header, HTTPException

from .db import fetch_one


@dataclass(frozen=True)
class User:
    username: str
    display_name: str
    roles: tuple[str, ...]
    access_groups: tuple[str, ...]

    def has_role(self, role: str) -> bool:
        return role in self.roles or "ADMIN" in self.roles


def load_user(username: str) -> User | None:
    row = fetch_one("SELECT * FROM users WHERE username = %s", (username,))
    if not row:
        return None
    return User(row["username"], row["display_name"], tuple(row["roles"]), tuple(row["access_groups"]))


def current_user(x_user: str | None = Header(default=None)) -> User:
    if not x_user:
        raise HTTPException(401, "Missing X-User header")
    user = load_user(x_user)
    if not user:
        raise HTTPException(401, f"Unknown user {x_user!r}")
    return user


def es_mandatory_filter(user: User, today: date | None = None) -> list[dict]:
    """is_active AND in validity window AND access_group IN user's groups."""
    d = (today or date.today()).isoformat()
    return [
        {"term": {"is_active": True}},
        {"range": {"effective_date": {"lte": d}}},
        {
            "bool": {
                "should": [
                    {"bool": {"must_not": {"exists": {"field": "expiry_date"}}}},
                    {"range": {"expiry_date": {"gte": d}}},
                ],
                "minimum_should_match": 1,
            }
        },
        {"terms": {"access_group": list(user.access_groups)}},
    ]


# Same rule, expressed for Cypher. `x` is the node or relationship variable being filtered.
def cypher_visible(var: str) -> str:
    return (
        f"{var}.is_active = true AND {var}.access_group IN $groups "
        f"AND {var}.effective_date <= $today "
        f"AND ({var}.expiry_date IS NULL OR {var}.expiry_date >= $today)"
    )


def cypher_params(user: User, today: date | None = None) -> dict:
    return {"groups": list(user.access_groups), "today": (today or date.today()).isoformat()}
