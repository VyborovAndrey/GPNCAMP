# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3-slim

EXPOSE 9998

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
CMD ["/bin/bash", "-c", "python bot.py"]