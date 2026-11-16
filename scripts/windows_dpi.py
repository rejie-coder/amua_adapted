"""Derive a DPI-unaware GUI launcher from the pinned Java 8 launcher.

Keep original signed runtime binaries intact. The private copy has only its DPI
manifest, PE checksum and Authenticode certificate directory changed. The obsolete
certificate is removed; the derived launcher is intentionally unsigned.
"""
import struct
from pathlib import Path

OLD=b'       <dpiAware>true</dpiAware>'
NEW=b'      <dpiAware>false</dpiAware>'
def derive(data):
    if data[:2]!=b'MZ':raise ValueError('Expected PE launcher')
    pe=struct.unpack_from('<I',data,0x3c)[0];optional=pe+24
    if data[pe:pe+4]!=b'PE\0\0' or struct.unpack_from('<H',data,optional)[0]!=0x20b:raise ValueError('Expected PE32+')
    if data.count(OLD)!=1 or len(OLD)!=len(NEW):raise ValueError('Pinned Java DPI manifest differs')
    start=data.index(b'<assembly ');end=data.index(b'</assembly>',start)+len(b'</assembly>')
    if OLD not in data[start:end]:raise ValueError('DPI marker is outside manifest')
    cert_entry=optional+112+4*8
    cert,size=struct.unpack_from('<II',data,cert_entry)
    if cert and cert+size!=len(data):raise ValueError('Unexpected certificate layout')
    result=bytearray(data[:cert] if cert else data)
    at=result.index(OLD);result[at:at+len(OLD)]=NEW
    struct.pack_into('<II',result,cert_entry,0,0)
    struct.pack_into('<I',result,optional+64,0) # user-mode PE checksum
    return bytes(result)

def install(runtime):
    source=runtime/'bin/javaw.exe';target=runtime/'bin/amua-javaw.exe'
    target.write_bytes(derive(source.read_bytes()))
    return target
