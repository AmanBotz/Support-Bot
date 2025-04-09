FROM python:3.9-slim

# Prevent Python from writing .pyc files and enable stdout logging.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory.
WORKDIR /app

# Copy dependency definitions.
COPY requirements.txt .

# Install Python dependencies.
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy the project files into the container.
COPY . .

# Expose port 8000 for the Flask health check.
EXPOSE 8000

# Run both the Flask server (server.py) and the Telegram bot (main.py) concurrently.
CMD ["sh", "-c", "python server.py & python main.py"]
