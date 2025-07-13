from unittest.mock import patch, MagicMock


def test_check_auth_missing_header(client):
    response = client.post("/agent", json={"query": "test"})
    assert response.status_code == 401
    assert "Authorization header missing" in response.get_data(as_text=True)


def test_check_auth_invalid_token(client):
    response = client.post(
        "/agent",
        headers={"Authorization": "Bearer invalid_token"},
        json={"query": "test"},
    )
    assert response.status_code == 401
    assert "Invalid subscription token" in response.get_data(as_text=True)


@patch("main.process_openai_response")
def test_agent_endpoint_success(mock_process_openai, client):
    mock_process_openai.return_value = MagicMock(content="Test response")

    response = client.post(
        "/agent",
        headers={"Authorization": "Bearer test_token"},
        json={"query": "hello"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["response"] == "Test response"
    assert "session_id" in data


def test_agent_endpoint_no_query(client):
    response = client.post(
        "/agent",
        headers={"Authorization": "Bearer test_token"},
        json={},
    )
    assert response.status_code == 400
    assert "Query is required" in response.get_data(as_text=True)


@patch("main.get_or_create_session")
def test_agent_endpoint_exception(mock_get_session, client):
    mock_get_session.side_effect = Exception("Test DB error")
    response = client.post(
        "/agent",
        headers={"Authorization": "Bearer test_token"},
        json={"query": "hello"},
    )
    assert response.status_code == 500
    assert "Test DB error" in response.get_data(as_text=True)
