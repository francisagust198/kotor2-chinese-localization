"""Patch localized GFF substrings by hash; append archive resources without repacking unrelated content."""
import hashlib
import re
import struct
from pathlib import Path
from localization import archive_members

def compact(text):
    return re.sub(r'(?<=[\u3400-\u9fff]) +(?=[\u3400-\u9fff])', '', text)

def read_local(b, field_index):
    field_offset = struct.unpack_from('<I',b,16)[0]
    data_offset, data_size = struct.unpack_from('<II',b,32)
    kind,label,value = struct.unpack_from('<III',b,field_offset+12*field_index)
    if kind != 12:
        raise ValueError('Target field is not a localized string')
    q = data_offset+value
    total,strref,count = struct.unpack_from('<III',b,q)
    end = q+4+total
    if total < 8 or end > data_offset+data_size:
        raise ValueError('Invalid localized string bounds')
    q += 12
    strings=[]
    for _ in range(count):
        language,size = struct.unpack_from('<II',b,q);q+=8
        if q+size > end:
            raise ValueError('Invalid substring bounds')
        strings.append((language,b[q:q+size]));q+=size
    if q != end:
        raise ValueError('Unexpected localized string trailing data')
    return strref,strings

def patch_gff(original, rows, encoder=None, preserve_unselected=False, allow_tlk_backed=False):
    encode_text=encoder or (lambda text:text.encode('utf-8'))
    if original[4:8] != b'V3.2':
        raise ValueError('Only GFF V3.2 is supported')
    b=bytearray(original)
    field_offset,field_count = struct.unpack_from('<II',b,16)
    data_offset,data_size = struct.unpack_from('<II',b,32)
    appended=bytearray();by_field={}
    for row in rows:
        if row['field_index'] >= field_count:
            raise ValueError('Field index out of bounds')
        key=(row['field_index'],row['language_gender'])
        if key in by_field:
            raise ValueError('Duplicate substring replacement')
        by_field[key]=row
    fields={key[0] for key in by_field}
    for field in sorted(fields):
        strref,strings=read_local(original,field)
        if strref != 0xffffffff and not allow_tlk_backed:
            raise ValueError('Do not replace a TLK-backed local string')
        body=bytearray(struct.pack('<II',strref,len(strings)))
        used=set()
        for language,raw in strings:
            row=by_field.get((field,language))
            if row:
                if hashlib.sha256(raw).hexdigest() != row['raw_sha256']:
                    raise ValueError('Source substring hash mismatch')
                text=row['candidate_zh'] if row.get('preserve_translation') else compact(row['candidate_zh']);used.add(language)
            else:
                text=raw.decode('cp1252')
            encoded=encode_text(text) if row else (raw if preserve_unselected else encode_text(text))
            body+=struct.pack('<II',language,len(encoded))+encoded
        if len(used) != sum(key[0]==field for key in by_field):
            raise ValueError('Replacement language/gender not found')
        struct.pack_into('<I',b,field_offset+12*field+8,data_size+len(appended))
        appended+=struct.pack('<I',len(body))+body
    old_end=data_offset+data_size
    for header_position in (8,16,24,40,48):
        offset=struct.unpack_from('<I',b,header_position)[0]
        if offset >= old_end:
            struct.pack_into('<I',b,header_position,offset+len(appended))
    struct.pack_into('<I',b,36,data_size+len(appended))
    result=bytes(b[:old_end])+bytes(appended)+bytes(b[old_end:])
    # Validate every localized field, including nonselected fields and all gender slots.
    for field in range(field_count):
        kind=struct.unpack_from('<I',original,field_offset+12*field)[0]
        if kind != 12:
            continue
        before_ref,before=read_local(original,field)
        after_ref,after=read_local(result,field)
        assert before_ref == after_ref and len(before) == len(after)
        for (language,raw),(new_language,new_raw) in zip(before,after):
            assert new_language == language
            row=by_field.get((field,language))
            expected=encode_text(row['candidate_zh'] if row.get('preserve_translation') else compact(row['candidate_zh'])) if row else (raw if preserve_unselected else (raw.decode('cp1252').encode('utf-8') if field in fields else raw))
            assert new_raw == expected
    # Existing field-data bytes remain intact; all modified strings are appended.
    assert result[data_offset:old_end] == original[data_offset:old_end]
    return result

def patch_archive(path, resource_rows, destination, **gff_options):
    original=path.read_bytes();b=bytearray(original)
    is_rim=b[:4]==b'RIM '
    if b[:4] not in (b'ERF ',b'MOD ',b'RIM '):
        raise ValueError('This probe only patches ERF/MOD/RIM archives')
    if is_rim:
        count,key_offset=struct.unpack_from('<II',b,12)
    else:
        count=struct.unpack_from('<I',b,16)[0]
        key_offset,res_offset=struct.unpack_from('<II',b,24)
    found=set()
    for i in range(count):
        if is_rim:
            name,kind,rid,offset,size=struct.unpack_from('<16sIIII',b,key_offset+32*i)
            record_offset=key_offset+32*i+24
        else:
            name,rid,kind,_=struct.unpack_from('<16sIHH',b,key_offset+24*i)
            record_offset=res_offset+rid*8
            offset,size=struct.unpack_from('<II',b,record_offset)
        key=(name.rstrip(b'\x00').decode('ascii'),kind)
        rows=resource_rows.get(key)
        if not rows:
            continue
        if key in found:
            raise ValueError('Duplicate resource identity')
        found.add(key)
        replacement=patch_gff(original[offset:offset+size],rows,**gff_options)
        new_offset=len(b);b+=replacement
        struct.pack_into('<II',b,record_offset,new_offset,len(replacement))
    if found != set(resource_rows):
        raise ValueError('Some patch resource identities were not found')
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(b)
    before=list(archive_members(path));after=list(archive_members(destination))
    assert len(before)==len(after)
    for (name,kind,data),(new_name,new_kind,new_data) in zip(before,after):
        assert (name,kind)==(new_name,new_kind)
        if (name,kind) not in resource_rows:
            assert new_data==data
    return len(found)
