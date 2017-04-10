FROM ubuntu:zesty
ARG DEBIAN_FRONTEND=noninteractive
USER root

##
## The official Debian and Ubuntu images automatically run apt-get clean, so explicit invocation is not required.
##
RUN     apt-get -y update && \
        apt-get -y upgrade && \
        rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

##
## mysql including password/confirmation
##  
RUN apt-get update && \
    apt-get install -y debconf-utils && \
    echo mysql-server mysql-server/root_password password juniper123 | debconf-set-selections && \
    echo mysql-server mysql-server/root_password_again password juniper123 | debconf-set-selections && \
    apt-get install -y mysql-server -o pkg::Options::="--force-confdef" -o pkg::Options::="--force-confold" --fix-missing && \
    apt-get install -y net-tools --fix-missing && \
    rm -rf /var/lib/apt/lists/*



# dependencies
RUN apt-get -y update && \
    apt-get -y install git \
            adduser \  
            libfontconfig \ 
            wget \ 
            make \
            curl \
            pmacct \
            unzip \
            vim \
            supervisor \
            inetutils-ping \
            dnsutils \
            gettext \
	    rsyslog \
	    openssh-server \ 
	    tshark \ 
            tcpdump && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*


COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY init.sh /tmp
COPY mysqld.cnf /etc/mysql/mysql.conf.d/
COPY sshd_config /etc/ssh

RUN mkdir /data
COPY data /data
WORKDIR /data

CMD ["/usr/bin/supervisord"]
