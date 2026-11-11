import json
import logging
import sqlite3
from typing import Any, Callable, Dict, List

from openai.types.responses import FunctionToolParam, ResponseFunctionToolCall
from openai.types.responses.response_input_item_param import FunctionCallOutput

from piggy_bank.services import (
    ServiceResult,
    add_account,
    get_balance,
    get_transactions,
    add_money,
    withdraw_money,
    transfer_money,
    remove_account,
)

log = logging.getLogger(__name__)

_ACCOUNT_ID = {"type": "integer", "description": "The ID of the account."}


def _function_tool(name: str, description: str, properties: Dict[str, Any]) -> FunctionToolParam:
    """Build a strict Responses API function tool.

    Strict mode makes the model's arguments always match the schema, which requires
    every property to be listed in `required` and `additionalProperties` to be false.
    """
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
        "strict": True,
    }


def get_tools() -> List[FunctionToolParam]:
    return [
        _function_tool(
            "add_account",
            "Adds a new account to the piggy bank.",
            {"name": {"type": "string", "description": "The name of the account to add."}},
        ),
        _function_tool(
            "get_balance",
            "Gets the balance of a specific account.",
            {"account_id": _ACCOUNT_ID},
        ),
        _function_tool(
            "get_transactions",
            "Gets the transaction history for a specific account.",
            {"account_id": _ACCOUNT_ID},
        ),
        _function_tool(
            "add_money",
            "Adds money to a specific account.",
            {
                "account_id": _ACCOUNT_ID,
                "amount": {"type": "number", "description": "The amount of money to add."},
                "reason": {"type": "string", "description": "The reason for adding the money."},
            },
        ),
        _function_tool(
            "withdraw_money",
            "Withdraws money from a specific account.",
            {
                "account_id": _ACCOUNT_ID,
                "amount": {"type": "number", "description": "The amount of money to withdraw."},
                "reason": {"type": "string", "description": "The reason for withdrawing the money."},
            },
        ),
        _function_tool(
            "transfer_money",
            "Transfers money from one account to another.",
            {
                "from_account_id": {"type": "integer", "description": "The ID of the account to transfer from."},
                "to_account_id": {"type": "integer", "description": "The ID of the account to transfer to."},
                "amount": {"type": "number", "description": "The amount of money to transfer."},
                "reason": {"type": "string", "description": "The reason for the transfer."},
            },
        ),
        _function_tool(
            "remove_account",
            "Removes an account and all its associated transactions. " "Account must have zero balance before removal.",
            {"account_id": {"type": "integer", "description": "The ID of the account to remove."}},
        ),
    ]


def _handlers() -> Dict[str, Callable[..., ServiceResult]]:
    # Resolved on each call (not at import time) so tests can patch the service functions.
    return {
        "add_account": add_account,
        "get_balance": get_balance,
        "get_transactions": get_transactions,
        "add_money": add_money,
        "withdraw_money": withdraw_money,
        "transfer_money": transfer_money,
        "remove_account": remove_account,
    }


def _run_tool(db: sqlite3.Connection, subscription_id: int, tool_call: ResponseFunctionToolCall) -> Dict[str, Any]:
    """Run one tool call and return a JSON-serialisable result.

    Failures are returned as {"error": ...} so the model can see what went wrong and
    recover, instead of the whole request failing.
    """
    handler = _handlers().get(tool_call.name)
    if handler is None:
        return {"error": f"Unknown tool: {tool_call.name}"}
    try:
        kwargs = json.loads(tool_call.arguments or "{}")
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON arguments: {e}"}
    try:
        result = handler(db=db, subscription_id=subscription_id, **kwargs)
    except Exception as e:  # noqa: BLE001 - surface any service failure to the model
        log.exception("Tool %s failed", tool_call.name)
        return {"error": f"{type(e).__name__}: {e}"}
    if result["error"]:
        return {"error": result["error"]}
    return result["response"]


def run_tools(
    db: sqlite3.Connection, subscription_id: int, tool_calls: List[ResponseFunctionToolCall]
) -> List[FunctionCallOutput]:
    """Run the model's function calls and return Responses API `function_call_output` items."""
    outputs: List[FunctionCallOutput] = []
    for tool_call in tool_calls:
        log.info("Running tool %s(%s) for subscription %s", tool_call.name, tool_call.arguments, subscription_id)
        outputs.append(
            {
                "type": "function_call_output",
                "call_id": tool_call.call_id,
                "output": json.dumps(_run_tool(db, subscription_id, tool_call)),
            }
        )
    return outputs
