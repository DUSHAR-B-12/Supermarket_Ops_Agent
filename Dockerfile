# Use official Python lightweight image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_HOME=/app
# Force absolute database path — Railway Volume must be mounted at /app/data
ENV DATABASE_URL=sqlite:////app/data/supermarket.db

# Create application directory
WORKDIR $APP_HOME

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Ensure data and output directories exist
RUN mkdir -p data outputs

# Default command
CMD ["python", "run.py"]
