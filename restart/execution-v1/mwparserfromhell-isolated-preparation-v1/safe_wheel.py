"""Exact inert wheel inventory/RECORD verification and bounded safe unpack."""
import base64,csv,hashlib,io,pathlib,stat,zipfile
WHEEL_SHA='efe6e5255379ff66a08d2102004b26a456692dafbab0cb1e52bed275a43f1c4c';WHEEL_BYTES=154635;CAP=5000000
RECORD='mwparserfromhell-0.7.2.dist-info/RECORD';LICENSE='mwparserfromhell-0.7.2.dist-info/licenses/LICENSE'
sha=lambda b:hashlib.sha256(b).hexdigest()
def safe_name(name):
 p=pathlib.PurePosixPath(name)
 if any(part in ['', '.', '..'] for part in name.rstrip('/').split('/')):raise ValueError('noncanonical_ZIP_path')
 if not name or '\\' in name or '\x00' in name or p.is_absolute() or '..' in p.parts or any(x in ['', '.'] for x in p.parts) or ':' in p.parts[0]:raise ValueError('unsafe_ZIP_path')
 if p.parts[0] not in ['mwparserfromhell','mwparserfromhell-0.7.2.dist-info'] or name.endswith('.pth') or '.data' in p.parts:raise ValueError('unexpected_wheel_package_or_script_path')
 return p

def inspect(path,check=lambda:None):
 raw=path.read_bytes()
 if len(raw)!=WHEEL_BYTES or sha(raw)!=WHEEL_SHA:raise ValueError('exact_verified_wheel_hash_size')
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  infos=z.infolist();names=[i.filename for i in infos]
  if len(infos)>100 or len(set(names))!=len(names):raise ValueError('wheel_member_count_or_duplicate_path')
  total=0;files={}
  for i in infos:
   check();safe_name(i.filename)
   if i.flag_bits&1 or stat.S_ISLNK(i.external_attr>>16) or i.file_size<0 or i.file_size>CAP:raise ValueError('encrypted_symlink_or_oversize_member')
   if i.is_dir():
    if i.file_size:raise ValueError('nonempty_directory')
    continue
   total+=i.file_size
   if total>CAP:raise ValueError('aggregate_extracted5MB')
   body=z.read(i) # ZIP CRC validated, each exactdeclared member<=5MB.
   if len(body)!=i.file_size:raise ValueError('ZIP_member_declared_length')
   files[i.filename]={'bytes':len(body),'SHA256':sha(body),'CRC32':i.CRC}
  records=list(csv.reader(io.StringIO(z.read(RECORD).decode('utf8'))));recordpaths=[]
  for row in records:
   if len(row)!=3:raise ValueError('RECORD_three_fields')
   name,digest,length=row;safe_name(name);recordpaths.append(name)
   if name not in files:raise ValueError('RECORD_missing_file')
   if name==RECORD:
    if digest or length:raise ValueError('RECORD_self_must_be_unhashed')
   else:
    expected='sha256='+base64.urlsafe_b64encode(bytes.fromhex(files[name]['SHA256'])).decode().rstrip('=')
    if digest!=expected or length!=str(files[name]['bytes']):raise ValueError('RECORD_SHA256_size_mismatch')
  if len(set(recordpaths))!=len(recordpaths) or set(recordpaths)!=set(files):raise ValueError('RECORD_exact_file_inventory')
  license=z.read(LICENSE)
  if b'Permission is hereby granted, free of charge' not in license or b'THE SOFTWARE IS PROVIDED "AS IS"' not in license:raise ValueError('complete_MIT_license_required')
 return {'wheel_SHA256':sha(raw),'wheel_bytes':len(raw),'files':files,'file_count':len(files),'extracted_bytes':total,'RECORD_SHA256':files[RECORD]['SHA256'],'LICENSE_SHA256':files[LICENSE]['SHA256'],'all_member_CRCs_and_RECORDs_verified':True,'no_scripts_dependencies_or_network':True}

def unpack(path,target,expected,check=lambda:None):
 actual=inspect(path,check)
 if actual!=expected:raise ValueError('frozen_wheel_inventory_changed')
 if target.exists() or target.is_symlink():raise ValueError('existing_install_target_no_retry')
 target.mkdir(parents=True)
 with zipfile.ZipFile(path) as z:
  total=0
  for name,record in actual['files'].items():
   check();rel=safe_name(name);dest=target.joinpath(*rel.parts);dest.parent.mkdir(parents=True,exist_ok=True);body=z.read(name)
   if sha(body)!=record['SHA256'] or len(body)!=record['bytes'] or total+len(body)>CAP:raise ValueError('prewrite_extracted_cap_hash')
   with dest.open('xb') as f:f.write(body)
   total+=len(body)
 if {str(p.relative_to(target)):sha(p.read_bytes()) for p in target.rglob('*') if p.is_file()}!={n:v['SHA256'] for n,v in actual['files'].items()}:raise ValueError('complete_installed_inventory_hashes')
 return actual
