import os
import logging
import time
import uuid
import json
from typing import Optional, Dict, Any, Union, Tuple, List
from flask import Flask, request, jsonify, g, Response
from openai import OpenAI
from dotenv import load_dotenv
from piggy_bank.db import init_db
from piggy_bank.tools import get_tools, run_tools
from piggy_bank.services import get_accounts
import sqlite3

load_dotenv()

DB_FILE: str = "pigbank.db"

app: Flask = Flask(__name__)
app.config["DATABASE"] = DB_FILE

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
client = OpenAI(api_key=os.environ.get("OPEN_AI_KEY"))

SESSION_TIMEOUT_SECONDS: int = 60


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


# ------------------ OPENAI HELPERS ------------------


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


def process_openai_response(subscription_id: int, messages: List[Dict[str, Any]]) -> Any:
    """Process OpenAI response and handle tool calls if needed."""
    db = get_db()
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=messages,  # type: ignore
        tools=get_tools(),  # type: ignore
    )
    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls

    log.debug("Received response: %s", response_message.content)

    if tool_calls:
        log.info(
            "Tool calls requested: %s",
            [f"{tc.function.name}({tc.function.arguments})" for tc in tool_calls],
        )
        messages.append(response_message.model_dump())  # Convert to dict

        with app.app_context():
            tool_outputs = run_tools(db, subscription_id, tool_calls)

        for tool_output in tool_outputs:
            messages.append(tool_output)

        second_response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=messages,  # type: ignore
        )
        response_message = second_response.choices[0].message

    messages.append(response_message.model_dump())  # Convert to dict
    return response_message


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

        # Process OpenAI response and handle tool calls
        response_message = process_openai_response(subscription_id, messages)

        # Update session with new messages
        update_session_messages(session_id, messages)

        return jsonify({"response": response_message.content, "session_id": session_id})

    except Exception as e:
        log.error("Error in OpenAI integration: %s", e)
        return jsonify({"error": str(e)}), 500


# ------------------ MAIN ------------------

if __name__ == "__main__":
    with app.app_context():
        cleanup_expired_sessions()  # Clean up any expired sessions on startup
    app.run(host="0.0.0.0", port=5000)
