
import unittest
from mvn2get import (
    verify_checksum,
    verify_checksums,
    PROBLEMS,
    Problem,
)
from .util import (
    find_test_file,
)


class ChecksumTest(unittest.TestCase):
    def test_valid_md5(self) -> None:
        # This md5 is just a plain md5 checksum in the file.
        PROBLEMS.clear()
        base_filename = find_test_file('aws-lambda-java-events-2.2.7.pom')
        verify_checksum('x', base_filename, 'md5')
        self.assertEqual(PROBLEMS, [])

        # This one has a filename suffix
        PROBLEMS.clear()
        base_filename = find_test_file('plexus-1.0.4.pom')
        verify_checksum('x', base_filename, 'md5')
        self.assertEqual(PROBLEMS, [])

    def test_valid_sha1(self) -> None:
        # This md5 is just a plain sha1 checksum in the file.
        PROBLEMS.clear()
        base_filename = find_test_file('aws-lambda-java-events-2.2.7.pom')
        verify_checksum('x', base_filename, 'sha1')
        self.assertEqual(PROBLEMS, [])

        # This one has a filename suffix
        PROBLEMS.clear()
        base_filename = find_test_file('plexus-1.0.4.pom')
        verify_checksum('x', base_filename, 'sha1')
        self.assertEqual(PROBLEMS, [])
