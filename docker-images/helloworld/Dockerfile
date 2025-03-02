FROM alpine:latest

COPY ./myserver.sh /root/myserver.sh

ENTRYPOINT ["nc", "-l", "-p", "80", "-lk", "-e", "/root/myserver.sh"]
