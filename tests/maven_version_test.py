
import unittest
from mvn2get import MavenVersion


class MavenVersionTest(unittest.TestCase):
    def test_just_text(self) -> None:
        mv = MavenVersion('xyz')
        self.assertEqual(
            mv.tokens,
            [(False, '-xyz')]
        )
