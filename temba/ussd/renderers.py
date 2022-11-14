"""
Written by Keeya Emmanuel Lubowa
On 23th Aug, 2022
Email ekeeya@oddjobs.tech
"""
from io import StringIO

from django.utils.xmlutils import SimplerXMLGenerator
from rest_framework import renderers
from rest_framework_xml.renderers import XMLRenderer


class PlainTextRenderer(renderers.BaseRenderer):
    media_type = 'text/plain'
    format = 'txt'
    charset = 'utf-8'

    def render(self, data, media_type=None, renderer_context=None):
        if isinstance(data, dict):
            if 'detail' in data:
                return data['detail'].encode(self.charset)
        return data.encode(self.charset)


class CustomXMLRenderer(XMLRenderer):
    """
    Since the default XMLRenderer handles application/xml, we needed one for text/xml
    """
    media_type = "text/xml"
    root_tag_name = "response"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """
        Renders `data` into serialized XML.
        """
        if data is None:
            return ""

        stream = StringIO()

        xml = SimplerXMLGenerator(stream, self.charset)
        xml.startDocument()
        xml.startElement(self.root_tag_name, {})

        self._to_xml(xml, data)

        xml.endElement(self.root_tag_name)
        xml.endDocument()
        return stream.getvalue()
