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

# Expose port 8000 for the Flask health check (if needed).
EXPOSE 8000

# Use CMD to run the bot.
CMD ["python", "main.py"]
