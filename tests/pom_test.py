
import unittest
import xml.dom.minidom
from mvn2get import (
    PROBLEMS,
    Problem,
    parse_xml,
    xml_getnode_text,
)
from .util import (
    find_test_file,
)


class XmlTest(unittest.TestCase):
    def test_parse_bad_plexus(self) -> None:
        # Plexus' POM is not a valid XML document.  But we need to be able to
        # handle it.
        pom_file = find_test_file('plexus-1.0.4.pom')
        root = self._assert_is_pom_xml(parse_xml(pom_file))
        self.assertEqual(xml_getnode_text(root, 'name'), 'Plexus')
        self.assertEqual(xml_getnode_text(root, 'version'), '1.0.4')

    def test_parse_bad_aws(self) -> None:
        # The aws-lambda-java-events POM has an unbound namespace prefix.
        pom_file = find_test_file('aws-lambda-java-events-2.2.7.pom')
        pom_xml = parse_xml(pom_file)
        self.assertIsInstance(pom_xml, xml.dom.minidom.Document)

    def _assert_is_pom_xml(self, pom_xml: object) -> xml.dom.minidom.Element:
        self.assertIsInstance(pom_xml, xml.dom.minidom.Document)
        root = pom_xml.childNodes[0]
        assert isinstance(root, xml.dom.minidom.Element)
        self.assertEqual(root.nodeName, 'project')
        return root
