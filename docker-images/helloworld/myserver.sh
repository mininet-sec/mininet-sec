#!/bin/sh
DATE=$(date)
HOSTNAME=$(hostname|cut -c 1-30)
MSG=$(printf "Hello World!\nThis message shows that your installation appears to be working correctly.\nDate: $DATE\nHostname: %-30s\n" $HOSTNAME)
LEN=$(echo "$MSG" | wc -c)
printf "HTTP/1.1 200 OK\nContent-Length: %d\nConnection: close\n\n$MSG" $LEN
