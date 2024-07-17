import pytest
import os
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.main import app, get_db, msgs, metadata, ssl_context

# Setup test database
TEST_DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"ssl": ssl_context}
)
TestingSessionLocal = sessionmaker(class_=AsyncSession, expire_on_commit=False, bind=engine)

@pytest.fixture(scope="module")
async def test_db():
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)

@pytest.fixture(scope="module")
def test_client(test_db):
    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client

@pytest.mark.asyncio
async def test_post_and_get_text_msg(test_client):
    # Post a text message
    response = test_client.post("/post-text-msg/", json={"receiver": 1, "text_msg": "Hello, World!"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Get the latest text message
    response = test_client.get("/latest-text-msg/")
    assert response.status_code == 200
    assert response.json() == {"text_msg": "Hello, World!"}

@pytest.mark.asyncio
async def test_get_all_text_msgs(test_client):
    # Post multiple text messages
    test_client.post("/post-text-msg/", json={"receiver": 1, "text_msg": "First message"})
    test_client.post("/post-text-msg/", json={"receiver": 2, "text_msg": "Second message"})

    # Get all text messages
    response = test_client.get("/all-text-msgs/")
    assert response.status_code == 200
    assert "First message" in response.json()["text_msgs"]
    assert "Second message" in response.json()["text_msgs"]

@pytest.mark.asyncio
async def test_post_and_get_msg(test_client):
    # Post a message
    response = test_client.post("/post-msg/", json={"receiver": 1, "msg": 42})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Get all messages
    response = test_client.get("/all-msgs/")
    assert response.status_code == 200
    assert 42 in response.json()["msgs"]

@pytest.mark.asyncio
async def test_get_all_messages_html(test_client):
    # Post some messages
    test_client.post("/post-msg/", json={"receiver": 1, "msg": 42})
    test_client.post("/post-text-msg/", json={"receiver": 2, "text_msg": "Hello, World!"})

    # Get all messages as HTML
    response = test_client.get("/all-messages/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<table>" in response.text
    assert "<td>42</td>" in response.text
    assert "<td>Hello, World!</td>" in response.text

@pytest.mark.asyncio
async def test_invalid_json(test_client):
    response = test_client.post("/post-msg/", data="invalid json")
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid JSON"}

# Note: This test might need to be adjusted based on how your application handles database errors
@pytest.mark.asyncio
async def test_database_error_handling(test_client, monkeypatch):
    async def mock_execute(*args, **kwargs):
        raise Exception("Database error")

    monkeypatch.setattr("sqlalchemy.ext.asyncio.AsyncSession.execute", mock_execute)

    response = test_client.post("/post-msg/", json={"receiver": 1, "msg": 42})
    assert response.status_code == 500
    assert "Database error" in response.json()["detail"]