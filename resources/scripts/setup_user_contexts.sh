#!/bin/bash

# Function to check if a command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Function to display usage information
usage() {
  echo "Usage: $0 <namespace> [kubeconfig_directory] [token_duration]"
  echo "  namespace: The Kubernetes namespace"
  echo "  kubeconfig_directory: Directory to store kubeconfig files (default: kubeconfigs)"
  echo "  token_duration: Duration of the token in seconds (default: 600 seconds / 10 minutes)"
  exit 1
}

# Check for required commands
if ! command_exists kubectl; then
  echo "kubectl is not installed. Please install it and try again."
  exit 1
fi

# Check if namespace argument is provided
if [ $# -eq 0 ]; then
  usage
fi

NAMESPACE=$1
KUBECONFIG_DIR=${2:-"kubeconfigs"}
TOKEN_DURATION=${3:-600}

CLUSTER_NAME=$(kubectl config view --minify -o jsonpath='{.clusters[0].name}')
CLUSTER_SERVER=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')
CLUSTER_CA=$(kubectl config view --minify --raw -o jsonpath='{.clusters[0].cluster.certificate-authority-data}')

# Create the directory to store the kubeconfig files
mkdir -p "$KUBECONFIG_DIR"

# Get all ServiceAccounts in the namespace
SERVICE_ACCOUNTS=$(kubectl get serviceaccounts -n $NAMESPACE -o jsonpath='{.items[*].metadata.name}')

for SA in $SERVICE_ACCOUNTS; do
  echo "Processing ServiceAccount: $SA"
  
  # Create a token for the ServiceAccount with specified duration
  TOKEN=$(kubectl create token $SA -n $NAMESPACE --duration="${TOKEN_DURATION}s")
  
  if [ -z "$TOKEN" ]; then
    echo "Failed to create token for ServiceAccount $SA. Skipping..."
    continue
  fi
  
  # Create a kubeconfig file for the user
  KUBECONFIG_FILE="$KUBECONFIG_DIR/${SA}-${NAMESPACE}-kubeconfig"
  
  cat << EOF > "$KUBECONFIG_FILE"
apiVersion: v1
kind: Config
clusters:
- name: ${CLUSTER_NAME}
  cluster:
    server: ${CLUSTER_SERVER}
    certificate-authority-data: ${CLUSTER_CA}
users:
- name: ${SA}
  user:
    token: ${TOKEN}
contexts:
- name: ${SA}-${NAMESPACE}
  context:
    cluster: ${CLUSTER_NAME}
    namespace: ${NAMESPACE}
    user: ${SA}
current-context: ${SA}-${NAMESPACE}
EOF

  echo "Created kubeconfig file for $SA: $KUBECONFIG_FILE"
  echo "Token duration: ${TOKEN_DURATION} seconds"
  echo "To use this config, run: kubectl --kubeconfig=$KUBECONFIG_FILE get pods"
  echo "---"
done

echo "All kubeconfig files have been created in the '$KUBECONFIG_DIR' directory."
echo "Distribute these files to the respective users."
echo "Users can then use them with kubectl by specifying the --kubeconfig flag or by setting the KUBECONFIG environment variable."
echo "Note: The tokens will expire after ${TOKEN_DURATION} seconds."
