"""
CrewAI tools for piggy bank operations
"""
import json
import logging
import sqlite3
from typing import Any, Dict, Callable
from crewai.tools import tool
from piggy_bank.services import (
    add_account,
    get_balance,
    get_transactions,
    add_money,
    withdraw_money,
    transfer_money,
    get_accounts,
)

log = logging.getLogger(__name__)


def create_crewai_tools(db_getter: Callable, subscription_id_getter: Callable):
    """Create all CrewAI tools for piggy bank operations"""
    
    @tool("Add a new account to the piggy bank")
    def add_account_tool(name: str) -> str:
        """Adds a new account to the piggy bank. Takes 'name' parameter."""
        try:
            db = db_getter()
            subscription_id = subscription_id_getter()
            result = add_account(db=db, name=name, subscription_id=subscription_id)
            
            if result["error"]:
                return f"Error: {result['error']}"
            else:
                return json.dumps(result["response"])
        except Exception as e:
            return f"Error adding account: {str(e)}"
    
    @tool("Get the balance of a specific account")
    def get_balance_tool(account_id: int) -> str:
        """Gets the balance of a specific account. Takes 'account_id' parameter."""
        try:
            db = db_getter()
            subscription_id = subscription_id_getter()
            result = get_balance(db=db, account_id=account_id, subscription_id=subscription_id)
            
            if result["error"]:
                return f"Error: {result['error']}"
            else:
                return json.dumps(result["response"])
        except Exception as e:
            return f"Error getting balance: {str(e)}"
    
    @tool("Add money to a specific account")
    def add_money_tool(account_id: int, amount: float, reason: str) -> str:
        """Adds money to a specific account. Takes 'account_id', 'amount', and 'reason' parameters."""
        try:
            db = db_getter()
            subscription_id = subscription_id_getter()
            result = add_money(
                db=db, 
                account_id=account_id, 
                amount=amount, 
                reason=reason, 
                subscription_id=subscription_id
            )
            
            if result["error"]:
                return f"Error: {result['error']}"
            else:
                return json.dumps(result["response"])
        except Exception as e:
            return f"Error adding money: {str(e)}"
    
    @tool("Withdraw money from a specific account")
    def withdraw_money_tool(account_id: int, amount: float, reason: str) -> str:
        """Withdraws money from a specific account. Takes 'account_id', 'amount', and 'reason' parameters."""
        try:
            db = db_getter()
            subscription_id = subscription_id_getter()
            result = withdraw_money(
                db=db, 
                account_id=account_id, 
                amount=amount, 
                reason=reason, 
                subscription_id=subscription_id
            )
            
            if result["error"]:
                return f"Error: {result['error']}"
            else:
                return json.dumps(result["response"])
        except Exception as e:
            return f"Error withdrawing money: {str(e)}"
    
    @tool("Transfer money from one account to another")
    def transfer_money_tool(from_account_id: int, to_account_id: int, amount: float, reason: str) -> str:
        """Transfers money from one account to another. Takes 'from_account_id', 'to_account_id', 'amount', and 'reason' parameters."""
        try:
            db = db_getter()
            subscription_id = subscription_id_getter()
            result = transfer_money(
                db=db, 
                from_account_id=from_account_id,
                to_account_id=to_account_id, 
                amount=amount, 
                reason=reason, 
                subscription_id=subscription_id
            )
            
            if result["error"]:
                return f"Error: {result['error']}"
            else:
                return json.dumps(result["response"])
        except Exception as e:
            return f"Error transferring money: {str(e)}"
    
    @tool("Get transaction history for a specific account")
    def get_transactions_tool(account_id: int) -> str:
        """Gets the transaction history for a specific account. Takes 'account_id' parameter."""
        try:
            db = db_getter()
            subscription_id = subscription_id_getter()
            result = get_transactions(db=db, account_id=account_id, subscription_id=subscription_id)
            
            if result["error"]:
                return f"Error: {result['error']}"
            else:
                return json.dumps(result["response"])
        except Exception as e:
            return f"Error getting transactions: {str(e)}"
    
    @tool("Get all accounts for the current user")
    def get_accounts_tool() -> str:
        """Gets all accounts for the current user."""
        try:
            db = db_getter()
            subscription_id = subscription_id_getter()
            result = get_accounts(db=db, subscription_id=subscription_id)
            
            if result["error"]:
                return f"Error: {result['error']}"
            else:
                return json.dumps(result["response"])
        except Exception as e:
            return f"Error getting accounts: {str(e)}"
    
    return [
        add_account_tool,
        get_balance_tool,
        add_money_tool,
        withdraw_money_tool,
        transfer_money_tool,
        get_transactions_tool,
        get_accounts_tool
    ]