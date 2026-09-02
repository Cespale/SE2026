FROM nginx:1.27-alpine

COPY gateway/nginx.conf /etc/nginx/nginx.base.conf
COPY gateway/streamhub-entrypoint.sh /streamhub-entrypoint.sh
RUN chmod 0555 /streamhub-entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/streamhub-entrypoint.sh"]
