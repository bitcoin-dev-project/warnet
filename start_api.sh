#!/bin/bash
# create a virtual environment
python -m venv .venv

# activate the virtual environment
source .venv/bin/activate

# install the requirements
pip install -r requirements.txt


# Start the first FastAPI service with automatic reload
uvicorn server-api.main:app --host 0.0.0.0 --port 8000 --reload &

# Store the process ID (PID) of the server-api uvicorn process
server_pid=$!

# Start the second FastAPI service with automatic reload
uvicorn client-api.main:app --host 0.0.0.0 --port 8001 --reload &

# Store the process ID (PID) of the client-api uvicorn process
client_pid=$!

# Function to check if a uvicorn process is running
is_running() {
	local pid=$1
	kill -0 $pid 2>/dev/null
	return $?
}

# Check if both uvicorn processes start successfully
if is_running $server_pid && is_running $client_pid; then
	echo "Server API is accessible at http://localhost:8000/docs"
	echo "Client API is accessible at http://localhost:8001/docs"
else
	echo "Failed to start one or both APIs."
fi

# Wait for both uvicorn processes to finish (e.g., when you press Ctrl+C)
wait $server_pid
wait $client_pid