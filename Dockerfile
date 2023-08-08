# Use the official Python image as a parent image
FROM python:3.11

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1


ENV POETRY_HOME=/opt/poetry
ENV POETRY_VENV=/opt/poetry-venv
ENV POETRY_CACHE_DIR=/opt/.cache

# Install poetry separated from system interpreter
RUN python3 -m venv $POETRY_VENV \
    && $POETRY_VENV/bin/pip install -U pip setuptools \
    && $POETRY_VENV/bin/pip install poetry

# Add `poetry` to PATH
ENV PATH="${PATH}:${POETRY_VENV}/bin"

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install project dependencies
RUN poetry config virtualenvs.create false && poetry lock && poetry install

# CMD to run the bot
CMD ["sh", "-c", "cd analyzer && poetry run python bot.py"]
