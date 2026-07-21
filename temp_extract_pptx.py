import zipfile
import os
import xml.etree.ElementTree as ET

path = r'C:\Users\USER\Downloads\BI_Platform_Architecture.pptx'
with zipfile.ZipFile(path) as z:
    names = [n for n in z.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')]
    ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
    for name in sorted(names):
        root = ET.fromstring(z.read(name))
        texts = []
        for t in root.findall('.//a:t', ns):
            txt = t.text or ''
            if txt.strip():
                texts.append(txt)
        print('---' + os.path.basename(name) + '---')
        print('\n'.join(texts[:120]))
        print()
