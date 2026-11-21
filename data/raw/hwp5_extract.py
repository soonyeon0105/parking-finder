"""HWP 5.0 본문 텍스트 추출 — PrvText + BodyText(raw deflate) 교차 확인용.
사용법: python3 hwp5_extract.py <file.hwp>"""
import sys, zlib, struct, olefile

def prvtext(path):
    ole = olefile.OleFileIO(path)
    return ole.openstream('PrvText').read().decode('utf-16-le', errors='replace')

def bodytext(path):
    ole = olefile.OleFileIO(path)
    data = ole.openstream('BodyText/Section0').read()
    out = zlib.decompressobj(-15).decompress(data)
    pos, texts = 0, []
    while pos + 4 <= len(out):
        header = struct.unpack('<I', out[pos:pos+4])[0]
        tag = header & 0x3FF; size = (header >> 20) & 0xFFF
        pos += 4
        if size == 0xFFF:
            size = struct.unpack('<I', out[pos:pos+4])[0]; pos += 4
        rec = out[pos:pos+size]; pos += size
        if tag == 67:
            texts.append(rec.decode('utf-16-le', errors='replace'))
    return ''.join(texts)

if __name__ == '__main__':
    print('=== PrvText ===')
    print(prvtext(sys.argv[1]))
    print('=== BodyText ===')
    print(bodytext(sys.argv[1]))
