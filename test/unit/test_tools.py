import json
import sqlite3
from unittest.mock import patch
from piggy_bank.tools import get_tools, run_tools
from openai.types.chat import ChatCompletionMessageToolCall
from openai.types.chat.chat_completion_message_tool_call import Function
from flask import Flask


def test_get_tools():
    tools = get_tools()
    assert isinstance(tools, list)
    assert len(tools) > 0
    for tool in tools:
        assert "type" in tool
        assert tool["type"] == "function"
        assert "function" in tool
        assert "name" in tool["function"]


@patch("piggy_bank.tools.add_account")
@patch("piggy_bank.tools.get_accounts")
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
    mock_get_accounts,
    mock_add_account,
    app: Flask,
    get_test_db: sqlite3.Connection,
):
    # Mock the service functions
    mock_add_account.return_value = {
        "response": {"message": "Account added"},
        "error": None,
    }
    mock_get_accounts.return_value = {
        "response": {"accounts": ["acc1", "acc2"]},
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
        ChatCompletionMessageToolCall(
            id="1",
            function=Function(
                name="add_account",
                arguments=json.dumps({"name": "test"}),
            ),
            type="function",
        )
    ]

    with app.app_context():
        tool_outputs = run_tools(get_test_db, 1, tool_calls)

    assert len(tool_outputs) == 1
    output = tool_outputs[0]
    assert output["tool_call_id"] == "1"
    assert output["role"] == "tool"
    assert output["name"] == "add_account"
    assert output["content"] == '{"message": "Account added"}'
    mock_add_account.assert_called_once_with(db=get_test_db, name="test", subscription_id=1)
