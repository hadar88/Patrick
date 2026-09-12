def test_root(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "Patrick API"}


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_health_does_not_depend_on_database_records(client, user_factory):
    user_factory()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}