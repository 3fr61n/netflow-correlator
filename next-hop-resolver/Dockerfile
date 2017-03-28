FROM juniper/pyez:2.0.1

USER root

## To be removed once change merge upstream
RUN apk add --no-cache ca-certificates && \
    update-ca-certificates
RUN apk add --no-cache wget git bind-tools supervisor python py-pip build-base tcpdump openssh
RUN pip install --upgrade pip

ARG TELEGRAF_VERSION=1.2.1
ARG KAFKA_PYTHON_VERSION=1.3.2

#############################
## Install Telegraf
#############################
RUN wget -q https://dl.influxdata.com/telegraf/releases/telegraf-${TELEGRAF_VERSION}-static_linux_amd64.tar.gz && \
    mkdir -p /usr/src /etc/telegraf && \
    tar -C /usr/src -xzf telegraf-${TELEGRAF_VERSION}-static_linux_amd64.tar.gz && \
    mv /usr/src/telegraf*/telegraf.conf /etc/telegraf/ && \
    chmod +x /usr/src/telegraf*/* && \
    cp -a /usr/src/telegraf*/* /usr/bin/ && \
    rm -rf *.tar.gz* /usr/src /root/.gnupg

########################
### Install kafka    ###
########################

RUN     pip install "kafka-python==$KAFKA_PYTHON_VERSION"

##############################
### Install Pytricia FLASK
##############################

RUN     pip install pytricia flask requests
RUN     pip install pexpect
RUN     pip install netmiko
#RUN mkdir -p /opt && \
#    cd /opt && \
#    git clone https://github.com/jsommers/pytricia.git && \
#    cd pytricia && \
#    python setup.py build && \
#    python setup.py install


ADD data /data/
WORKDIR /data
COPY supervisord.conf /etc/supervisord.conf
ENTRYPOINT ["supervisord", "--nodaemon", "--configuration", "/etc/supervisord.conf"]


