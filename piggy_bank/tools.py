import json
import logging
import sqlite3
from typing import Any, Dict, List
from flask import g
from openai.types.chat import ChatCompletionMessageToolCall
from piggy_bank.services import (
    add_account,
    list_accounts,
    get_balance,
    get_transactions,
    add_money,
    withdraw_money,
    transfer_money,
)


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
                        "subscription_id": {
                            "type": "integer",
                            "description": "The subscription ID for the account.",
                        },
                    },
                    "required": ["name", "subscription_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_accounts",
                "description": "Lists all accounts in the piggy bank.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subscription_id": {
                            "type": "integer",
                            "description": "The subscription ID.",
                        },
                    },
                    "required": ["subscription_id"],
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
                        "name": {
                            "type": "string",
                            "description": "The name of the account.",
                        },
                        "subscription_id": {
                            "type": "integer",
                            "description": "The subscription ID.",
                        },
                    },
                    "required": ["name", "subscription_id"],
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
                        "name": {
                            "type": "string",
                            "description": "The name of the account.",
                        },
                        "subscription_id": {
                            "type": "integer",
                            "description": "The subscription ID.",
                        },
                    },
                    "required": ["name", "subscription_id"],
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
                        "name": {
                            "type": "string",
                            "description": "The name of the account.",
                        },
                        "amount": {
                            "type": "number",
                            "description": "The amount of money to add.",
                        },
                        "reason": {
                            "type": "string",
                            "description": "The reason for adding the money.",
                        },
                        "subscription_id": {
                            "type": "integer",
                            "description": "The subscription ID.",
                        },
                    },
                    "required": ["name", "amount", "reason", "subscription_id"],
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
                        "name": {
                            "type": "string",
                            "description": "The name of the account.",
                        },
                        "amount": {
                            "type": "number",
                            "description": "The amount of money to withdraw.",
                        },
                        "reason": {
                            "type": "string",
                            "description": "The reason for withdrawing the money.",
                        },
                        "subscription_id": {
                            "type": "integer",
                            "description": "The subscription ID.",
                        },
                    },
                    "required": ["name", "amount", "reason", "subscription_id"],
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
                        "from_name": {
                            "type": "string",
                            "description": "The name of the account to transfer from.",
                        },
                        "to_name": {
                            "type": "string",
                            "description": "The name of the account to transfer to.",
                        },
                        "amount": {
                            "type": "number",
                            "description": "The amount of money to transfer.",
                        },
                        "reason": {
                            "type": "string",
                            "description": "The reason for the transfer.",
                        },
                        "subscription_id": {
                            "type": "integer",
                            "description": "The subscription ID.",
                        },
                    },
                    "required": [
                        "from_name",
                        "to_name",
                        "amount",
                        "reason",
                        "subscription_id",
                    ],
                },
            },
        },
    ]


def run_tools(db: sqlite3.Connection, tool_calls: List[ChatCompletionMessageToolCall]) -> List[Dict[str, Any]]:
    tool_outputs = []
    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        kwargs = json.loads(tool_call.function.arguments)
        # Inject subscription_id from Flask context if available
        if hasattr(g, "subscription_id"):
            kwargs["subscription_id"] = g.subscription_id
        logging.info("subscription_id: %s", g.subscription_id)

        if tool_name == "add_account":
            result = add_account(
                db=db,
                name=str(kwargs.get("name")),
                subscription_id=kwargs.get("subscription_id"),
            )
        elif tool_name == "list_accounts":
            result = list_accounts(db=db, subscription_id=kwargs.get("subscription_id"))
        elif tool_name == "get_balance":
            result = get_balance(
                db=db,
                name=str(kwargs.get("name")),
                subscription_id=kwargs.get("subscription_id"),
            )
        elif tool_name == "get_transactions":
            result = get_transactions(
                db=db,
                name=str(kwargs.get("name")),
                subscription_id=kwargs.get("subscription_id"),
            )
        elif tool_name == "add_money":
            result = add_money(
                db=db,
                name=str(kwargs.get("name")),
                amount=float(kwargs.get("amount") or 0.0),
                reason=str(kwargs.get("reason")),
                subscription_id=kwargs.get("subscription_id"),
            )
        elif tool_name == "withdraw_money":
            result = withdraw_money(
                db=db,
                name=str(kwargs.get("name")),
                amount=float(kwargs.get("amount") or 0.0),
                reason=str(kwargs.get("reason")),
                subscription_id=kwargs.get("subscription_id"),
            )
        elif tool_name == "transfer_money":
            result = transfer_money(
                db=db,
                from_name=str(kwargs.get("from_name")),
                to_name=str(kwargs.get("to_name")),
                amount=float(kwargs.get("amount") or 0.0),
                reason=str(kwargs.get("reason")),
                subscription_id=kwargs.get("subscription_id"),
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
