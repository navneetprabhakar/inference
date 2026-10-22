"""Literal metadata book-prefix LEADS only. No domain ownership/family clearance."""
import ipaddress,re,unicodedata
from urllib.parse import urlsplit,unquote_to_bytes
SECTIONS={'chapter','front-matter','back-matter','part'}
STATUS={'NONEMPTY_LITERAL_BOOK_PREFIX_CANDIDATE':1,'HOST_ONLY_ROOT_UNCERTAIN':2,'INVALID_PUBLIC_URL_SYNTAX':3,'ORIGIN_MISMATCH_UNCLEARED':4,'QUERY_OR_FRAGMENT_UNCERTAIN':5,'NO_SHARED_NATIVE_PREFIX':6}
def public(value):
 if type(value) is not str or len(value.encode('utf8'))>4096 or any(c.isspace() or unicodedata.category(c) in {'Cc','Cf'} for c in value) or '\\' in value:raise ValueError('URL_chars_length')
 u=urlsplit(value)
 if u.scheme not in {'http','https'} or not u.hostname or u.username is not None or u.password is not None or u.port not in (None,443 if u.scheme=='https' else 80):raise ValueError('URL_scheme_credentials_host_port')
 try:ip=ipaddress.ip_address(u.hostname)
 except ValueError:
  if not re.fullmatch(r'(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}',u.hostname) or u.hostname.endswith(('.localhost','.local','.internal')):raise ValueError('nonpublic_hostname_syntax')
 else:
  if not ip.is_global:raise ValueError('nonpublic_IP')
 if re.search(r'%(?![0-9a-fA-F]{2})',u.path) or '//' in u.path:raise ValueError('ambiguous_path_spelling')
 segments=u.path.split('/')[1:]
 if segments and segments[-1]=='':segments.pop()
 for raw in segments:
  decoded=unquote_to_bytes(raw).decode('utf8',errors='strict')
  if not raw or decoded in {'.','..'} or '/' in decoded or '\\' in decoded or any(unicodedata.category(c) in {'Cc','Cf'} for c in decoded):raise ValueError('unsafe_encoded_path_segment')
 return u,segments

def derive(book_url,url):
 try:b,bs=public(book_url);u,us=public(url)
 except (ValueError,TypeError,UnicodeError):return STATUS['INVALID_PUBLIC_URL_SYNTAX'],None
 origin=lambda x:(x.scheme,x.hostname,x.port or (443 if x.scheme=='https' else 80))
 if origin(b)!=origin(u):return STATUS['ORIGIN_MISMATCH_UNCLEARED'],None
 if b.query or u.query or b.fragment or u.fragment:return STATUS['QUERY_OR_FRAGMENT_UNCERTAIN'],None
 bi=next((i for i,s in enumerate(bs) if s in SECTIONS),None);ui=next((i for i,s in enumerate(us) if s in SECTIONS),None)
 if bi is not None and ui is not None and bs[:bi]==us[:ui]:prefix=bs[:bi]
 elif bi is None and ui is not None and bs==us[:ui]:prefix=bs
 else:return STATUS['NO_SHARED_NATIVE_PREFIX'],None
 # Raw path spelling preserved: no percent/NFC/case/underscore normalization.
 root=b.scheme+'://'+b.netloc+'/'+('/'.join(prefix)+'/' if prefix else '')
 return STATUS['NONEMPTY_LITERAL_BOOK_PREFIX_CANDIDATE'] if prefix else STATUS['HOST_ONLY_ROOT_UNCERTAIN'],root
