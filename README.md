# Piggy Bank AI Assistant API

An AI-powered Flask-based API for managing personal accounts and transactions using OpenAI's GPT model with function calling capabilities.

## Features

- **AI-Powered Interface**: Natural language interaction with your piggy bank
- **Session Management**: Maintains conversation context with automatic session cleanup
- **Multi-tenant Support**: Subscription-based access with secure token authentication
- **Account Management**: Create and manage multiple accounts per subscription
- **Transaction Operations**: Add money, withdraw money, and transfer between accounts
- **Transaction History**: View detailed transaction records
- **Account Name Normalization**: Automatic name standardization (e.g., "victor" → "viktor")
- **Parallel Tool Execution**: AI can execute multiple operations simultaneously

## Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   ```

2. Activate the virtual environment:
   ```bash
   # On Linux/Mac:
   source venv/bin/activate
   
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   Create a `.env` file in the project root with your OpenAI API key:
   ```
   OPEN_AI_KEY=your_openai_api_key_here
   ```

5. Run the application:
   ```bash
   python main.py
   ```

The API will be available at `http://localhost:5000`

## Generating a Subscription

To use the API, you first need a subscription token. You can generate one by running the `generate_subscription.py` script:

```bash
python generate_subscription.py "Your Name"
```

This will create a new subscription and output an authentication token. Use this token as a Bearer token in your API requests.

## API Endpoints

The application provides an AI-powered conversational interface instead of traditional REST endpoints. All requests require authentication using a Bearer token.

### Authentication
Add `Authorization` header to your requests.
```
Authorization: Bearer <your_subscription_token>
```

### SIRI Integration

1. Save this shortcut to your device https://www.icloud.com/shortcuts/070d9eef36134caa8f70fa988407f142
2. Edit the shortcut to add your authentication token in the "Get contents of" step:
   - Click `Show More`
   - Edit the Value of Header `Authorization`, it should say 'Bearer <your token>`
   - Replace `<your token>` with your token so it looks like: `Bearer my_token_232j23hk23j4h2`
3. Click play to test the shortcut.


### Main Endpoint

#### POST `/agent`
The primary endpoint for interacting with the AI assistant.

**Request Body:**
```json
{
  "query": "Your natural language request",
  "session_id": "optional_session_id_for_conversation_continuity"
}
```

**Response:**
```json
{
  "response": "AI assistant's response",
  "session_id": "session_id_for_future_requests"
}
```

**Example Requests:**
- `"Create an account called 'savings'"`
- `"Add $100 to my savings account for salary"`
- `"Transfer $50 from savings to checking for bills"`
- `"What's my current balance in all accounts?"`
- `"Show me recent transactions for my checking account"`

### Available Operations

The AI assistant can perform the following operations through natural language:

#### Account Management
- **Create Account**: "Create a new account named [name]"
- **List Accounts**: "Show me all my accounts" or "What accounts do I have?"
- **Get Balance**: "What's my balance in [account]?" or "How much money is in [account]?"

#### Transactions
- **Add Money**: "Add $[amount] to [account] for [reason]"
- **Withdraw Money**: "Withdraw $[amount] from [account] for [reason]"
- **Transfer Money**: "Transfer $[amount] from [account1] to [account2] for [reason]"
- **Transaction History**: "Show me transactions for [account]" or "What are my recent transactions?"

### Session Management

- Sessions automatically expire after 60 seconds of inactivity
- Include the `session_id` from previous responses to maintain conversation context
- The AI can remember previous context within the same session
- Sessions are automatically cleaned up on server startup and during operation

## Database

The application uses SQLite with the following tables:

### Core Tables
- **`subscriptions`** - Store subscription information and authentication tokens
  - `id` (Primary Key)
  - `family_name` - Name of the subscription holder
  - `auth_token` - Unique authentication token

- **`accounts`** - Store account information per subscription
  - `id` (Primary Key)
  - `name` - Account name (normalized)
  - `subscription_id` - Foreign key to subscriptions table
  - Unique constraint on (name, subscription_id)

- **`transactions`** - Store all financial transactions
  - `id` (Primary Key)
  - `account_id` - Foreign key to accounts table
  - `amount` - Transaction amount (positive for deposits, negative for withdrawals)
  - `reason` - Description/reason for the transaction
  - `timestamp` - When the transaction occurred

### Session Management
- **`sessions`** - Store AI conversation sessions
  - `id` - Unique session identifier (UUID)
  - `subscription_id` - Foreign key to subscriptions table
  - `messages` - JSON-encoded conversation history
  - `last_access` - Last activity timestamp for session cleanup
  - `created_at` - Session creation timestamp

The database file (`pigbank.db`) is created automatically when the application starts.

## Technical Details

### AI Integration
- Uses OpenAI's GPT-4 Turbo model for natural language processing
- Implements function calling to execute financial operations
- Supports parallel tool execution for complex multi-step requests
- Maintains conversation context through session management

### Authentication & Authorization
- Subscription-based multi-tenant architecture
- Bearer token authentication for all requests
- Automatic token validation before processing requests

### Error Handling
- Comprehensive error handling with appropriate HTTP status codes
- Database transaction rollback on errors
- Detailed logging for debugging and monitoring

## Example Usage

Here are some example interactions with the AI assistant:

### Creating and Managing Accounts
```bash
curl -X POST http://localhost:5000/agent \
  -H "Authorization: Bearer your_token_here" \
  -H "Content-Type: application/json" \
  -d '{"query": "Create a savings account for me"}'
```

### Adding Money
```bash
curl -X POST http://localhost:5000/agent \
  -H "Authorization: Bearer your_token_here" \
  -H "Content-Type: application/json" \
  -d '{"query": "Add $500 to my savings account for monthly salary"}'
```

### Complex Operations
```bash
curl -X POST http://localhost:5000/agent \
  -H "Authorization: Bearer your_token_here" \
  -H "Content-Type: application/json" \
  -d '{"query": "Create a checking account, transfer $100 from savings to checking, and show me all account balances"}'
```

### Conversation with Session
```bash
# First request
curl -X POST http://localhost:5000/agent \
  -H "Authorization: Bearer your_token_here" \
  -H "Content-Type: application/json" \
  -d '{"query": "What accounts do I have?"}'

# Follow-up request using session_id from previous response
curl -X POST http://localhost:5000/agent \
  -H "Authorization: Bearer your_token_here" \
  -H "Content-Type: application/json" \
  -d '{"query": "Add $50 to the first account", "session_id": "session_id_from_previous_response"}'
```

## Development

### Running Tests
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest test/ -v
```

### Code Quality
```bash
# Format code
black . --line-length 88

# Lint code
flake8 .

# Type checking
mypy .
```

### Using VS Code Tasks
The project includes pre-configured VS Code tasks:
- Install Dependencies
- Install Dev Dependencies
- Run Flask App
- Run Tests
- Format Code
- Lint Code
- Type Check

## Running on a Raspberry Pi at Startup

To run this application automatically on a Raspberry Pi at startup, you can use the provided `systemd` service file.

1.  **Make the `run.sh` script executable:**

    ```bash
    chmod +x run.sh
    ```

2.  **Move the `systemd` service file:**

    ```bash
    sudo mv piggybank.service /etc/systemd/system/
    ```

3.  **Enable and start the service:**

    ```bash
    sudo systemctl enable piggybank.service
    sudo systemctl start piggybank.service
    ```

4.  **Check the service status:**

    ```bash
    sudo systemctl status piggybank.service
    ```

## Dependencies

### Core Dependencies
- **Flask** - Web framework
- **openai** - OpenAI API client for AI functionality
- **python-dotenv** - Environment variable management

### Development Dependencies
See `requirements-dev.txt` for testing and development tools.

## License

This project is licensed under the terms specified in the LICENSE file.
