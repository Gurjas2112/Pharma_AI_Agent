#!/usr/bin/env bash
# Provision the Ollama GPU host on EC2. Works against LocalStack (prototype IaC
# validation) or real AWS (production) - controlled by AWS_ENDPOINT_URL.
#   ./ec2_ollama.sh            # create
#   ./ec2_ollama.sh --dry-run  # real AWS: permission check only (DryRun)
set -euo pipefail
cd "$(dirname "$0")"
REGION="${AWS_DEFAULT_REGION:-ap-south-1}"
TYPE="${INSTANCE_TYPE:-g4dn.xlarge}"
NAME="repurpora-ollama"
EP=()
[[ -n "${AWS_ENDPOINT_URL:-}" ]] && EP=(--endpoint-url "$AWS_ENDPOINT_URL")
AWS=(aws "${EP[@]}" --region "$REGION" --output text)
DRY=()
[[ "${1:-}" == "--dry-run" && -z "${AWS_ENDPOINT_URL:-}" ]] && DRY=(--dry-run)
TOKEN="${OLLAMA_PROXY_TOKEN:?set OLLAMA_PROXY_TOKEN}"

# Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 22.04) - resolved via SSM on real AWS
if [[ -n "${AWS_ENDPOINT_URL:-}" ]]; then
  AMI="ami-0123456789abcdef0"   # LocalStack accepts any AMI id
else
  AMI=$("${AWS[@]}" ssm get-parameter --name \
    /aws/service/deeplearning/ami/x86_64/base-oss-nvidia-driver-gpu-ubuntu-22.04/latest/ami-id \
    --query Parameter.Value)
fi

VPC=$("${AWS[@]}" ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId')
SG=$("${AWS[@]}" ec2 describe-security-groups --filters Name=group-name,Values=$NAME-sg \
      --query 'SecurityGroups[0].GroupId' 2>/dev/null || true)
if [[ -z "$SG" || "$SG" == "None" ]]; then
  SG=$("${AWS[@]}" ec2 create-security-group --group-name $NAME-sg --vpc-id "$VPC" \
        --description "Repurpora Ollama proxy (443 only)" --query GroupId)
  "${AWS[@]}" ec2 authorize-security-group-ingress --group-id "$SG" --protocol tcp --port 443 --cidr 0.0.0.0/0 >/dev/null
  "${AWS[@]}" ec2 authorize-security-group-ingress --group-id "$SG" --protocol tcp --port 80 --cidr 0.0.0.0/0 >/dev/null
fi

UD=$(sed "s/__OLLAMA_PROXY_TOKEN__/$TOKEN/" user_data.sh)
IID=$("${AWS[@]}" ec2 run-instances "${DRY[@]}" --image-id "$AMI" --instance-type "$TYPE" \
  --security-group-ids "$SG" --user-data "$UD" \
  --metadata-options HttpTokens=required,HttpEndpoint=enabled \
  --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=80,VolumeType=gp3,Encrypted=true}' \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME},{Key=project,Value=repurpora}]" \
  --query 'Instances[0].InstanceId')
EIP=$("${AWS[@]}" ec2 allocate-address --domain vpc --query AllocationId)
"${AWS[@]}" ec2 associate-address --instance-id "$IID" --allocation-id "$EIP" >/dev/null || true
IP=$("${AWS[@]}" ec2 describe-addresses --allocation-ids "$EIP" --query 'Addresses[0].PublicIp')
echo "instance=$IID sg=$SG eip=$IP"
echo "OLLAMA_BASE_URL=https://${IP//./-}.sslip.io  (after user-data finishes, ~10 min)"
