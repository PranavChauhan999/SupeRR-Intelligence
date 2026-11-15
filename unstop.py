import json
from pathlib import Path
root=Path(__file__).parent
d=json.loads((root/'data/snapshot.json').read_text())
lines=['SUPERR SELECTOR | ROUND 1','Unstop player selection order','Frozen analysis '+d['freeze'],'']
for role,label in [('bat','BATTING'),('bowl','BOWLING')]:
    group=sorted((p for p in d['players'] if p['role']==role and p['rank'] and p['rank']<=10),key=lambda p:p['rank'])
    lines.extend([label,*[f"{p['rank']:2d}. {p['name']}" for p in group],''])
(root/'files').mkdir(exist_ok=True)
(root/'files/SupeRR-Unstop.txt').write_text('\n'.join(lines)+'\n')
