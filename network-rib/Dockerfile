FROM juniper/pyez:2.0.1

USER root

## To be removed once change merge upstream
RUN apk add --no-cache ca-certificates && \
    update-ca-certificates
RUN apk add --no-cache wget git bind-tools supervisor python py-pip build-base tcpdump nginx uwsgi uwsgi-python openssh
RUN pip install --upgrade pip

RUN pip install flask pytricia netaddr gunicorn statsd requests
RUN pip install netmiko
ENV APP_DIR /data

# app dir
RUN mkdir ${APP_DIR} \
    && chown -R nginx:nginx ${APP_DIR} \
    && chmod 777 /run/ -R \
    && chmod 777 /root/ -R

# expose web server port
# only http, for ssl use reverse proxy
EXPOSE 4000

ADD data /data/
WORKDIR ${APP_DIR}
COPY supervisord.conf /etc/supervisord.conf
ENTRYPOINT ["supervisord", "--nodaemon", "--configuration", "/etc/supervisord.conf"]

