set -a && source .env && set +a

sshpass -p "$SERV1_PASS" ssh "$SERV1_LOGIN"@"$SERV1_IP" 'bash -s' < ghcr_pull.sh

sshpass -p "$SERV2_PASS" ssh "$SERV2_LOGIN"@"$SERV2_IP" 'bash -s' < ghcr_pull.sh