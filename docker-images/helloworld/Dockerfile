FROM alpine:latest

COPY ./myserver.sh /root/myserver.sh

EXPOSE 80/tcp

ENTRYPOINT ["nc", "-l", "-p", "80", "-lk", "-e", "/root/myserver.sh"]
