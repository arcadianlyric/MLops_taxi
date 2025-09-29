FROM tensorflow/tfx:1.14.0

# Set working directory
WORKDIR /app

# Install additional dependencies
RUN pip install --upgrade pip && \
    pip install pandas scikit-learn matplotlib seaborn

# Copy pipeline files
COPY taxi_pipeline_native_keras.py /app/
COPY taxi_pipeline_k8s.py /app/
COPY taxi_utils_native_keras.py /app/
COPY data/ /app/data/

# Create necessary directories
RUN mkdir -p /app/pipelines /app/metadata /app/serving_model

# Set environment variables
ENV PYTHONPATH=/app:$PYTHONPATH
ENV TFX_PIPELINE_ROOT=/app/pipelines
ENV TFX_METADATA_PATH=/app/metadata
ENV TFX_SERVING_MODEL_DIR=/app/serving_model

# Make the pipeline executable
RUN chmod +x /app/taxi_pipeline_k8s.py

# Default command - use the Kubernetes-optimized pipeline
CMD ["python", "/app/taxi_pipeline_k8s.py"]
