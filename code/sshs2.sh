set -a ; source ./.env ; set +a 
echo "$SERV2_LOGIN"@"$SERV2_IP" && sshpass -p "$SERV2_PASS" ssh -X "$SERV2_LOGIN"@"$SERV2_IP" 