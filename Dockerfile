# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libxml2-dev \
    libxslt-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create results directory
RUN mkdir -p results

# Copy and make startup script executable
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Expose port 8877
EXPOSE 8877

# Set environment variables for asyncio compatibility
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONASYNCIODEBUG=0
ENV SCRAPY_SETTINGS_MODULE=GoogleIndexSpider.settings

# Use the startup script
CMD ["/app/start.sh"]