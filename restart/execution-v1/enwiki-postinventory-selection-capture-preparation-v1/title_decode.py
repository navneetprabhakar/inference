"""Strict XML1.0 character-data decoding ONCE for raw index title lexemes.

Does not parse XML documents or accept markup/DTDs/HTML entities. Original index
lexeme and line are never changed. Literal CR/LF are explicitly held: line-index
framing cannot faithfully represent them, and this helper does not normalize
whitespace. Character references to XML-valid whitespace retain exact scalars.
"""
import hashlib
MAX_RAW_UTF8=65536
ENTITIES={'amp':'&','lt':'<','gt':'>','quot':'"','apos':"'"}

def xmlchar(n):
    return n in (9,10,13) or 0x20<=n<=0xD7FF or 0xE000<=n<=0xFFFD or 0x10000<=n<=0x10FFFF

def decode_once(lexeme):
    if type(lexeme) is not str:raise ValueError('title_lexeme_requires_str')
    try:raw=lexeme.encode('utf8',errors='strict')
    except UnicodeError:raise ValueError('title_lexeme_invalid_UTF8') from None
    if len(raw)>MAX_RAW_UTF8:raise ValueError('title_lexeme_resource_cap')
    if any(not xmlchar(ord(c)) for c in lexeme):raise ValueError('title_literal_not_XML10_char')
    if '\r' in lexeme or '\n' in lexeme:raise ValueError('literal_linebreak_index_representation_hold')
    if '<' in lexeme or ']]>' in lexeme:raise ValueError('title_literal_markup_or_CDATA_close')
    out=[];i=0;count=0
    while i<len(lexeme):
        if lexeme[i]!='&':out.append(lexeme[i]);i+=1;continue
        end=lexeme.find(';',i+1)
        if end<0:raise ValueError('unterminated_XML_reference')
        name=lexeme[i+1:end]
        if name in ENTITIES:value=ENTITIES[name]
        elif name.startswith('#'):
            digits=name[2:] if name.startswith('#x') else name[1:]
            base=16 if name.startswith('#x') else 10
            alphabet='0123456789abcdefABCDEF' if base==16 else '0123456789'
            if not digits:raise ValueError('empty_XML_numeric_reference')
            scalar=0
            for digit in digits:
                if digit not in alphabet:raise ValueError('invalid_XML_numeric_digit')
                scalar=scalar*base+int(digit,base)
                if scalar>0x10FFFF:raise ValueError('XML_numeric_scalar_range')
            if not xmlchar(scalar):raise ValueError('XML_numeric_not_XML10_char')
            value=chr(scalar)
        else:raise ValueError('unknown_XML_entity_no_HTML5')
        out.append(value);i=end+1;count+=1
    semantic=''.join(out)
    return {'raw_index_title':lexeme,'raw_index_title_UTF8_bytes':len(raw),
       'raw_index_title_SHA256':hashlib.sha256(raw).hexdigest(),
       'semantic_expected_title':semantic,
       'semantic_expected_title_SHA256':hashlib.sha256(semantic.encode('utf8')).hexdigest(),
       'references_decoded_once':count,'representation':'XML10_TEXT_ENTITIES_AND_NUMERIC_ONCE',
       'normalization':'NONE_NO_HTML5_CASE_NFC_UNDERSCORE_OR_WHITESPACE_NORMALIZATION'}
