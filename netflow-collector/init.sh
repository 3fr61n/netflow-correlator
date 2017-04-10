#!/bin/bash

MYSQL="mysql -u root -p$MYSQL_PASSWORD"

# start services
service mysql start
service ssh start
service rsyslog start


## permissions for remote connection
$MYSQL << EOF
    create user "$MYSQL_USER"@'%' IDENTIFIED BY "$MYSQL_USER_PASSWORD";
    GRANT ALL PRIVILEGES ON *.* TO "$MYSQL_USER"@'%' WITH GRANT OPTION;
    FLUSH PRIVILEGES;
EOF

## create initial database and bgp table
$MYSQL < /data/sql/pmacct-create-db_bgp_v1.mysql
$MYSQL < /data/sql/pmacct-grant-db.mysql

## root permission to ssh to this container
echo "PermitRootLogin yes" >> /etc/ssh/sshd_config

bash /data/start-input-netflow.sh
echo "root:$ROOT_PASSWORD" | chpasswd

