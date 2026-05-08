set -a ; source ./.env ; set +a 
echo "$SERV1_LOGIN"@"$SERV1_IP" && sshpass -p "$SERV1_PASS" ssh "$SERV1_LOGIN"@"$SERV1_IP" 