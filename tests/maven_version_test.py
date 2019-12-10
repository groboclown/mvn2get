
import unittest
from mvn2get import MavenVersion


class MavenVersionTest(unittest.TestCase):
    def test_parse_just_text(self) -> None:
        mv = MavenVersion('xyz')
        self.assertEqual(
            mv.tokens,
            [(False, '-xyz')]
        )

    def test_parse_text_parts(self) -> None:
        mv = MavenVersion('abc-def.xyz')
        self.assertEqual(
            mv.tokens,
            [(False, '-abc'), (False, '-def'), (False, '.xyz')]
        )

    def test_parse_no_prefix(self) -> None:
        mv = MavenVersion('.1-alpha')
        self.assertEqual(
            mv.tokens,
            [(True, '-0'), (True, '.1'), (False, '-alpha')]
        )
