FROM ubuntu:zesty

USER root

RUN     apt-get -y update && \
        apt-get -y upgrade && \
        apt-get clean   &&\
        rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# dependencies
RUN     apt-get -y update && \
        apt-get -y install \
        git adduser libfontconfig wget make curl tcpdump pmacct unzip vim supervisor inetutils-ping dnsutils gettext tcpdump && \
        apt-get clean   &&\
        rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

RUN mkdir /data
ADD data /data
WORKDIR /data

CMD ["/usr/bin/supervisord"]
