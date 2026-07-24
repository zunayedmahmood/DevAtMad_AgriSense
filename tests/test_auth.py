from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_account_signup_login_flow(client):
    uid = uuid.uuid4().hex[:8]
    email = f"farmer_karim_{uid}@example.com"
    
    # 1. Signup Account (Creates subscribed active account)
    signup_resp = client.post(
        "/v1/auth/signup",
        json={
            "email": email,
            "password": "SecretPassword123",
            "full_name": "Karim Hossain",
        },
    )
    assert signup_resp.status_code == 200
    data = signup_resp.json()
    assert data["email"] == email
    assert data["full_name"] == "Karim Hossain"
    assert data["subscription_status"] == "active"
    farmer_id = data["farmer_id"]

    # Duplicate Signup Error
    dup_resp = client.post(
        "/v1/auth/signup",
        json={
            "email": email,
            "password": "Password456",
            "full_name": "Karim Hossain",
        },
    )
    assert dup_resp.status_code == 400

    # 2. Login Account
    login_resp = client.post(
        "/v1/auth/login",
        json={
            "email": email,
            "password": "SecretPassword123",
        },
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert login_data["farmer_id"] == farmer_id
    assert login_data["subscription_status"] == "active"

    # Invalid Password Login
    wrong_resp = client.post(
        "/v1/auth/login",
        json={
            "email": email,
            "password": "WrongPassword",
        },
    )
    assert wrong_resp.status_code == 401


def test_multi_chat_sessions_per_account(client):
    uid = uuid.uuid4().hex[:8]
    email = f"farmer_multi_{uid}@example.com"

    signup_resp = client.post(
        "/v1/auth/signup",
        json={
            "email": email,
            "password": "Password123",
            "full_name": "Multi Chat Farmer",
        },
    )
    farmer_id = signup_resp.json()["farmer_id"]

    # Create Chat 1
    chat1_resp = client.post(
        f"/v1/farmers/{farmer_id}/chats",
        json={"farmer_id": farmer_id, "title": "Boro Rice Advisory"},
    )
    assert chat1_resp.status_code == 200
    session1_id = chat1_resp.json()["session"]["session_id"]
    assert chat1_resp.json()["session"]["title"] == "Boro Rice Advisory"

    # Create Chat 2
    chat2_resp = client.post(
        f"/v1/farmers/{farmer_id}/chats",
        json={"farmer_id": farmer_id, "title": "Tomato Crop Planning"},
    )
    assert chat2_resp.status_code == 200
    session2_id = chat2_resp.json()["session"]["session_id"]

    # List Farmer Chats
    list_resp = client.get(f"/v1/farmers/{farmer_id}/chats")
    assert list_resp.status_code == 200
    chats = list_resp.json()["chats"]
    session_ids = [c["session_id"] for c in chats]
    assert session1_id in session_ids
    assert session2_id in session_ids


def test_strict_multi_tenant_data_isolation(client):
    uid_a = uuid.uuid4().hex[:8]
    uid_b = uuid.uuid4().hex[:8]

    # Register Farmer A
    farmer_a_resp = client.post(
        "/v1/auth/signup",
        json={
            "email": f"farmer_a_{uid_a}@example.com",
            "password": "PasswordA123",
            "full_name": "Farmer Alice",
        },
    )
    farmer_a_id = farmer_a_resp.json()["farmer_id"]

    # Register Farmer B
    farmer_b_resp = client.post(
        "/v1/auth/signup",
        json={
            "email": f"farmer_b_{uid_b}@example.com",
            "password": "PasswordB123",
            "full_name": "Farmer Bob",
        },
    )
    farmer_b_id = farmer_b_resp.json()["farmer_id"]

    # Create Session for Farmer A
    sess_a_resp = client.post(
        f"/v1/farmers/{farmer_a_id}/chats",
        json={"farmer_id": farmer_a_id, "title": "Alice Secret Session"},
    )
    session_a_id = sess_a_resp.json()["session"]["session_id"]

    # Farmer B attempts to read Farmer A's session -> Should be denied / 404
    forbidden_get = client.get(f"/v1/sessions/{session_a_id}?farmer_id={farmer_b_id}")
    assert forbidden_get.status_code == 404

    # Farmer B attempts to delete Farmer A's session -> Should be denied / 404
    forbidden_del = client.delete(f"/v1/sessions/{session_a_id}?farmer_id={farmer_b_id}")
    assert forbidden_del.status_code == 404

    # Farmer A can read their own session
    allowed_get = client.get(f"/v1/sessions/{session_a_id}?farmer_id={farmer_a_id}")
    assert allowed_get.status_code == 200
    assert allowed_get.json()["farmer_id"] == farmer_a_id
