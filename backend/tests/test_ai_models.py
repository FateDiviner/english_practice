from sqlalchemy import BigInteger, String, Text, UniqueConstraint


def test_ai_model_schemas(tmp_path: object = None) -> None:
    from app.models.ai_conversation import AiConversation
    from app.models.ai_message import AiMessage

    conversation = AiConversation.__table__
    message = AiMessage.__table__

    assert set(conversation.columns.keys()) == {
        "id",
        "user_id",
        "title",
        "scene",
        "created_at",
        "updated_at",
    }
    assert isinstance(conversation.c.id.type, BigInteger)
    assert isinstance(conversation.c.title.type, String)
    assert conversation.c.title.type.length == 100
    assert isinstance(conversation.c.scene.type, String)
    assert conversation.c.scene.type.length == 50
    assert conversation.c.user_id.foreign_keys
    assert next(iter(conversation.c.user_id.foreign_keys)).ondelete == "CASCADE"

    assert set(message.columns.keys()) == {
        "id",
        "conversation_id",
        "role",
        "content",
        "created_at",
    }
    assert isinstance(message.c.id.type, BigInteger)
    assert message.c.role.type.enums == ["user", "assistant"]
    assert isinstance(message.c.content.type, Text)
    assert next(iter(message.c.conversation_id.foreign_keys)).ondelete == "CASCADE"
    assert {index.name for index in message.indexes} == {"idx_ai_messages_conversation"}
    assert not any(isinstance(item, UniqueConstraint) for item in message.constraints)
