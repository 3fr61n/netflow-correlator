FROM juniper/pyez:2.0.1

USER root

## To be removed once change merge upstream
RUN apk add --no-cache ca-certificates && \
    update-ca-certificates
RUN apk add --no-cache wget git bind-tools supervisor python py-pip build-base tcpdump nginx uwsgi uwsgi-python 
RUN pip install --upgrade pip

RUN pip install flask pytricia netaddr
RUN pip install netmiko
ENV APP_DIR /data

# app dir
RUN mkdir ${APP_DIR} \
    && chown -R nginx:nginx ${APP_DIR} \
    && chmod 777 /run/ -R \
    && chmod 777 /root/ -R

# expose web server port
# only http, for ssl use reverse proxy
EXPOSE 5000

ADD data /data/
WORKDIR ${APP_DIR}
COPY supervisord.conf /etc/supervisord.conf
ENTRYPOINT ["supervisord", "--nodaemon", "--configuration", "/etc/supervisord.conf"]




#FROM pypy:2-5.7.0
#
#USER root
#
#RUN     apt-get -y update && \
#        apt-get -y upgrade && \
#        apt-get clean   &&\
#        rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
#
## dependencies
#RUN     apt-get -y update && \
#        apt-get -y install \
#        git wget curl tcpdump unzip vim supervisor inetutils-ping dnsutils gettext && \
#        apt-get clean   &&\
#        rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
#
#ARG KAFKA_PYTHON_VERSION=1.3.2
#
##################################################
#### Install kafka, falcon, and dependencies   ###
##################################################
#
#RUN     pip install "kafka-python==$KAFKA_PYTHON_VERSION" gunicorn uwsgi pytricia statsd
#
##################################################
#### Install falcon via cpython                ###
##################################################
#
#RUN    pip install cython
#RUN    pip install --no-binary :all: falcon
#
##################################################
#### Install wrt for rest api benchmark        ###
##################################################
#
#RUN apt-get -y update && \
#    apt-get install build-essential libssl-dev git -y && \
#   git clone https://github.com/wg/wrk.git && \
#   cd wrk && \
#   make && \
#   cp wrk /usr/local/bin
#
#COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
#
#ADD data /data/
#WORKDIR /data
#COPY supervisord.conf /etc/supervisord.conf
#ENTRYPOINT ["supervisord", "--nodaemon", "--configuration", "/etc/supervisord.conf"]
