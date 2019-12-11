
import unittest

from mvn2get import (
    maven_artifact_path_for_url,
    convert_to_repo_urls_from_url,
    convert_to_repo_urls,
    convert_to_repo_urls_from_artifact,
    CONFIG,
    PROBLEMS,
    Problem,
)


class RepositoryLayoutTest(unittest.TestCase):
    def test_convert_to_repo_urls_from_url__no_trailing_slash(self) -> None:
        CONFIG.remote_repo_urls = ['https://repo1.maven.org/maven2/']
        CONFIG.local_repo_urls = []
        PROBLEMS.clear()
        res = convert_to_repo_urls_from_url(
            'https://repo1.maven.org/maven2/org/apache/logging/log4j/log4j-slf4j-impl/2.12.1'
        )
        self.assertEqual(
            res,
            ['https://repo1.maven.org/maven2/org/apache/logging/log4j/log4j-slf4j-impl/2.12.1/']
        )
        self.assertEqual(PROBLEMS, [])

    def test_convert_to_repo_urls_from_url__mvnrepo(self) -> None:
        CONFIG.remote_repo_urls = ['https://repo1.maven.org/maven2/']
        CONFIG.local_repo_urls = []
        PROBLEMS.clear()
        res = convert_to_repo_urls_from_url(
            'https://repo1.maven.org/maven2/org.apache.logging.log4j/log4j-slf4j-impl/2.12.1'
        )
        self.assertEqual(
            res,
            ['https://repo1.maven.org/maven2/org/apache/logging/log4j/log4j-slf4j-impl/2.12.1/']
        )
        self.assertEqual(PROBLEMS, [])

    def test_convert_to_repo_urls_from_url__bad_root(self) -> None:
        CONFIG.remote_repo_urls = ['https://repo1.maven.org/maven2/']
        CONFIG.local_repo_urls = []
        PROBLEMS.clear()
        res = convert_to_repo_urls_from_url(
            'http://repo1.maven.org/maven2/org/apache/logging/log4j/log4j-slf4j-impl/2.12.1'
        )
        self.assertEqual(res, [])
        self.assertEqual(PROBLEMS, [
            Problem(
                'http://repo1.maven.org/maven2/org/apache/logging/log4j/log4j-slf4j-impl/2.12.1', [], False,
                "Unknown source repository."
            )
        ])
