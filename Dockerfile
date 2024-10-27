# Use a lightweight Python image
FROM python:3.13-slim

# Install Poetry
RUN pip install --no-cache-dir poetry flask

# Set the working directory
WORKDIR /app

# Copy only the dependency files first for caching
COPY pyproject.toml poetry.lock /app/

# Install dependencies with Poetry in a virtual environment-free mode
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

# Copy the entire project directory into the container
COPY . /app

# Expose the Flask app port
EXPOSE 5000

# Run the Flask app
CMD ["python", "omnilogic.py"]
