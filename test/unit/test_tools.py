import json
import sqlite3
from unittest.mock import patch
from piggy_bank.tools import get_tools, run_tools
from openai.types.responses import ResponseFunctionToolCall
from flask import Flask


def test_get_tools():
    tools = get_tools()
    assert isinstance(tools, list)
    assert len(tools) > 0
    for tool in tools:
        assert tool["type"] == "function"
        assert tool["name"]
        assert tool["strict"] is True
        params = tool["parameters"]
        # Strict mode requires every property to be required and no extra properties.
        assert params["additionalProperties"] is False
        assert set(params["required"]) == set(params["properties"])


@patch("piggy_bank.tools.add_account")
@patch("piggy_bank.tools.get_balance")
@patch("piggy_bank.tools.get_transactions")
@patch("piggy_bank.tools.add_money")
@patch("piggy_bank.tools.withdraw_money")
@patch("piggy_bank.tools.transfer_money")
def test_run_tools(
    mock_transfer_money,
    mock_withdraw_money,
    mock_add_money,
    mock_get_transactions,
    mock_get_balance,
    mock_add_account,
    app: Flask,
    get_test_db: sqlite3.Connection,
):
    # Mock the service functions
    mock_add_account.return_value = {
        "response": {"message": "Account added"},
        "error": None,
    }
    mock_get_balance.return_value = {"response": {"balance": 100.0}, "error": None}
    mock_get_transactions.return_value = {
        "response": {"transactions": [{"id": 1, "amount": 50}]},
        "error": None,
    }
    mock_add_money.return_value = {
        "response": {"message": "Money added"},
        "error": None,
    }
    mock_withdraw_money.return_value = {
        "response": {"message": "Money withdrawn"},
        "error": None,
    }
    mock_transfer_money.return_value = {
        "response": {"message": "Money transferred"},
        "error": None,
    }

    tool_calls = [
        ResponseFunctionToolCall(
            call_id="1",
            name="add_account",
            arguments=json.dumps({"name": "test"}),
            type="function_call",
        )
    ]

    with app.app_context():
        tool_outputs = run_tools(get_test_db, 1, tool_calls)

    assert len(tool_outputs) == 1
    output = tool_outputs[0]
    assert output["type"] == "function_call_output"
    assert output["call_id"] == "1"
    assert output["output"] == '{"message": "Account added"}'
    mock_add_account.assert_called_once_with(db=get_test_db, name="test", subscription_id=1)


def _call(name: str, arguments: str) -> ResponseFunctionToolCall:
    return ResponseFunctionToolCall(call_id="c1", name=name, arguments=arguments, type="function_call")


def test_run_tools_unknown_tool_returns_error(get_test_db: sqlite3.Connection):
    [output] = run_tools(get_test_db, 1, [_call("nope", "{}")])
    assert json.loads(output["output"]) == {"error": "Unknown tool: nope"}


def test_run_tools_bad_json_returns_error(get_test_db: sqlite3.Connection):
    [output] = run_tools(get_test_db, 1, [_call("get_balance", "{not json")])
    assert "Invalid JSON arguments" in json.loads(output["output"])["error"]


@patch("piggy_bank.tools.get_balance")
def test_run_tools_service_error_and_exception(mock_get_balance, get_test_db: sqlite3.Connection):
    mock_get_balance.return_value = {"response": None, "error": "Account not found"}
    [output] = run_tools(get_test_db, 1, [_call("get_balance", '{"account_id": 9}')])
    assert json.loads(output["output"]) == {"error": "Account not found"}

    mock_get_balance.side_effect = RuntimeError("db locked")
    [output] = run_tools(get_test_db, 1, [_call("get_balance", '{"account_id": 9}')])
    assert json.loads(output["output"]) == {"error": "RuntimeError: db locked"}
