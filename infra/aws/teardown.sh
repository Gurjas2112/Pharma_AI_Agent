#!/usr/bin/env bash
# Stop (default) or terminate the Ollama host to control GPU spend.
set -euo pipefail
EP=(); [[ -n "${AWS_ENDPOINT_URL:-}" ]] && EP=(--endpoint-url "$AWS_ENDPOINT_URL")
AWS=(aws "${EP[@]}" --region "${AWS_DEFAULT_REGION:-ap-south-1}" --output text)
IDS=$("${AWS[@]}" ec2 describe-instances --filters Name=tag:Name,Values=repurpora-ollama \
      Name=instance-state-name,Values=running,stopped --query 'Reservations[].Instances[].InstanceId')
[[ -z "$IDS" ]] && { echo "no instances"; exit 0; }
if [[ "${1:-stop}" == "terminate" ]]; then "${AWS[@]}" ec2 terminate-instances --instance-ids $IDS
else "${AWS[@]}" ec2 stop-instances --instance-ids $IDS; fi
