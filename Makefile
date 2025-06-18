SHELL := /bin/bash

.PHONY: migrations migrate runserver test lint clean worker format

DJANGO_APP_NAME := realmate_challenge
DJANGO_SETTINGS_PATH := ${DJANGO_APP_NAME}.settings

migrations:
	@echo "Creating new Django migrations..."
	DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_PATH} poetry run python manage.py makemigrations

migrate:
	@echo "Applying Django migrations..."
	DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_PATH} poetry run python manage.py migrate

runserver:
	@echo "Starting the Django development server..."
	DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_PATH} poetry run python manage.py runserver 0.0.0.0:8000

worker:
	@echo "Starting celery worker..."
	DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_PATH} poetry run celery -A ${DJANGO_APP_NAME} worker -l info

test:
	@echo "Running tests with 100% code coverage..."
	DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_PATH} poetry run pytest -vv --maxfail=1
lint:
	@echo "Running the linter (ruff)..."
	poetry run ruff check .

format:
	@echo "Formatting code with ruff..."
	poetry run ruff format .

clean:
	@echo "Cleaning temporary files and coverage reports..."
	@rm -f .coverage
	@rm -rf htmlcov/
	@find . -name "__pycache__" -exec rm -rf {} +
	@find . -name "*.pyc" -delete