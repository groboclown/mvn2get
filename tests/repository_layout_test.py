
import unittest

from mvn2get import (
    maven_artifact_path_for_url,
    convert_to_repo_urls_from_url,
    convert_to_repo_urls,
    convert_to_repo_urls_from_artifact,
    CONFIG,
)


class RepositoryLayoutTest(unittest.TestCase):
    def test_convert_to_repo_urls_from_url__no_trailing_slash(self) -> None:
        CONFIG.remote_repo_urls = ['https://repo1.maven.org/maven2/']
        CONFIG.local_repo_urls = []
        res = convert_to_repo_urls_from_url(
            'https://repo1.maven.org/maven2/org/apache/logging/log4j/log4j-slf4j-impl/2.12.1'
        )
        self.assertEqual(
            res,
            ['https://repo1.maven.org/maven2/org/apache/logging/log4j/log4j-slf4j-impl/2.12.1/']
        )
