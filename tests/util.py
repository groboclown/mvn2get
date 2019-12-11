

import os

TEST_DIR = os.path.dirname(os.path.abspath(__file__))


def find_test_file(name: str) -> str:
    filename = os.path.join(TEST_DIR, 'data', name)
    assert os.path.isfile(filename)
    return filename


def read_file(name: str) -> str:
    with open(find_test_file(name), 'r') as f:
        return f.read()
