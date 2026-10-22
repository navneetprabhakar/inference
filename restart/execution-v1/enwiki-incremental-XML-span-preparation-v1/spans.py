"""Incremental original-XML page spans; no native-source reader or admission.

Hash the original bytes, including CDATA/entity spelling and closing tags.
Memory retains an incomplete lexical token plus one bounded feed, not a page.
The caller supplies semantic SAX handlers and consumes emitted rows promptly.
"""
import hashlib
import xml.parsers.expat as expat


class PageSpans:
    def __init__(self, emit, *, start=lambda *a: None, end=lambda *a: None,
                 data=lambda *a: None, feed_cap=65536, token_cap=1048576,
                 decoded_cap=256000000000, page_cap=25792234):
        for value in (feed_cap, token_cap, decoded_cap, page_cap):
            if type(value) is not int or value <= 0:
                raise ValueError('positive_finite_limits_required')
        if feed_cap > token_cap:
            raise ValueError('feed_exceeds_lexical_limit')
        self.feed_cap, self.token_cap = feed_cap, token_cap
        self.decoded_cap, self.page_cap = decoded_cap, page_cap
        self.emit, self.on_start, self.on_end, self.on_data = emit, start, end, data
        self.parser = expat.ParserCreate(namespace_separator='}')
        self.parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
        self.parser.StartElementHandler = self._start
        self.parser.EndElementHandler = self._end
        self.parser.CharacterDataHandler = self.on_data
        self.parser.XmlDeclHandler = self._declaration
        for name in ('StartDoctypeDeclHandler', 'EntityDeclHandler',
                     'ExternalEntityRefHandler', 'SkippedEntityHandler'):
            setattr(self.parser, name, self._forbid)
        self.raw = bytearray()
        self.base = self.decoded = self.depth = self.pages = self.max_retained = 0
        self.namespace = None
        self.active = None
        self.root_closed = self.finished = self.failed = False
        self.prefix = bytearray()

    def _forbid(self, *args):
        raise ValueError('DTD_or_entity_forbidden')

    def _declaration(self, version, encoding, standalone):
        if encoding and encoding.lower().replace('-', '') != 'utf8':
            raise ValueError('UTF8_required')

    def _start(self, name, attrs):
        ns, _, local = name.rpartition('}')
        if self.depth == 0:
            if local != 'mediawiki' or not ns.startswith('http://www.mediawiki.org/xml/export-') or not ns.endswith('/'):
                raise ValueError('native_mediawiki_root_required')
            self.namespace = ns
        if ns != self.namespace:
            raise ValueError('mixed_native_namespace')
        if self.depth == 1 and local == 'page':
            if self.active is not None or self.pages >= self.page_cap:
                raise ValueError('page_cardinality_limit')
            pos = self.parser.CurrentByteIndex
            self.active = {'start': pos, 'cursor': pos, 'hash': hashlib.sha256()}
        self.depth += 1
        self.on_start(name, attrs)

    def _hash_until(self, pos):
        if self.active is None:
            return
        cursor = self.active['cursor']
        if not self.base <= cursor <= pos <= self.base + len(self.raw):
            raise ValueError('source_hash_cursor_outside_buffer')
        self.active['hash'].update(memoryview(self.raw)[cursor-self.base:pos-self.base])
        self.active['cursor'] = pos

    def _closing_end(self):
        pos = self.parser.CurrentByteIndex
        i = pos - self.base
        if i < 0 or i > len(self.raw):
            raise ValueError('end_callback_outside_retained_source')
        if self.raw[i:i+2] == b'</':
            j = self.raw.find(b'>', i)
            if j < 0:
                raise ValueError('complete_closing_tag_unavailable')
            return self.base + j + 1
        if i >= 2 and self.raw[i-2:i] == b'/>':
            return pos
        raise ValueError('unsupported_end_callback_position')

    def _end(self, name):
        self.on_end(name)
        self.depth -= 1
        if self.depth == 1 and name == self.namespace + '}page':
            end = self._closing_end()
            self._hash_until(end)
            row = {'ordinal': self.pages + 1, 'start': self.active['start'],
                   'end': end, 'bytes': end-self.active['start'],
                   'SHA256': self.active['hash'].hexdigest()}
            self.pages += 1
            self.active = None
            self.emit(row)
        if self.depth == 0:
            self.root_closed = True

    def feed(self, chunk):
        if self.finished or self.failed:
            raise ValueError('terminal_parser')
        if type(chunk) is not bytes or not 0 < len(chunk) <= self.feed_cap:
            raise ValueError('nonempty_bounded_bytes_required')
        if self.decoded + len(chunk) > self.decoded_cap:
            self.failed = True
            raise ValueError('decoded_limit')
        try:
            self.raw.extend(chunk)
            self.decoded += len(chunk)
            self.max_retained = max(self.max_retained, len(self.raw))
            if len(self.raw) > self.token_cap + self.feed_cap:
                raise ValueError('incomplete_lexical_token_limit')
            if len(self.prefix) < 4:
                self.prefix.extend(chunk[:4-len(self.prefix)])
                if b'\0' in self.prefix or self.prefix.startswith((b'\xff\xfe', b'\xfe\xff')):
                    raise ValueError('nonUTF8_prefix')
            self.parser.Parse(chunk, False)
            # Expat may defer reparsing an incomplete token. Only its consumed
            # cursor is safe: hashing all delivered bytes could include bytes
            # beyond a deferred closing-page callback.
            self._hash_until(self.parser.CurrentByteIndex)
            keep = self.parser.CurrentByteIndex
            if not self.base <= keep <= self.decoded:
                raise ValueError('parser_consumption_position')
            # Keep two bytes before the parser cursor for an empty element whose
            # EndElement callback is delivered at the next feed boundary.
            keep = max(self.base, keep-2)
            del self.raw[:keep-self.base]
            self.base = keep
            if len(self.raw) > self.token_cap:
                raise ValueError('incomplete_lexical_token_limit')
        except BaseException:
            self.failed = True
            raise

    def finish(self):
        if self.finished or self.failed:
            raise ValueError('terminal_parser')
        try:
            self.parser.Parse(b'', True)
            if self.active is not None or self.depth != 0 or not self.root_closed:
                raise ValueError('actual_XML_root_not_closed')
            self.finished = True
            return {'pages': self.pages, 'decoded_bytes': self.decoded,
                    'max_retained_source_bytes': self.max_retained,
                    'actual_root_closed': True}
        except BaseException:
            self.failed = True
            raise
