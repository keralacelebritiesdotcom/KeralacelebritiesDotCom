#!/usr/bin/env python3
"""Generate blogs.json from metadata in blogs/Travel-*.html."""
from pathlib import Path
from html.parser import HTMLParser
import json
ROOT=Path(__file__).resolve().parent
class Parser(HTMLParser):
    def __init__(self): super().__init__(); self.meta={}
    def handle_starttag(self,tag,attrs):
        if tag.lower()=='meta':
            a=dict(attrs); k=a.get('name','')
            if k.startswith('travel-'): self.meta[k[7:]]=a.get('content','')
stories=[]
for p in (ROOT/'blogs').glob('Travel-*.html'):
    parser=Parser(); parser.feed(p.read_text(encoding='utf-8')); m=parser.meta
    stories.append({'title':m.get('title') or p.stem,'description':m.get('description',''),'image':m.get('image',''),'category':m.get('category','Travel Story'),'date':m.get('date',''),'url':f'blogs/{p.name}'})
stories.sort(key=lambda x:x.get('date',''),reverse=True)
(ROOT/'blogs.json').write_text(json.dumps(stories,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f'Wrote {len(stories)} travel stories to blogs.json')
