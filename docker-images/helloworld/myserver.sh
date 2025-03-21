#!/bin/sh
DATE=$(date)
HOSTNAME=$(hostname|cut -c 1-40)
MSG=$(printf "Hello World!\nThis message shows that your installation appears to be working correctly.\nDate: $DATE\nHostname: %-40s" $HOSTNAME)
LEN=$(echo "$MSG" | wc -c)
printf "HTTP/1.1 200 OK\nContent-Length: %d\nConnection: close\n\n$MSG\n" $LEN
