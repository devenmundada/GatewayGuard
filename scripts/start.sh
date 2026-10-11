#!/bin/bash
# Bring the GatewayGuard cluster back after a break. Safe to re-run.

echo "1/6 Starting VMs..."
multipass start gg-app gg-db gg-cache

echo "2/6 Syncing clocks..."
for vm in gg-app gg-db gg-cache; do
  echo "    $vm: $(multipass exec $vm -- sudo chronyc makestep)"
done

echo "3/6 Opening firewall ports..."
echo "    gg-app 30080"; multipass exec gg-app -- sudo ufw allow 30080
echo "    gg-db 30030";  multipass exec gg-db -- sudo ufw allow 30030
echo "    gg-db 30090";  multipass exec gg-db -- sudo ufw allow 30090
echo "    gg-db 30093";  multipass exec gg-db -- sudo ufw allow 30093
# Pod-to-pod traffic between nodes (Flannel VXLAN) and the kubelet. Without these,
# pods on gg-db / gg-cache cannot reach CoreDNS on gg-app.
for vm in gg-db gg-cache; do
  echo "    $vm 8472/udp + 10250"
  multipass exec $vm -- sudo ufw allow 8472/udp
  multipass exec $vm -- sudo ufw allow 10250/tcp
done

echo "4/6 Checking the GatewayGuard image in K3s..."
if multipass exec gg-app -- sudo k3s ctr images ls | grep -q "gatewayguard:latest"; then
  echo "    image present"
else
  echo "    image missing, re-importing from Docker..."
  multipass exec gg-app -- bash -c "sudo docker save gatewayguard:latest | sudo k3s ctr images import -"
  kubectl delete pod -l app=gatewayguard
fi

echo "5/6 Disk usage (warn above 80%)..."
for vm in gg-app gg-db gg-cache; do
  use=$(multipass exec $vm -- df / --output=pcent | tail -1 | tr -dc '0-9')
  if [ "$use" -gt 80 ]; then echo "    WARNING: $vm is ${use}% full"; else echo "    $vm ${use}%"; fi
done

echo "6/6 Waiting for pods, then health check..."
kubectl wait --for=condition=ready pod --all --timeout=180s
curl -s --max-time 10 http://192.168.252.2:30080/health/ready; echo
echo "Grafana:    http://192.168.252.3:30030"
echo "Prometheus: http://192.168.252.3:30090"
