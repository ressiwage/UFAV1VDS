set -a ; source ./.env ; set +a 
echo "$SERV1_LOGIN"@"$SERV1_IP" && sshpass -p "$SERV1_PASS" ssh -X "$SERV1_LOGIN"@"$SERV1_IP" 