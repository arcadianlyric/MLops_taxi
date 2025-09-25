# Use the official TFX image which comes with TFX, TensorFlow, and Beam pre-installed
FROM --platform=linux/amd64 tensorflow/tfx:1.12.0

# Set the working directory in the container
WORKDIR /app

# Copy the entire project into the container
COPY . /app/

# Install additional dependencies from requirements.txt
# The base image already has tfx, tensorflow, apache-beam, and ml-metadata
RUN pip install --no-cache-dir -r requirements.txt

# Set the entrypoint to be a shell
ENTRYPOINT ["/bin/bash"]
