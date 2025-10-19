# test_squirrel_server.py
import http.client
import json
import os
import pytest
import shutil
import subprocess
import sys
import time
import urllib

from squirrel_db import SquirrelDB


todo = pytest.mark.skip(reason='todo: pending spec')



@pytest.fixture(scope="session", autouse=True)
def prepare_db_before_server():

    db_path = "squirrel_db.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    shutil.copyfile("empty_squirrel_db.db", db_path)
    yield

    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except PermissionError:
            time.sleep(0.5)
            try:
                os.remove(db_path)
            except PermissionError:
                pass 


@pytest.fixture
def clean_db():

    db_path = "squirrel_db.db"
    shutil.copyfile("empty_squirrel_db.db", db_path)
    yield


@pytest.fixture(scope="session", autouse=True)
def start_and_stop_server(prepare_db_before_server):

    proc = subprocess.Popen([sys.executable, "squirrel_server.py"])
    time.sleep(1) 
    yield
    proc.terminate()
    proc.wait()

@pytest.fixture
def http_client():
    conn = http.client.HTTPConnection("localhost:8080")
    yield conn
    conn.close()


@pytest.fixture
def request_body():
    return urllib.parse.urlencode({'name': 'Sam', 'size': 'large'})


@pytest.fixture
def request_headers():
    return {'Content-Type': 'application/x-www-form-urlencoded'}


@pytest.fixture
def db():
    return SquirrelDB()


@pytest.fixture
def make_a_squirrel():
    conn = http.client.HTTPConnection("localhost:8080")
    body = urllib.parse.urlencode({'name': 'Furina', 'size': 'small'})
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    conn.request("POST", "/squirrels", body=body, headers=headers)
    response = conn.getresponse()
    conn.close()
    db = SquirrelDB()
    squirrels = db.getSquirrels()
    for squirrel in squirrels:
        if squirrel["name"] == "Furina" and squirrel["size"] == "small":
            return squirrel["id"]
    return None





def describe_get_squirrels():

    def it_returns_200_status_code(http_client):
        http_client.request("GET", "/squirrels")
        response = http_client.getresponse()
        assert response.status == 200

    def it_returns_json_content_type_header(http_client):
        http_client.request("GET", "/squirrels")
        response = http_client.getresponse()
        assert response.getheader("Content-Type") == "application/json"

    def it_returns_empty_json_array(http_client, clean_db):
        http_client.request("GET", "/squirrels")
        response = http_client.getresponse()
        data = json.loads(response.read())
        assert data == []

    def it_returns_json_array_with_one_squirrel(http_client, clean_db, make_a_squirrel):
        http_client.request("GET", "/squirrels")
        response = http_client.getresponse()
        data = json.loads(response.read())
        assert len(data) == 1
        assert data[0]["name"] == "Furina"
        assert data[0]["size"] == "small"


def describe_post_squirrels():

    def it_creates_a_new_squirrel(http_client, request_headers, request_body, db):
        http_client.request("POST", "/squirrels", body=request_body, headers=request_headers)
        response = http_client.getresponse()
        assert response.status == 201
        squirrels = db.getSquirrels()
        assert any(s["name"] == "Sam" for s in squirrels)

    def it_returns_404_if_post_has_id(http_client, request_headers, request_body):
        http_client.request("POST", "/squirrels/1", body=request_body, headers=request_headers)
        response = http_client.getresponse()
        assert response.status == 404


def describe_get_squirrel_by_id():

    def it_retrieves_existing_squirrel(http_client, clean_db, make_a_squirrel):
        http_client.request("GET", f"/squirrels/{make_a_squirrel}")
        response = http_client.getresponse()
        data = json.loads(response.read())
        assert data["name"] == "Furina"

    def it_returns_404_for_nonexistent_squirrel(http_client):
        http_client.request("GET", "/squirrels/9999")
        response = http_client.getresponse()
        assert response.status == 404

    def it_returns_404_for_non_integer_id(http_client):
        http_client.request("GET", "/squirrels/banana")
        response = http_client.getresponse()
        assert response.status == 404


def describe_put_squirrel():

    def it_updates_existing_squirrel(http_client, clean_db, make_a_squirrel, request_headers):
        body = urllib.parse.urlencode({"name": "Chip", "size": "medium"})
        http_client.request("PUT", f"/squirrels/{make_a_squirrel}", body=body, headers=request_headers)
        response = http_client.getresponse()
        assert response.status == 204

    def it_returns_404_for_missing_id(http_client, request_headers):
        body = urllib.parse.urlencode({"name": "Ghost", "size": "tiny"})
        http_client.request("PUT", "/squirrels/9999", body=body, headers=request_headers)
        response = http_client.getresponse()
        assert response.status == 404

    def it_returns_404_for_invalid_resource(http_client, request_headers):
        body = urllib.parse.urlencode({"name": "Nowhere", "size": "small"})
        http_client.request("PUT", "/cats/1", body=body, headers=request_headers)
        response = http_client.getresponse()
        assert response.status == 404


def describe_delete_squirrel():

    def it_deletes_existing_squirrel(http_client, clean_db, make_a_squirrel):
        http_client.request("DELETE", f"/squirrels/{make_a_squirrel}")
        response = http_client.getresponse()
        assert response.status == 204

    def it_returns_404_for_nonexistent_squirrel(http_client):
        http_client.request("DELETE", "/squirrels/9999")
        response = http_client.getresponse()
        assert response.status == 404

    def it_returns_404_for_invalid_resource(http_client):
        http_client.request("DELETE", "/trees/1")
        response = http_client.getresponse()
        assert response.status == 404


def describe_404_cases():

    def it_returns_404_for_invalid_route(http_client):
        http_client.request("GET", "/rabbits")
        response = http_client.getresponse()
        assert response.status == 404

    def it_returns_404_for_invalid_subpath(http_client):
        http_client.request("GET", "/squirrels/abc/extra")
        response = http_client.getresponse()
        assert response.status == 404

    def it_returns_404_for_root_path(http_client):
        http_client.request("GET", "/")
        response = http_client.getresponse()
        assert response.status == 404
