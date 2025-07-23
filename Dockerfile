FROM python:3.12-slim

WORKDIR /app

# Installe Python + isc-dhcp-server
RUN apt-get update && \
    apt-get install -y isc-dhcp-server iproute2 procps iputils-ping net-tools tcpdump vim nano gcc python3-dev && \
    pip install --no-cache-dir flask flask_sqlalchemy flask_socketio paramiko ping3 netifaces

COPY . .

EXPOSE 5050 67/udp

CMD ["python", "app.py"]
