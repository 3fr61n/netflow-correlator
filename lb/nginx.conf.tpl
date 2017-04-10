user root;
worker_processes auto;

events {
    worker_connections  1024;
}

{{ $ports := split $.Env.SERVICES_LB "," }}

{{ range $port := $ports }}
{{ range $service, $containers := groupByMulti $ "Env.SERVICES_CLIENT" "," }}
{{ if eq $port $service }}
# Load balance UDP-based traffic across two servers
stream {
    upstream udp_{{$port}} {
                #hash $remote_addr consistent;
      {{ range $container := $containers }}
        {{ range $address := $container.Addresses }}
                {{ if eq $address.Port $port }}
                # {{$container.Name}}
                server {{$container.Name}}:{{ $address.Port }};
                {{ end }}
        {{ end }}
      {{ end }}
    }

    server {
        listen {{$port}} udp;
        proxy_pass udp_{{$port}};
        proxy_timeout 1s;
        proxy_bind $remote_addr transparent;
        proxy_responses 0;
        error_log lb_error.log debug;
    }
}
{{ end }}
{{ end }}
{{ end }}
