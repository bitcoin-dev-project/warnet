FROM alpine:latest

RUN apk add openssh

RUN echo "root:" | chpasswd

RUN ssh-keygen -A

CMD ["/usr/sbin/sshd", "-D", \
  "-o", "PasswordAuthentication=yes", \
  "-o", "PermitEmptyPasswords=yes", \
  "-o", "PermitRootLogin=yes"]