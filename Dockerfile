# Use a modern, slim Python base image for better compatibility and smaller size
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file first to leverage Docker layer caching
# This prevents re-installing dependencies on every code change
COPY app-requirements.txt ./requirements.txt

# Install all dependencies from the requirements file
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the ports the application will run on
EXPOSE 8000
EXPOSE 8501

# No entrypoint is needed, as the command will be specified in the Kubernetes deployment manifest
