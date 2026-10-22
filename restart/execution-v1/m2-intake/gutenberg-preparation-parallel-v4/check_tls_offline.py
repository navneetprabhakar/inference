"""Real TLS handshakes over MemoryBIO; no sockets, HTTP or trust-store mutation."""
import datetime,json,pathlib,ssl,tempfile
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import discover as d

def handshake(client_context,cert_path,key_path,hostname):
 server_context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);server_context.load_cert_chain(cert_path,key_path)
 ci,co,si,so=(ssl.MemoryBIO() for _ in range(4));c=client_context.wrap_bio(ci,co,server_side=False,server_hostname=hostname);s=server_context.wrap_bio(si,so,server_side=True)
 cdone=sdone=False
 for _ in range(100):
  for conn,done in [(c,cdone),(s,sdone)]:
   if done:continue
   try:
    conn.do_handshake()
    if conn is c:cdone=True
    else:sdone=True
   except ssl.SSLWantReadError:pass
  b=co.read()
  if b:si.write(b)
  b=so.read()
  if b:ci.write(b)
  if cdone and sdone:return True
 raise AssertionError('Bounded in-memory handshake did not settle')
checks=[]
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);now=datetime.datetime.now(datetime.timezone.utc)
 key=rsa.generate_private_key(public_exponent=65537,key_size=2048);name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Offline synthetic fixture')])
 cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(123456).not_valid_before(now-datetime.timedelta(days=1)).not_valid_after(now+datetime.timedelta(days=1)).add_extension(x509.BasicConstraints(ca=True,path_length=None),critical=True).add_extension(x509.SubjectAlternativeName([x509.DNSName('fixture.invalid')]),critical=False).sign(key,hashes.SHA256())
 cp=root/'fixture.pem';kp=root/'fixture.key';cp.write_bytes(cert.public_bytes(serialization.Encoding.PEM));kp.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));kp.chmod(0o600)
 ctx=d.trusted_context();assert ctx.verify_mode==ssl.CERT_REQUIRED and ctx.check_hostname;checks.append('production_context_requires_chain_and_hostname')
 try:handshake(ctx,str(cp),str(kp),'fixture.invalid')
 except ssl.SSLCertVerificationError:checks.append('production_bundle_rejects_untrusted_self_signed_chain')
 else:raise AssertionError('Untrusted self-signed chain accepted')
 trusted=ssl.create_default_context(cafile=str(cp));assert handshake(trusted,str(cp),str(kp),'fixture.invalid');checks.append('offline_harness_valid_chain_control')
 try:handshake(trusted,str(cp),str(kp),'wrong.invalid')
 except ssl.SSLCertVerificationError:checks.append('hostname_mismatch_rejected')
 else:raise AssertionError('Wrong hostname accepted')
 from unittest.mock import patch
 with patch.object(d,'CA_SHA256','0'*64):
  try:d.trusted_context()
  except ValueError:checks.append('changed_bundle_hash_refused')
  else:raise AssertionError('Wrong CA pin accepted')
out={'status':'PASS_OFFLINE_TLS_NO_NETWORK','checks':len(checks),'cases':checks,'public_bundle_sha256':d.CA_SHA256,'does_not_prove':'No Gutenberg peer chain was available offline; endpoint success remains unproven until a separately dispatched bounded request.'}
pathlib.Path(__file__).with_name('tls-check-result.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
