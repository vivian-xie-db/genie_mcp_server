# Genie MCP Server

This project provides an async server for interacting with Databricks Genie via a MCP StreamableHTTP Protocol. It enables users to query Genie and receive answers or data, leveraging Databricks authentication and robust error handling.

## Features

- Async API server using Starlette and Uvicorn
- Integration with Databricks Genie for conversational queries
- Automatic OAuth token management for Databricks


## Project Structure

- `mcp_server.py`: Main server entry point, exposes the tool via MCP StreamableHTTP Protocol.
- `genie_room.py`: Handles Genie API interactions and conversation logic.
- `token_minter.py`: Manages Databricks OAuth token minting and refreshing.
- `requirements.txt`: Python dependencies.
- `app.yaml`: Example deployment configuration.


## Deploying to Databricks Apps

You can deploy the Genie MCP Server as a Databricks app by following these steps:

1. **Clone the Repository to Your Workspace**

   In your Databricks workspace, navigate to the directory where you want to deploy the app (e.g., `/Workspace/Users/your.email@databricks.com/genie_mcp_server`). Then, clone the repository:

   ```bash
   git clone https://github.com/your-org/genie_mcp_server.git
   ```

2. **Configure the Genie Space ID and Other Environment Variables**

   Open the `app.yaml` file in the root of the cloned repository. Update the `SPACE_ID` value to match your Genie space. 

   Example `app.yaml`:

   ```yaml
   command:
   - "python"
   - "mcp_server.py"

   env:
   - name: "SPACE_ID"
     value: "your_space_id"
   ```

3. **Create and Deploy the App in Databricks**

   - Go to the Databricks Apps interface.
   - Create a new app and specify the path to the directory where you cloned the repository.
   - Complete the app creation and deployment process.
   ```databricks apps deploy genie-mcp-server --source-code-path /Workspace/Users/your.email@databricks.com/genie_mcp_server```

4. **Access the API**

   Once deployed, your Genie MCP Server app will be running and accessible via the configured port and endpoint (e.g., `https://app-url.aws.databricksapps.com/api/mcp/`). You can now send MCP requests to your deployed app from within your Databricks workspace or from external clients, depending on your network configuration.

