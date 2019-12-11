
from typing import Optional
import unittest
from mvn2get import MavenVersion


class MavenVersionTest(unittest.TestCase):
    def test_parse_invalid(self) -> None:
        self.assertEqual(MavenVersion('').tokens, [])

        # "ga" and "final" are meaningless as the first token and are ignored.
        self.assertEqual(MavenVersion('ga').tokens, [])
        self.assertEqual(MavenVersion('final').tokens, [])

    def test_parse_single(self) -> None:
        # "True" means numeric, "False" means non-numeric.
        self.assertEqual(MavenVersion('xyz').tokens, [(False, '-xyz')])
        self.assertEqual(MavenVersion('1').tokens, [(True, '-1')])
        self.assertEqual(MavenVersion('1023').tokens, [(True, '-1023')])
        self.assertEqual(MavenVersion('alpha').tokens, [(False, '-alpha')])
        self.assertEqual(MavenVersion('beta').tokens, [(False, '-beta')])
        self.assertEqual(MavenVersion('milestone').tokens, [(False, '-milestone')])
        self.assertEqual(MavenVersion('rc').tokens, [(False, '-rc')])
        self.assertEqual(MavenVersion('cr').tokens, [(False, '-cr')])

    def test_parse_parts(self) -> None:
        self.assertEqual(
            MavenVersion('abc-def.xyz').tokens,
            [(False, '-abc'), (False, '-def'), (False, '.xyz')]
        )
        self.assertEqual(
            MavenVersion('rc1').tokens,
            [(False, '-rc'), (True, '-1')]
        )
        self.assertEqual(
            MavenVersion('5.bard2').tokens,
            [(True, '-5'), (False, '.bard'), (True, '-2')]
        )
        self.assertEqual(MavenVersion('ga.1').tokens, [(True, '.1')])
        self.assertEqual(MavenVersion('final.beta').tokens, [(False, '.beta')])

    def test_parse_no_prefix(self) -> None:
        self.assertEqual(
            MavenVersion('.123-alpha').tokens,
            [(True, '-0'), (True, '.123'), (False, '-alpha')]
        )

    def test_compare_same(self) -> None:
        self._assert_eq('12')
        self._assert_eq('alpha')
        self._assert_eq('single-23', 'single23')
        self._assert_eq('161', '161-final')
        self._assert_eq('161', '161-ga')
        self._assert_eq('161-final', '161-ga')
        self._assert_eq('12-rc')
        self._assert_eq('12-rc', '12-cr')

    def test_compare_not_equal(self) -> None:
        """Check equal, not equal, and compare functions"""
        self._assert_lt('1', '2')
        self._assert_lt('a', 'b')
        self._assert_lt('a', '1')
        self._assert_lt('1.0', '1.1')
        self._assert_lt('1', '1.0')
        self._assert_lt('1', '1-0')
        self._assert_lt('1', '1.a')
        self._assert_lt('1', '1-a')
        self._assert_lt('1.1.2', '1.2')
        self._assert_lt('1.alpha', '1-alpha')
        self._assert_lt('1.a', '1-a')
        self._assert_lt('1-a', '1-1')
        self._assert_lt('1-1', '1.1')
        self._assert_lt('1-alpha', '1-beta')
        self._assert_lt('1-beta', '2-alpha')
        self._assert_lt('1-ga', '1-sp')
        self._assert_lt('1-sp1', '1-sp2')

    def _assert_lt(self, earlier_str: str, later_str: str) -> None:
        earlier = MavenVersion(earlier_str)
        later = MavenVersion(later_str)
        self.assertEqual(
            earlier.compare(later),
            1
        )
        self.assertEqual(
            later.compare(earlier),
            -1
        )
        self.assertTrue(later != earlier)
        self.assertTrue(earlier != later)
        self.assertFalse(later == earlier)
        self.assertFalse(earlier == later)

    def _assert_eq(self, s1: str, s2: Optional[str] = None) -> None:
        if s2 is None:
            s2 = s1
        mv1 = MavenVersion(s1)
        mv2 = MavenVersion(s2)
        self.assertEqual(mv1.compare(mv2), 0)
        self.assertEqual(mv2.compare(mv1), 0)
        self.assertTrue(mv1 == mv2)
        self.assertTrue(mv2 == mv1)
        self.assertFalse(mv1 != mv2)
        self.assertFalse(mv2 != mv1)
