from app.models.user import User
from sqlalchemy import BigInteger, String


def test_user_table_matches_data_dictionary() -> None:
    table = User.__table__

    assert table.name == "users"
    assert set(table.columns.keys()) == {
        "id",
        "username",
        "email",
        "password_hash",
        "role",
        "status",
        "created_at",
        "updated_at",
    }
    assert isinstance(table.c.id.type, BigInteger)
    assert table.c.id.primary_key
    assert isinstance(table.c.username.type, String)
    assert table.c.username.type.length == 50
    assert isinstance(table.c.email.type, String)
    assert table.c.email.type.length == 100
    assert isinstance(table.c.password_hash.type, String)
    assert table.c.password_hash.type.length == 255
    assert table.c.role.type.enums == ["user", "admin"]
    assert table.c.status.type.enums == ["active", "disabled"]


def test_user_unique_indexes_match_data_dictionary() -> None:
    indexes = {index.name: index for index in User.__table__.indexes}

    assert indexes["ix_users_username"].unique
    assert indexes["ix_users_email"].unique
