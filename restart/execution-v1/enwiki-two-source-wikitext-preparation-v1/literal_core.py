"""Apply frozen byte edits only; no regex, template parser or rendering guesses."""
import hashlib
sha=lambda b:hashlib.sha256(b).hexdigest()
def apply(raw,recipe):
 if sha(raw)!=recipe['source_text_SHA256'] or len(raw)!=recipe['source_text_bytes']:raise ValueError('exact_source_hash_size')
 pieces=[];cursor=0;out=0;inverse=[]
 for op in recipe['operations']:
  a=op['start_byte'];b=op['end_exclusive_byte'];old=bytes.fromhex(op['original_hex']);new=bytes.fromhex(op['replacement_hex'])
  if type(a)is not int or type(b)is not int or not cursor<=a<b<=len(raw):raise ValueError('ordered_disjoint_source_spans')
  if raw[a:b]!=old or sha(old)!=op['original_SHA256']:raise ValueError('literal_source_span_mismatch')
  pieces.append(raw[cursor:a]);out+=a-cursor;start=out;pieces.append(new);out+=len(new);cursor=b
  inverse.append({'output_start_byte':start,'output_end_exclusive_byte':out,'original_hex':old.hex(),'replacement_hex':new.hex(),'operation':op['operation'],'source_start_byte':a,'source_end_exclusive_byte':b})
 pieces.append(raw[cursor:]);derived=b''.join(pieces)
 if len(derived)!=recipe['derivative_content_bytes_arithmetic_only']:raise ValueError('predeclared_size_reconciliation')
 if restore(derived,inverse)!=raw:raise ValueError('inverse_exact_source_failure')
 return derived,inverse

def restore(derived,inverse):
 parts=[];cursor=0
 for op in inverse:
  a=op['output_start_byte'];b=op['output_end_exclusive_byte'];new=bytes.fromhex(op['replacement_hex'])
  if not cursor<=a<=b<=len(derived) or derived[a:b]!=new:raise ValueError('inverse_span_or_replacement_mismatch')
  parts.extend([derived[cursor:a],bytes.fromhex(op['original_hex'])]);cursor=b
 parts.append(derived[cursor:]);return b''.join(parts)

def mapped_boundary(position,recipe):
 if any(o['start_byte']<position<o['end_exclusive_byte'] for o in recipe['operations']):raise ValueError('unit_boundary_inside_edit')
 return position+sum(len(bytes.fromhex(o['replacement_hex']))-(o['end_exclusive_byte']-o['start_byte']) for o in recipe['operations'] if o['end_exclusive_byte']<=position)
