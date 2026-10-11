#!/bin/bash
# Build the image on gg-app, load it into K3s, migrate the database, roll out the app.
# Run from the repo root on your Mac:  ./scripts/deploy.sh
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/devenmundada/GatewayGuard.git}"
BRANCH="${BRANCH:-main}"

echo "1/6 Making sure the JWT secret exists in the cluster..."
if ! kubectl get secret gatewayguard-secrets -o jsonpath='{.data.JWT_SECRET}' 2>/dev/null | grep -q .; then
  kubectl patch secret gatewayguard-secrets --type merge \
    -p "{\"stringData\":{\"JWT_SECRET\":\"$(openssl rand -base64 48 | tr -d '\n')\"}}"
  echo "    generated a new random JWT_SECRET (existing logins are invalidated once)"
else
  echo "    already set"
fi

echo "2/6 Building the image on gg-app from $BRANCH..."
multipass exec gg-app -- bash -c "
  set -e
  rm -rf ~/gg-build && git clone --depth 1 --branch $BRANCH $REPO_URL ~/gg-build
  cd ~/gg-build && sudo docker build -f Dockerfile.prod -t gatewayguard:latest .
"

echo "3/6 Loading the image into K3s (K3s does not share Docker's image store)..."
multipass exec gg-app -- bash -c "sudo docker save gatewayguard:latest | sudo k3s ctr images import -"

echo "4/6 Migrating the database..."
kubectl delete job gatewayguard-migrate --ignore-not-found
kubectl apply -f kubernetes/migrate-job.yaml
kubectl wait --for=condition=complete job/gatewayguard-migrate --timeout=180s \
  || { kubectl logs job/gatewayguard-migrate; exit 1; }

echo "5/6 Rolling out the app and monitoring..."
kubectl apply -f kubernetes/monitoring/prometheus-pvc.yaml
kubectl apply -f kubernetes/monitoring/prometheus-config.yaml
kubectl apply -f kubernetes/monitoring/prometheus-deployment.yaml
kubectl apply -f kubernetes/gatewayguard-service.yaml
kubectl apply -f kubernetes/gatewayguard-deployment.yaml
kubectl rollout restart deployment/gatewayguard
kubectl rollout status deployment/gatewayguard --timeout=180s

echo "6/6 Checking..."
curl -s --max-time 10 http://192.168.252.2:30080/health; echo
