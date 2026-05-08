set -a && source .env && set +a
sshpass -p '$SERV1_PASS' ssh $SERV1_USER@$SERV1_IP 'bash -s' < install_everything.sh