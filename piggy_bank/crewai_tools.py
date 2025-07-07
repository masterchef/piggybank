"""
CrewAI tools for piggy bank operations
"""
import json
import logging
import sqlite3
from typing import Any, Dict
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

# For mock implementation without full CrewAI
try:
    from crewai_tools import BaseTool
    CREWAI_TOOLS_AVAILABLE = True
except ImportError:
    CREWAI_TOOLS_AVAILABLE = False
    
    class BaseTool:
        def __init__(self, name: str, description: str, func=None):
            self.name = name
            self.description = description
            self._func = func
        
        def _run(self, *args, **kwargs):
            if self._func:
                return self._func(*args, **kwargs)
            return "Mock tool execution"


class AddAccountTool(BaseTool):
    """Tool for adding a new account"""
    
    def __init__(self, db_getter, subscription_id_getter):
        self.db_getter = db_getter
        self.subscription_id_getter = subscription_id_getter
        super().__init__(
            name="add_account",
            description="Adds a new account to the piggy bank. Takes 'name' parameter.",
            func=self._execute
        )
    
    def _execute(self, name: str) -> str:
        try:
            db = self.db_getter()
            subscription_id = self.subscription_id_getter()
            result = add_account(db=db, name=name, subscription_id=subscription_id)
            
            if result["error"]:
                return f"Error: {result['error']}"
            else:
                return json.dumps(result["response"])
        except Exception as e:
            return f"Error adding account: {str(e)}"


class GetBalanceTool(BaseTool):
    """Tool for getting account balance"""
    
    def __init__(self, db_getter, subscription_id_getter):
        self.db_getter = db_getter
        self.subscription_id_getter = subscription_id_getter
        super().__init__(
            name="get_balance",
            description="Gets the balance of a specific account. Takes 'account_id' parameter.",
            func=self._execute
        )
    
    def _execute(self, account_id: int) -> str:
        try:
            db = self.db_getter()
            subscription_id = self.subscription_id_getter()
            result = get_balance(db=db, account_id=account_id, subscription_id=subscription_id)
            
            if result["error"]:
                return f"Error: {result['error']}"
            else:
                return json.dumps(result["response"])
        except Exception as e:
            return f"Error getting balance: {str(e)}"


class AddMoneyTool(BaseTool):
    """Tool for adding money to an account"""
    
    def __init__(self, db_getter, subscription_id_getter):
        self.db_getter = db_getter
        self.subscription_id_getter = subscription_id_getter
        super().__init__(
            name="add_money",
            description="Adds money to a specific account. Takes 'account_id', 'amount', and 'reason' parameters.",
            func=self._execute
        )
    
    def _execute(self, account_id: int, amount: float, reason: str) -> str:
        try:
            db = self.db_getter()
            subscription_id = self.subscription_id_getter()
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


class WithdrawMoneyTool(BaseTool):
    """Tool for withdrawing money from an account"""
    
    def __init__(self, db_getter, subscription_id_getter):
        self.db_getter = db_getter
        self.subscription_id_getter = subscription_id_getter
        super().__init__(
            name="withdraw_money",
            description="Withdraws money from a specific account. Takes 'account_id', 'amount', and 'reason' parameters.",
            func=self._execute
        )
    
    def _execute(self, account_id: int, amount: float, reason: str) -> str:
        try:
            db = self.db_getter()
            subscription_id = self.subscription_id_getter()
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


class TransferMoneyTool(BaseTool):
    """Tool for transferring money between accounts"""
    
    def __init__(self, db_getter, subscription_id_getter):
        self.db_getter = db_getter
        self.subscription_id_getter = subscription_id_getter
        super().__init__(
            name="transfer_money",
            description="Transfers money from one account to another. Takes 'from_account_id', 'to_account_id', 'amount', and 'reason' parameters.",
            func=self._execute
        )
    
    def _execute(self, from_account_id: int, to_account_id: int, amount: float, reason: str) -> str:
        try:
            db = self.db_getter()
            subscription_id = self.subscription_id_getter()
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


class GetTransactionsTool(BaseTool):
    """Tool for getting transaction history"""
    
    def __init__(self, db_getter, subscription_id_getter):
        self.db_getter = db_getter
        self.subscription_id_getter = subscription_id_getter
        super().__init__(
            name="get_transactions",
            description="Gets the transaction history for a specific account. Takes 'account_id' parameter.",
            func=self._execute
        )
    
    def _execute(self, account_id: int) -> str:
        try:
            db = self.db_getter()
            subscription_id = self.subscription_id_getter()
            result = get_transactions(db=db, account_id=account_id, subscription_id=subscription_id)
            
            if result["error"]:
                return f"Error: {result['error']}"
            else:
                return json.dumps(result["response"])
        except Exception as e:
            return f"Error getting transactions: {str(e)}"


class GetAccountsTool(BaseTool):
    """Tool for getting all accounts"""
    
    def __init__(self, db_getter, subscription_id_getter):
        self.db_getter = db_getter
        self.subscription_id_getter = subscription_id_getter
        super().__init__(
            name="get_accounts",
            description="Gets all accounts for the current user.",
            func=self._execute
        )
    
    def _execute(self) -> str:
        try:
            db = self.db_getter()
            subscription_id = self.subscription_id_getter()
            result = get_accounts(db=db, subscription_id=subscription_id)
            
            if result["error"]:
                return f"Error: {result['error']}"
            else:
                return json.dumps(result["response"])
        except Exception as e:
            return f"Error getting accounts: {str(e)}"


def create_crewai_tools(db_getter, subscription_id_getter):
    """Create all CrewAI tools for piggy bank operations"""
    return [
        AddAccountTool(db_getter, subscription_id_getter),
        GetBalanceTool(db_getter, subscription_id_getter),
        AddMoneyTool(db_getter, subscription_id_getter),
        WithdrawMoneyTool(db_getter, subscription_id_getter),
        TransferMoneyTool(db_getter, subscription_id_getter),
        GetTransactionsTool(db_getter, subscription_id_getter),
        GetAccountsTool(db_getter, subscription_id_getter),
    ]