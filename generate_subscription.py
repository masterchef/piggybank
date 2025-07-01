import sqlite3
import uuid
import argparse


def create_subscription(name: str):
    """
    Creates a new subscription and returns the auth token.
    """
    db = sqlite3.connect("pigbank.db")
    db.row_factory = sqlite3.Row
    auth_token = str(uuid.uuid4())
    try:
        db.execute(
            "INSERT INTO subscriptions (name, auth_token) VALUES (?, ?)",
            (name, auth_token),
        )
        db.commit()
        print(f"Subscription created for '{name}'.")
        print(f"Auth Token: {auth_token}")
    except sqlite3.IntegrityError:
        print("Error: Could not create subscription. Is the name unique?")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a new subscription.")
    parser.add_argument("name", type=str, help="The name for the new subscription.")
    args = parser.parse_args()
    create_subscription(args.name)
