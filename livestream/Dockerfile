FROM nginx:alpine

# Install required packages
RUN apk add --no-cache \
    bash \
    gettext \
    perl \
    jq \
    su-exec \
    && rm -rf /var/cache/apk/*

# Add user 'abdullah' (non-root)
RUN adduser -D -s /bin/bash abdullah && \
    addgroup abdullah abdullah

# Create required directories and set permissions
RUN mkdir -p /app/config /app/logs /mnt/Data/Syslog/nginx /etc/nginx/conf.d && \
    chown -R abdullah:abdullah /app /mnt/Data/Syslog/nginx /etc/nginx && \
    chmod -R 775 /app /mnt/Data/Syslog/nginx /etc/nginx && \
    chmod g+s /app /mnt/Data/Syslog/nginx

# Copy configuration files
COPY --chown=abdullah:abdullah config/nginx.conf.template /app/config/
COPY --chown=abdullah:abdullah config/rtsp.conf.template /app/config/
COPY entrypoint.sh /app/

# Set permissions
RUN chmod +x /app/entrypoint.sh && \
    chown abdullah:abdullah /app/entrypoint.sh

# Set working directory
WORKDIR /app

# Expose port
EXPOSE 8554

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]