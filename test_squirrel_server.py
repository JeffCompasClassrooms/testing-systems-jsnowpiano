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
    import socket
    import platform
    
    # Kill any process using port 8080 first
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    port_in_use = sock.connect_ex(('localhost', 8080)) == 0
    sock.close()
    
    if port_in_use:
        if platform.system() == "Windows":
            subprocess.run(
                ["powershell", "-Command", 
                 "Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"],
                capture_output=True,
                text=True
            )
        else:
            subprocess.run(
                ["sh", "-c", "lsof -ti:8080 | xargs kill -9"],
                capture_output=True,
                text=True
            )
        time.sleep(2)
    
    db_path = "squirrel_db.db"
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except PermissionError:
            time.sleep(1)
            try:
                os.remove(db_path)
            except PermissionError:
                pass
    
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
    import socket
    import platform
    import signal
    
    lock_file = "squirrel_tests.lock"
    
    if os.path.exists(lock_file):
        print("Another test instance detected. Ending other instance")
        try:
            with open(lock_file, 'r') as f:
                old_pid = int(f.read().strip())
            
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/F", "/PID", str(old_pid)], 
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                os.kill(old_pid, signal.SIGKILL)
            
            time.sleep(1)
            print("Previous test instance killed.")
        except (ValueError, ProcessLookupError, FileNotFoundError):
            pass
        

        if os.path.exists(lock_file):
            os.remove(lock_file)
    
    with open(lock_file, 'w') as f:
        f.write(str(os.getpid()))
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        port_in_use = sock.connect_ex(('localhost', 8080)) == 0
        sock.close()
        
        if port_in_use:
            print("\nKilling existing server on port 8080...")
            
            if platform.system() == "Windows":
                subprocess.run(
                    ["powershell", "-Command", 
                     "Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"],
                    capture_output=True,
                    text=True
                )
            else:
                subprocess.run(
                    ["sh", "-c", "lsof -ti:8080 | xargs kill -9"],
                    capture_output=True,
                    text=True
                )
            
            time.sleep(1)
        
        proc = subprocess.Popen([sys.executable, "squirrel_server.py"], 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
        time.sleep(1)
        
        yield
        
        proc.terminate()
        proc.wait()
    finally:
        # Remove lock file
        if os.path.exists(lock_file):
            os.remove(lock_file)

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
    
    def it_returns_multiple_squirrels(http_client, clean_db, request_headers):
        # Create multiple squirrels
        for name, size in [("Rocky", "medium"), ("Sandy", "small"), ("Bruno", "large")]:
            body = urllib.parse.urlencode({'name': name, 'size': size})
            conn = http.client.HTTPConnection("localhost:8080")
            conn.request("POST", "/squirrels", body=body, headers=request_headers)
            conn.getresponse()
            conn.close()
        
        http_client.request("GET", "/squirrels")
        response = http_client.getresponse()
        data = json.loads(response.read())
        assert len(data) == 3
        names = [s["name"] for s in data]
        assert "Rocky" in names
        assert "Sandy" in names
        assert "Bruno" in names


def describe_post_squirrels():

    def it_creates_a_new_squirrel(http_client, clean_db, request_headers, request_body, db):
        http_client.request("POST", "/squirrels", body=request_body, headers=request_headers)
        response = http_client.getresponse()
        assert response.status == 201
        squirrels = db.getSquirrels()
        assert any(s["name"] == "Sam" for s in squirrels)

    def it_returns_404_if_post_has_id(http_client, request_headers, request_body):
        http_client.request("POST", "/squirrels/1", body=request_body, headers=request_headers)
        response = http_client.getresponse()
        assert response.status == 404
    
    def it_returns_400_when_missing_size(http_client, request_headers):
        body = urllib.parse.urlencode({'name': 'Incomplete'})
        http_client.request("POST", "/squirrels", body=body, headers=request_headers)
        response = http_client.getresponse()
        assert response.status == 400
    
    def it_returns_400_when_missing_name(http_client, request_headers):
        body = urllib.parse.urlencode({'size': 'large'})
        http_client.request("POST", "/squirrels", body=body, headers=request_headers)
        response = http_client.getresponse()
        assert response.status == 400
    
    def it_creates_squirrel_and_can_retrieve_it(http_client, clean_db, request_headers):
        body = urllib.parse.urlencode({'name': 'TestSquirrel', 'size': 'tiny'})
        http_client.request("POST", "/squirrels", body=body, headers=request_headers)
        response = http_client.getresponse()
        response.read()
        assert response.status == 201
        
        # Retrieve all squirrels to find the created one
        conn = http.client.HTTPConnection("localhost:8080")
        conn.request("GET", "/squirrels")
        get_response = conn.getresponse()
        squirrels = json.loads(get_response.read())
        conn.close()
        
        created = [s for s in squirrels if s["name"] == "TestSquirrel"]
        assert len(created) == 1
        assert created[0]["size"] == "tiny"
    
    def it_assigns_unique_ids_to_multiple_squirrels(http_client, clean_db, request_headers):
        # Create multiple squirrels
        for i in range(3):
            body = urllib.parse.urlencode({'name': f'Squirrel{i}', 'size': 'medium'})
            conn = http.client.HTTPConnection("localhost:8080")
            conn.request("POST", "/squirrels", body=body, headers=request_headers)
            conn.getresponse()
            conn.close()
        
        # Verify all have unique IDs
        http_client.request("GET", "/squirrels")
        response = http_client.getresponse()
        squirrels = json.loads(response.read())
        ids = [s["id"] for s in squirrels]
        assert len(ids) == len(set(ids))  # All IDs are unique


def describe_get_squirrel_by_id():

    def it_retrieves_existing_squirrel(http_client, clean_db, make_a_squirrel):
        http_client.request("GET", f"/squirrels/{make_a_squirrel}")
        response = http_client.getresponse()
        data = json.loads(response.read())
        assert data["name"] == "Furina"
        assert data["size"] == "small"
        assert data["id"] == make_a_squirrel

    def it_returns_404_for_nonexistent_squirrel(http_client):
        http_client.request("GET", "/squirrels/9999")
        response = http_client.getresponse()
        assert response.status == 404

    def it_returns_404_for_non_integer_id(http_client):
        http_client.request("GET", "/squirrels/banana")
        response = http_client.getresponse()
        assert response.status == 404
    
    def it_returns_json_content_type_for_valid_squirrel(http_client, clean_db, make_a_squirrel):
        http_client.request("GET", f"/squirrels/{make_a_squirrel}")
        response = http_client.getresponse()
        assert response.getheader("Content-Type") == "application/json"
    
    def it_returns_404_for_zero_id(http_client):
        http_client.request("GET", "/squirrels/0")
        response = http_client.getresponse()
        assert response.status == 404
    
    def it_returns_404_for_negative_id(http_client):
        http_client.request("GET", "/squirrels/-1")
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
    
    def it_verifies_update_by_retrieving(http_client, clean_db, make_a_squirrel, request_headers):
        # Update the squirrel
        body = urllib.parse.urlencode({"name": "UpdatedName", "size": "huge"})
        http_client.request("PUT", f"/squirrels/{make_a_squirrel}", body=body, headers=request_headers)
        response = http_client.getresponse()
        response.read()
        assert response.status == 204
        
        # Verify the update by retrieving
        conn = http.client.HTTPConnection("localhost:8080")
        conn.request("GET", f"/squirrels/{make_a_squirrel}")
        get_response = conn.getresponse()
        updated_squirrel = json.loads(get_response.read())
        conn.close()
        
        assert updated_squirrel["name"] == "UpdatedName"
        assert updated_squirrel["size"] == "huge"
        assert updated_squirrel["id"] == make_a_squirrel
    
    def it_returns_404_for_put_without_id(http_client, request_headers):
        body = urllib.parse.urlencode({"name": "NoID", "size": "small"})
        http_client.request("PUT", "/squirrels", body=body, headers=request_headers)
        response = http_client.getresponse()
        assert response.status == 404
    
    def it_returns_400_when_missing_size(http_client, clean_db, make_a_squirrel, request_headers):
        body = urllib.parse.urlencode({"name": "Incomplete"})
        http_client.request("PUT", f"/squirrels/{make_a_squirrel}", body=body, headers=request_headers)
        response = http_client.getresponse()
        assert response.status == 400
    
    def it_returns_400_when_missing_name(http_client, clean_db, make_a_squirrel, request_headers):
        body = urllib.parse.urlencode({"size": "huge"})
        http_client.request("PUT", f"/squirrels/{make_a_squirrel}", body=body, headers=request_headers)
        response = http_client.getresponse()
        assert response.status == 400


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
    
    def it_verifies_deletion_by_retrieving(http_client, clean_db, make_a_squirrel):
        # Delete the squirrel
        http_client.request("DELETE", f"/squirrels/{make_a_squirrel}")
        response = http_client.getresponse()
        response.read()
        assert response.status == 204
        
        # Verify deletion by trying to retrieve
        conn = http.client.HTTPConnection("localhost:8080")
        conn.request("GET", f"/squirrels/{make_a_squirrel}")
        get_response = conn.getresponse()
        conn.close()
        assert get_response.status == 404
    
    def it_verifies_deletion_removes_from_list(http_client, clean_db, make_a_squirrel):
        # Get initial count
        conn = http.client.HTTPConnection("localhost:8080")
        conn.request("GET", "/squirrels")
        before = json.loads(conn.getresponse().read())
        conn.close()
        initial_count = len(before)
        
        # Delete the squirrel
        http_client.request("DELETE", f"/squirrels/{make_a_squirrel}")
        response = http_client.getresponse()
        response.read()
        
        # Verify count decreased
        conn = http.client.HTTPConnection("localhost:8080")
        conn.request("GET", "/squirrels")
        after = json.loads(conn.getresponse().read())
        conn.close()
        assert len(after) == initial_count - 1
    
    def it_returns_404_for_delete_without_id(http_client):
        http_client.request("DELETE", "/squirrels")
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
    
    def it_returns_404_for_post_to_invalid_resource(http_client, request_headers):
        body = urllib.parse.urlencode({'name': 'Test', 'size': 'small'})
        http_client.request("POST", "/birds", body=body, headers=request_headers)
        response = http_client.getresponse()
        assert response.status == 404
    
    def it_returns_404_for_empty_path(http_client):
        http_client.request("GET", "")
        response = http_client.getresponse()
        assert response.status == 404
    
    def it_returns_404_for_delete_invalid_resource(http_client):
        http_client.request("DELETE", "/birds/1")
        response = http_client.getresponse()
        assert response.status == 404
