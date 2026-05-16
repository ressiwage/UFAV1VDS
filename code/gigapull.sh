set -a && source .env && set +a
# sync s3
sshpass -p "$SERV1_PASS" ssh "$SERV1_LOGIN"@"$SERV1_IP" \
  'docker secret create env -' < .env

sshpass -p "$SERV1_PASS" ssh "$SERV1_LOGIN"@"$SERV1_IP" 'bash -s' < ghcr_pull.sh

# sync s3
sshpass -p "$SERV2_PASS" ssh "$SERV2_LOGIN"@"$SERV2_IP" \
  'docker secret create env -' < .env

sshpass -p "$SERV2_PASS" ssh "$SERV2_LOGIN"@"$SERV2_IP" 'bash -s' < ghcr_pull.sh