# Use a lightweight Python base image to keep the image under 300MB
FROM python:3.12-slim

# Set working directory inside the container
WORKDIR /app

# Create a non-root user and group for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy requirements first to leverage Docker layer caching
COPY app/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY app/main.py .

# Create logs directory and assign ownership to non-root user
RUN mkdir -p /app/logs && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Document the port the app listens on
EXPOSE 3000

# Default environment variables — overridden by Docker Compose at runtime
ENV MODE=stable
ENV APP_VERSION=1.0.0
ENV APP_PORT=3000

# Start the Flask app
CMD ["python", "main.py"]
