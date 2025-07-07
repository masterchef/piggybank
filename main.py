import os
import logging
import time
import uuid
import json
from typing import Optional, Dict, Any, Union, Tuple, List
from flask import Flask, request, jsonify, g, Response
from dotenv import load_dotenv
from piggy_bank.db import init_db
from piggy_bank.tools import get_tools, run_tools
from piggy_bank.crewai_tools import create_crewai_tools
from piggy_bank.services import get_accounts
import sqlite3

# CrewAI imports (will be replaced with actual CrewAI once installed)
try:
    from crewai import Agent, Task, Crew
    CREWAI_AVAILABLE = True
except ImportError:
    # Fallback for development without CrewAI installed
    CREWAI_AVAILABLE = False
    
    class Agent:
        def __init__(self, role, goal, backstory, tools=None, verbose=False, llm=None):
            self.role = role
            self.goal = goal
            self.backstory = backstory
            self.tools = tools or []
            self.verbose = verbose
            self.llm = llm

    class Task:
        def __init__(self, description, agent, expected_output=None):
            self.description = description
            self.agent = agent
            self.expected_output = expected_output

    class Crew:
        def __init__(self, agents, tasks, verbose=False):
            self.agents = agents
            self.tasks = tasks
            self.verbose = verbose
        
        def kickoff(self, inputs=None):
            # Mock implementation for testing
            return type('CrewOutput', (), {'raw': 'Mock response from CrewAI'})()

    print("Warning: CrewAI not available, using mock implementation")

load_dotenv()

DB_FILE: str = "pigbank.db"

app: Flask = Flask(__name__)
app.config["DATABASE"] = DB_FILE

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

SESSION_TIMEOUT_SECONDS: int = 60

# CrewAI client initialization
crew = None  # Will be initialized in create_piggy_bank_crew()


def get_db() -> sqlite3.Connection:
    """Get a database connection for the current request."""
    if "db" not in g:
        g.db = init_db(app.config["DATABASE"])
    return g.db  # type: ignore


@app.teardown_appcontext
def close_db(exception: Optional[BaseException]) -> None:
    db = g.pop("db", None)
    if db:
        db.close()


# ------------------ AUTH ------------------


def get_subscription_id_from_token(token: str) -> Optional[int]:
    db = get_db()
    cur = db.execute("SELECT id FROM subscriptions WHERE auth_token = ?", (token,))
    row = cur.fetchone()
    return row["id"] if row else None


@app.before_request
def check_auth() -> Optional[Tuple[Response, int]]:
    auth_header: str = request.headers.get("Authorization", "")  # type: ignore
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Authorization header missing."}), 401
    token = auth_header.replace("Bearer ", "", 1)
    subscription_id = get_subscription_id_from_token(token)
    if not subscription_id:
        return jsonify({"error": "Invalid subscription token."}), 401
    g.subscription_id = subscription_id
    return None


# ------------------ CREWAI HELPERS ------------------


def create_piggy_bank_crew():
    """Create and return a CrewAI crew for piggy bank operations."""
    global crew
    if crew is not None:
        return crew
    
    # Create CrewAI tools with proper context
    def get_current_db():
        from flask import g
        return get_db()
    
    def get_current_subscription_id():
        from flask import g
        return g.get("subscription_id")
    
    crewai_tools = create_crewai_tools(get_current_db, get_current_subscription_id)
    
    # Create piggy bank assistant agent
    piggy_bank_agent = Agent(
        role="Piggy Bank Assistant",
        goal="Help users manage their piggy bank accounts efficiently by executing requested operations immediately",
        backstory="""You are a helpful piggy bank assistant that immediately executes all requested operations.
        You have access to tools to manage accounts, add/withdraw money, transfer funds, and check balances.
        When given commands, execute them immediately without asking for confirmation.
        Always provide clear feedback about the operations performed.""",
        tools=crewai_tools,
        verbose=True
    )
    
    # Create crew with the agent
    crew = Crew(
        agents=[piggy_bank_agent],
        tasks=[],  # Tasks will be created dynamically
        verbose=True
    )
    
    return crew


def process_crewai_response(subscription_id: int, messages: List[Dict[str, Any]]) -> Any:
    """Process CrewAI response and handle tool calls if needed."""
    try:
        # Get the user's latest message
        user_message = messages[-1]["content"] if messages else ""
        
        log.info(f"Processing CrewAI request: '{user_message}'")
        
        # Get or create crew
        current_crew = create_piggy_bank_crew()
        
        # For mock implementation, we'll simulate tool execution based on user message
        response_content = simulate_crewai_execution(user_message, subscription_id)
        
        # Create a mock response object similar to OpenAI's structure
        class MockResponse:
            def __init__(self, content):
                self.content = content
            
            def model_dump(self):
                return {"role": "assistant", "content": self.content}
        
        return MockResponse(response_content)
        
    except Exception as e:
        log.error("Error in CrewAI execution: %s", e)
        # Return a fallback response
        class MockResponse:
            def __init__(self, content):
                self.content = content
            
            def model_dump(self):
                return {"role": "assistant", "content": self.content}
        
        return MockResponse(f"I apologize, but I encountered an error processing your request: {str(e)}")


def simulate_crewai_execution(user_message: str, subscription_id: int) -> str:
    """Simulate CrewAI execution by parsing user intent and executing appropriate tools."""
    user_lower = user_message.lower()
    
    try:
        db = get_db()
        
        log.info(f"Processing message: '{user_message}', lower: '{user_lower}'")
        
        # Create account
        if "create" in user_lower and "account" in user_lower:
            # Extract account name - simplified parsing
            account_name = "savings"  # default
            
            # Look for common account types first
            words = user_message.lower().split()
            types = ["emergency", "vacation", "retirement", "checking", "savings"]
            for account_type in types:
                if account_type in words:
                    account_name = account_type
                    break
            
            # Look for "called X" or "named X" patterns
            import re
            called_match = re.search(r'(?:called|named)\s+([\w\s]+?)(?:\s+(?:for|account)|$)', user_message, re.IGNORECASE)
            if called_match:
                account_name = called_match.group(1).strip()
            
            # Look for quoted names
            quote_match = re.search(r'["\']([^"\']+)["\']', user_message)
            if quote_match:
                account_name = quote_match.group(1).strip()
            
            from piggy_bank.services import add_account
            result = add_account(db=db, name=account_name, subscription_id=subscription_id)
            
            if result["error"]:
                return f"Sorry, I couldn't create the account: {result['error']}"
            else:
                return f"Great! I've created a new account named '{account_name}' for you. Account ID: {result['response']['account_id']}"
        
        # Get accounts / list accounts
        elif any(phrase in user_lower for phrase in ["show", "list", "get", "what"]) and "account" in user_lower:
            from piggy_bank.services import get_accounts
            result = get_accounts(db=db, subscription_id=subscription_id)
            
            if result["error"]:
                return f"Sorry, I couldn't retrieve your accounts: {result['error']}"
            else:
                accounts = result["response"]["accounts"]
                if not accounts:
                    return "You don't have any accounts yet. Would you like me to create one for you?"
                else:
                    account_list = []
                    for account in accounts:
                        account_list.append(f"- {account['name']}: ${account['balance']:.2f} (ID: {account['id']})")
                    return f"Here are your accounts:\n" + "\n".join(account_list)
        
        # Add money
        elif ("add" in user_lower and "$" in user_message):
            # Simple parsing - look for amount and account
            import re
            amount_match = re.search(r'\$?(\d+(?:\.\d{2})?)', user_message)
            amount = float(amount_match.group(1)) if amount_match else 100.0
            
            # Get first account for simplicity
            from piggy_bank.services import get_accounts, add_money
            accounts_result = get_accounts(db=db, subscription_id=subscription_id)
            
            if accounts_result["error"] or not accounts_result["response"]["accounts"]:
                return "You need to create an account first. Would you like me to create one for you?"
            
            account = accounts_result["response"]["accounts"][0]
            account_id = account["id"]
            
            result = add_money(
                db=db,
                account_id=account_id,
                amount=amount,
                reason="Manual deposit",
                subscription_id=subscription_id
            )
            
            if result["error"]:
                return f"Sorry, I couldn't add the money: {result['error']}"
            else:
                return f"Successfully added ${amount:.2f} to your {account['name']} account. New balance: ${result['response']['balance']:.2f}"
        
        # Get balance
        elif "balance" in user_lower:
            from piggy_bank.services import get_accounts
            result = get_accounts(db=db, subscription_id=subscription_id)
            
            if result["error"] or not result["response"]["accounts"]:
                return "You don't have any accounts yet. Would you like me to create one for you?"
            
            accounts = result["response"]["accounts"]
            if len(accounts) == 1:
                account = accounts[0]
                return f"Your {account['name']} account balance is ${account['balance']:.2f}"
            else:
                balance_list = []
                for account in accounts:
                    balance_list.append(f"- {account['name']}: ${account['balance']:.2f}")
                return f"Here are your account balances:\n" + "\n".join(balance_list)
        
        # Default response
        else:
            return """Hello! I'm your piggy bank assistant. I can help you with:
- Creating accounts ("Create a savings account")
- Checking balances ("What's my balance?")
- Adding money ("Add $50 to my account")
- Listing accounts ("Show me my accounts")

What would you like to do?"""
    
    except Exception as e:
        log.error("Error in simulated execution: %s", e)
        return f"I encountered an error: {str(e)}"


# ------------------ SESSION HELPERS ------------------


def get_or_create_session(
    session_id: Optional[str], now: float, subscription_id: int
) -> Tuple[str, List[Dict[str, Any]]]:
    """Get existing session or create a new one, returning session_id and messages."""
    db = get_db()
    # If session_id is provided and exists, use it
    if session_id:
        log.info("Looking for existing session: %s", session_id)
        cur = db.execute(
            "SELECT messages, last_access FROM sessions WHERE id = ? AND subscription_id = ?",
            (session_id, subscription_id),
        )
        row = cur.fetchone()
        if row and now - row["last_access"] < SESSION_TIMEOUT_SECONDS:
            # Update last access time
            db.execute("UPDATE sessions SET last_access = ? WHERE id = ?", (now, session_id))
            db.commit()
            log.info("Using existing session: %s", session_id)
            return session_id, json.loads(row["messages"])
        elif row:
            # Session has expired, delete it
            db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            db.commit()
            log.info("Session %s expired, deleted", session_id)

    # Try to find the most recent active session for this subscription
    cur = db.execute(
        "SELECT id, messages, last_access FROM sessions WHERE subscription_id = ? ORDER BY last_access DESC LIMIT 1",
        (subscription_id,),
    )
    row = cur.fetchone()
    if row and now - row["last_access"] < SESSION_TIMEOUT_SECONDS:
        # Update last access time
        db.execute("UPDATE sessions SET last_access = ? WHERE id = ?", (now, row["id"]))
        db.commit()
        log.info("Resuming most recent session: %s", row["id"])
        return row["id"], json.loads(row["messages"])

    # Create a new session
    new_session_id = str(uuid.uuid4())
    log.info("Creating new session: %s", new_session_id)

    # Get current accounts for this subscription
    accounts_result = get_accounts(db, subscription_id)
    accounts_info = ""
    if accounts_result["error"] is None and accounts_result["response"]["accounts"]:
        accounts_list = []
        for account in accounts_result["response"]["accounts"]:
            accounts_list.append(f"- {account['name']}: ${account['balance']:.2f} (ID: {account['id']})")
        accounts_info = "\n\nCurrent accounts:\n" + "\n".join(accounts_list)
    else:
        accounts_info = "\n\nNo accounts currently exist."

    messages = [
        {
            "role": "system",
            "content": f"""You are a helpful piggy bank assistant that immediately executes all requested operations.
            You have access to a set of tools to manage accounts, and you can call multiple tools in parallel.

            IMPORTANT: Do NOT ask for verification or user approval - execute all requested actions immediately.
            When given multi-step commands (like "add money and transfer"), execute ALL steps in the same response.
            Do NOT plan or explain what you will do - just do it immediately.
            
            If money was added, transferred or withdrawn, you should always return the updated balance after all operations are complete.{accounts_info}""",
        }
    ]

    db.execute(
        "INSERT INTO sessions (id, subscription_id, messages, last_access) VALUES (?, ?, ?, ?)",
        (new_session_id, subscription_id, json.dumps(messages), now),
    )
    db.commit()
    return new_session_id, messages


def update_session_messages(session_id: str, messages: List[Dict[str, Any]]) -> None:
    """Update the messages for a session in the database."""
    db = get_db()
    db.execute(
        "UPDATE sessions SET messages = ?, last_access = ? WHERE id = ?",
        (json.dumps(messages), time.time(), session_id),
    )
    db.commit()


def cleanup_expired_sessions() -> None:
    """Remove expired sessions from the database."""
    cutoff_time = time.time() - SESSION_TIMEOUT_SECONDS
    db = get_db()
    cur = db.execute("DELETE FROM sessions WHERE last_access < ?", (cutoff_time,))
    deleted_count = cur.rowcount
    db.commit()
    if deleted_count > 0:
        log.info("Cleaned up %s expired sessions", deleted_count)


# ------------------ ROUTES ------------------


@app.route("/agent", methods=["POST"])
def agent() -> Union[Response, Tuple[Response, int]]:
    data: Dict[str, Any] = request.json or {}
    user_query: Optional[str] = data.get("query")
    session_id: Optional[str] = data.get("session_id")
    subscription_id = g.get("subscription_id")
    if not user_query:
        return jsonify({"error": "Query is required"}), 400

    try:
        # Get or create session and retrieve conversation history
        session_id, messages = get_or_create_session(session_id, time.time(), subscription_id)

        # Add user query to conversation
        messages.append({"role": "user", "content": user_query})

        # Process CrewAI response and handle tool calls
        response_message = process_crewai_response(subscription_id, messages)

        # Update session with new messages
        update_session_messages(session_id, messages)

        return jsonify({"response": response_message.content, "session_id": session_id})

    except Exception as e:
        log.error("Error in CrewAI integration: %s", e)
        return jsonify({"error": str(e)}), 500


# ------------------ MAIN ------------------

if __name__ == "__main__":
    with app.app_context():
        cleanup_expired_sessions()  # Clean up any expired sessions on startup
    app.run(host="0.0.0.0", port=5000)
