import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_index(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Smart Fridge" in resp.data.decode() or "Умный" in resp.data.decode()


def test_vr_shell(client):
    resp = client.get("/vr-shell")
    assert resp.status_code == 200
    assert "Продукт" in resp.data.decode()


def test_ai_assistant(client):
    resp = client.get("/ai-assistant")
    assert resp.status_code == 200


def test_recipe(client):
    resp = client.get("/recipe")
    assert resp.status_code == 200


def test_statistics(client):
    resp = client.get("/statistics")
    assert resp.status_code == 200


def test_nav_links(client):
    resp = client.get("/")
    html = resp.data.decode()
    assert "/vr-shell" in html
    assert "/ai-assistant" in html
    assert "/statistics" in html
