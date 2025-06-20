import os
import pytest
import redis
import psycopg2
import socket

TIMEOUT = 30.0

@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig):
    return pytestconfig.rootpath / "docker-compose.yml"


@pytest.fixture(scope="session")
def django_settings():
    from realmate_challenge import settings
    return settings


@pytest.fixture(scope="session")
def wait_for_redis_service(django_settings, docker_services):
    def is_responsive():
        client = redis.Redis.from_url(url=django_settings.CELERY_BROKER_URL)
        try:
            return client.ping()
        except redis.exceptions.ConnectionError:
            return False

    docker_services.wait_until_responsive(
        timeout=TIMEOUT, pause=0.1, check=lambda: is_responsive()
    )


@pytest.fixture(scope="session")
def wait_for_postgres_service(django_settings, docker_services):
    def is_responsive():
        try:
            conn = psycopg2.connect(
                dbname=django_settings.DATABASES['default']['NAME'],
                user=django_settings.DATABASES['default']['USER'],
                password=django_settings.DATABASES['default']['PASSWORD'],
                host=django_settings.DATABASES['default']['HOST'],
                port=django_settings.DATABASES['default']['PORT'],
            )
            conn.close()
            return True
        except psycopg2.OperationalError:
            return False

    docker_services.wait_until_responsive(
        timeout=TIMEOUT, pause=0.1, check=lambda: is_responsive()
    )


@pytest.fixture(scope="session")
def wait_for_django_service(django_settings, docker_services):
    def is_responsive():
        host, port = os.getenv("DJANGO_HOST"), os.getenv("DJANGO_PORT")
        try:
            with socket.create_connection(
                (host, port)
                ,timeout=2
            ):
                return True
        except (ConnectionRefusedError, socket.timeout):
            return False

    docker_services.wait_until_responsive(
        timeout=TIMEOUT, pause=0.1, check=lambda: is_responsive()
    )

@pytest.fixture(autouse=True, scope="session")
def setup_only_for_integration_tests(
    request,
    wait_for_redis_service,
    wait_for_postgres_service,
    wait_for_django_service
):
    if "integration" in request.node.keywords:
        pass
