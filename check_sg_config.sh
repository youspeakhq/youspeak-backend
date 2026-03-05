#!/bin/bash
# Check security group configuration for curriculum service

echo "======================================================================"
echo "Security Group Analysis for Curriculum Service"
echo "======================================================================"
echo ""

# Get curriculum service task
TASK_ARN=$(aws ecs list-tasks --cluster youspeak-cluster --service-name youspeak-curriculum-service-staging --region us-east-1 --query 'taskArns[0]' --output text)

# Get task ENI
ENI_ID=$(aws ecs describe-tasks --cluster youspeak-cluster --tasks $TASK_ARN --region us-east-1 --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text)

# Get task security group
echo "[1/4] Curriculum Service Security Group:"
TASK_SG=$(aws ec2 describe-network-interfaces --network-interface-ids $ENI_ID --region us-east-1 --query 'NetworkInterfaces[0].Groups[0].GroupId' --output text)
echo "   Security Group ID: $TASK_SG"

# Show inbound rules
echo ""
echo "   Inbound Rules:"
aws ec2 describe-security-groups --group-ids $TASK_SG --region us-east-1 --query 'SecurityGroups[0].IpPermissions[].[FromPort,ToPort,IpProtocol,UserIdGroupPairs[0].GroupId // CidrIp]' --output table

# Get load balancer security group
echo ""
echo "[2/4] Load Balancer Security Group:"
LB_SG=$(aws elbv2 describe-load-balancers --names internal-youspeak-curric-int-stg --region us-east-1 --query 'LoadBalancers[0].SecurityGroups[0]' --output text)
echo "   Security Group ID: $LB_SG"

echo ""
echo "   Outbound Rules:"
aws ec2 describe-security-groups --group-ids $LB_SG --region us-east-1 --query 'SecurityGroups[0].IpPermissions[].[FromPort,ToPort,IpProtocol,UserIdGroupPairs[0].GroupId // CidrIp]' --output table

# Check if rule exists
echo ""
echo "[3/4] Checking Connectivity:"
RULE_EXISTS=$(aws ec2 describe-security-groups --group-ids $TASK_SG --region us-east-1 --query "SecurityGroups[0].IpPermissions[?FromPort==\`8001\` && ToPort==\`8001\`].UserIdGroupPairs[?GroupId==\`$LB_SG\`]" --output text)

if [ -z "$RULE_EXISTS" ]; then
    echo "   ❌ MISSING: Inbound rule for port 8001 from LB security group"
    echo "   This is the root cause!"
else
    echo "   ✅ Rule exists: Port 8001 from $LB_SG"
fi

echo ""
echo "[4/4] Target Group Health Check:"
aws elbv2 describe-target-groups --target-group-arns arn:aws:elasticloadbalancing:us-east-1:497068062563:targetgroup/youspeak-curric-tg-stg/fb119ff5cf07df94 --region us-east-1 --query 'TargetGroups[0].{Path:HealthCheckPath,Port:HealthCheckPort,Protocol:HealthCheckProtocol,Timeout:HealthCheckTimeoutSeconds,Interval:HealthCheckIntervalSeconds}' --output json | jq '.'

echo ""
echo "======================================================================"
