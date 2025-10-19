import os
import pickle
import pytest
from mydb import MyDB




@pytest.fixture
def db_filename():
    return "mydatabase.db"

@pytest.fixture
def nonempty_db(db_filename):
    with open(db_filename, "wb") as f:
        pickle.dump(["stuff", "more stuff"], f)

@pytest.fixture(autouse=True)
def cleanup(db_filename):
    yield
    if os.path.exists(db_filename):
        os.remove(db_filename)




def describe_MyDB():

    def describe_init():
        def it_sets_the_filename_attribute(db_filename):
            db = MyDB(db_filename)
            assert db.fname == db_filename

        def it_creates_a_new_empty_file_if_missing(db_filename):
            assert not os.path.exists(db_filename)
            MyDB(db_filename)
            assert os.path.exists(db_filename)
            with open(db_filename, "rb") as f:
                assert pickle.load(f) == []

        def it_keeps_existing_data(nonempty_db, db_filename):
            before = pickle.load(open(db_filename, "rb"))
            MyDB(db_filename)
            after = pickle.load(open(db_filename, "rb"))
            assert before == after

    def describe_loadStrings():
        def it_returns_empty_list_when_file_is_empty(db_filename):
            db = MyDB(db_filename)
            assert db.loadStrings() == []

        def it_returns_existing_data(nonempty_db, db_filename):
            db = MyDB(db_filename)
            assert db.loadStrings() == ["stuff", "more stuff"]

    def describe_saveStrings():
        def it_saves_list_of_strings(db_filename):
            db = MyDB(db_filename)
            data = ["acorn", "oak", "maple"]
            db.saveStrings(data)
            with open(db_filename, "rb") as f:
                assert pickle.load(f) == data

        def it_overwrites_previous_data(nonempty_db, db_filename):
            db = MyDB(db_filename)
            new_data = ["pine", "cedar"]
            db.saveStrings(new_data)
            with open(db_filename, "rb") as f:
                assert pickle.load(f) == new_data


    def describe_saveString():
        def it_adds_a_string_to_an_empty_file(db_filename):
            db = MyDB(db_filename)
            db.saveString("squirrel")
            with open(db_filename, "rb") as f:
                assert pickle.load(f) == ["squirrel"]

        def it_adds_a_string_to_existing_data(nonempty_db, db_filename):
            db = MyDB(db_filename)
            db.saveString("nuts")
            with open(db_filename, "rb") as f:
                data = pickle.load(f)
            assert data == ["stuff", "more stuff", "nuts"]
