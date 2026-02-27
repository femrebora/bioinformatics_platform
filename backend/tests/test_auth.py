"""Tests for the /api/v1/auth endpoints."""
import pytest


@pytest.mark.asyncio
async def test_register_and_login(client):
    """Full register → login flow."""
    email = "newuser@example.com"
    password = "securepass99"

    # Register
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["email"] == email
    assert "id" in data

    # Duplicate registration
    resp2 = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert resp2.status_code == 400

    # Login with correct credentials
    resp3 = await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert resp3.status_code == 200, resp3.text
    assert "access_token" in resp3.json()

    # Login with wrong password
    resp4 = await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "wrongpassword"},
    )
    assert resp4.status_code == 401


@pytest.mark.asyncio
async def test_register_short_password(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "password": "abc"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_with_token(client, auth_headers):
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@example.com"
