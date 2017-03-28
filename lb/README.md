# nginx-udp
NGINX Load Balancer packaged with docker-gen for docker-compose

The configuration is generated dynamically on the fly and is based on environment variables both on LB and Server side

On NGINX, you need to define the variable : SERVICES_LB
On Servers, you need to define the variable : SERVICES_CLIENT

Both can be single value or list of value separated with `,`

# Here is an example of docker-compose file

```yaml
lb:
  image: dgarros/nginx-confd
  links:
   - opennti-input-syslog
  volumes:
   - /var/run/docker.sock:/tmp/docker.sock:ro
   - $PWD/nginx.conf.tpl:/etc/nginx/nginx.conf.tpl:ro
  environment:
   - "SERVICES_LB=6000"
  ports:
   - "6000:6000/udp"

opennti-input-syslog:
  image: juniper/open-nti-input-syslog
  environment:
   - "OUTPUT_INFLUXDB=false"
   - "OUTPUT_STDOUT=true"
   - "SERVICES_CLIENT=6000"
  expose:
   - "6000/udp"
  volumes:
   - /etc/localtime:/etc/localtime
```
