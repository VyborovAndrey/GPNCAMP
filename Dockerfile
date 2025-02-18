# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3-slim

EXPOSE 9999

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1
# Install pip requirements
COPY requirements.txt .
RUN python -m  pip install -r requirements.txt
COPY . .
# Creates a non-root user with an explicit UID and adds permission to access the /app folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["/bin/sh", "-c", "PASSWORD=$(jq -r '.ssl.certificatePassword' /ssl/config.json) && \
    openssl pkcs12 -in /ssl/keystore.p12 -nokeys -out /ssl/fullchain.pem -passin pass:$PASSWORD && \
    openssl pkcs12 -in /ssl/keystore.p12 -nocerts -nodes -out /ssl/privkey.pem -passin pass:$PASSWORD && \
    gunicorn --bind 0.0.0.0:9999 --certfile=/ssl/fullchain.pem --keyfile=/ssl/privkey.pem DB:app"]