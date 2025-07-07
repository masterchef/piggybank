import json
import logging
import sqlite3
from typing import Any, Dict, List, Union
from piggy_bank.services import (
    add_account,
    get_balance,
    get_transactions,
    add_money,
    withdraw_money,
    transfer_money,
)

log = logging.getLogger(__name__)

# Mock tool call structure for CrewAI compatibility
class MockToolCall:
    def __init__(self, tool_name: str, arguments: str, tool_call_id: str = None):
        self.function = type('Function', (), {'name': tool_name, 'arguments': arguments})()
        self.id = tool_call_id or f"call_{tool_name}"


def get_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "add_account",
                "description": "Adds a new account to the piggy bank.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name of the account to add.",
                        },
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_balance",
                "description": "Gets the balance of a specific account.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {
                            "type": "integer",
                            "description": "The ID of the account.",
                        },
                    },
                    "required": ["account_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_transactions",
                "description": "Gets the transaction history for a specific account.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {
                            "type": "integer",
                            "description": "The ID of the account.",
                        },
                    },
                    "required": ["account_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "add_money",
                "description": "Adds money to a specific account.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {
                            "type": "integer",
                            "description": "The ID of the account.",
                        },
                        "amount": {
                            "type": "number",
                            "description": "The amount of money to add.",
                        },
                        "reason": {
                            "type": "string",
                            "description": "The reason for adding the money.",
                        },
                    },
                    "required": ["account_id", "amount", "reason"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "withdraw_money",
                "description": "Withdraws money from a specific account.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {
                            "type": "integer",
                            "description": "The ID of the account.",
                        },
                        "amount": {
                            "type": "number",
                            "description": "The amount of money to withdraw.",
                        },
                        "reason": {
                            "type": "string",
                            "description": "The reason for withdrawing the money.",
                        },
                    },
                    "required": ["account_id", "amount", "reason"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "transfer_money",
                "description": "Transfers money from one account to another.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "from_account_id": {
                            "type": "integer",
                            "description": "The ID of the account to transfer from.",
                        },
                        "to_account_id": {
                            "type": "integer",
                            "description": "The ID of the account to transfer to.",
                        },
                        "amount": {
                            "type": "number",
                            "description": "The amount of money to transfer.",
                        },
                        "reason": {
                            "type": "string",
                            "description": "The reason for the transfer.",
                        },
                    },
                    "required": [
                        "from_account_id",
                        "to_account_id",
                        "amount",
                        "reason",
                    ],
                },
            },
        },
    ]


def run_tools(
    db: sqlite3.Connection, subscription_id: int, tool_calls: Union[List[MockToolCall], List[Any]]
) -> List[Dict[str, Any]]:
    tool_outputs = []
    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        kwargs = json.loads(tool_call.function.arguments)
        # Inject subscription_id from Flask context if available
        log.info("subscription_id: %s", subscription_id)

        if tool_name == "add_account":
            result = add_account(
                db=db,
                name=str(kwargs.get("name")),
                subscription_id=subscription_id,
            )
        elif tool_name == "get_balance":
            result = get_balance(
                db=db,
                account_id=int(kwargs.get("account_id")),
                subscription_id=subscription_id,
            )
        elif tool_name == "get_transactions":
            result = get_transactions(
                db=db,
                account_id=int(kwargs.get("account_id")),
                subscription_id=subscription_id,
            )
        elif tool_name == "add_money":
            result = add_money(
                db=db,
                account_id=int(kwargs.get("account_id")),
                amount=float(kwargs.get("amount") or 0.0),
                reason=str(kwargs.get("reason")),
                subscription_id=subscription_id,
            )
        elif tool_name == "withdraw_money":
            result = withdraw_money(
                db=db,
                account_id=int(kwargs.get("account_id")),
                amount=float(kwargs.get("amount") or 0.0),
                reason=str(kwargs.get("reason")),
                subscription_id=subscription_id,
            )
        elif tool_name == "transfer_money":
            result = transfer_money(
                db=db,
                from_account_id=int(kwargs.get("from_account_id")),
                to_account_id=int(kwargs.get("to_account_id")),
                amount=float(kwargs.get("amount") or 0.0),
                reason=str(kwargs.get("reason")),
                subscription_id=subscription_id,
            )
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

        if result["error"]:
            tool_output = json.dumps({"error": result["error"]})
        else:
            tool_output = json.dumps(result["response"])

        tool_outputs.append(
            {
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": tool_name,
                "content": tool_output,
            }
        )
    return tool_outputs
