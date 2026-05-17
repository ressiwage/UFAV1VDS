set -a && source .env && set +a
# sync s3
sshpass -p "$SERV1_PASS" ssh "$SERV1_LOGIN"@"$SERV1_IP" \
  'cd ~/HSE-DIPLOMA-6/code && make delete-unused'


# sync s3
sshpass -p "$SERV2_PASS" ssh "$SERV2_LOGIN"@"$SERV2_IP" \
  'cd ~/HSE-DIPLOMA-6/code && make delete-unused'

