def sign_up(client):
    """Create an anonymous account and return bearer headers for it."""
    r = client.post("/v1/auth/anonymous")
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
