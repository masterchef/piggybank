import json
from unittest.mock import patch, MagicMock

import pytest
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText

import main


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
    mock_process_openai.return_value = "Test response"

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


def _response(*items):
    """A stand-in for a Responses API response with the given output items."""
    resp = MagicMock()
    resp.output = list(items)
    resp.output_text = "".join(
        c.text for i in items if i.type == "message" for c in i.content if c.type == "output_text"
    )
    return resp


def _text(text):
    return ResponseOutputMessage(
        id="msg_1",
        type="message",
        role="assistant",
        status="completed",
        content=[ResponseOutputText(type="output_text", text=text, annotations=[])],
    )


def _call(name, args, call_id):
    return ResponseFunctionToolCall(type="function_call", call_id=call_id, name=name, arguments=json.dumps(args))


@patch("main.run_tools")
@patch("main.client")
def test_process_openai_response_runs_multiple_tool_rounds(mock_client, mock_run_tools, app):
    # Round 1 creates an account, round 2 deposits into it, round 3 answers.
    mock_client.responses.create.side_effect = [
        _response(_call("add_account", {"name": "Tom"}, "c1")),
        _response(_call("add_money", {"account_id": 1, "amount": 5, "reason": "gift"}, "c2")),
        _response(_text("Tom now has $5.00")),
    ]
    mock_run_tools.side_effect = lambda db, sub, calls: [
        {"type": "function_call_output", "call_id": c.call_id, "output": "{}"} for c in calls
    ]
    messages = [{"role": "user", "content": "open Tom an account with $5"}]

    with app.test_request_context():
        assert main.process_openai_response(1, messages) == "Tom now has $5.00"

    assert mock_client.responses.create.call_count == 3
    assert [m.get("type") for m in messages[1:]] == [
        "function_call",
        "function_call_output",
        "function_call",
        "function_call_output",
        "message",
    ]
    kwargs = mock_client.responses.create.call_args.kwargs
    assert kwargs["model"] == main.OPENAI_MODEL
    assert kwargs["store"] is False
    assert kwargs["tools"]  # tools stay available on every round


@patch("main.run_tools", return_value=[])
@patch("main.client")
def test_process_openai_response_stops_after_max_rounds(mock_client, _mock_run_tools, app):
    mock_client.responses.create.return_value = _response(_call("get_balance", {"account_id": 1}, "c1"))
    with app.test_request_context(), pytest.raises(RuntimeError):
        main.process_openai_response(1, [{"role": "user", "content": "loop"}])
    assert mock_client.responses.create.call_count == main.MAX_TOOL_ROUNDS


def test_is_current_format_rejects_chat_completions_history():
    assert main._is_current_format(json.dumps([{"role": "developer", "content": "x"}]))
    assert not main._is_current_format(json.dumps([{"role": "tool", "tool_call_id": "1", "content": "{}"}]))
    assert not main._is_current_format(json.dumps([{"role": "assistant", "tool_calls": []}]))
