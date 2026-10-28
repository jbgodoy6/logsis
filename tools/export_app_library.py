"""Export mobile BIN presets/limit metadata from the same Studio profiles."""
from pathlib import Path
import hashlib
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from logsis_studio.core import Project,available_models,nominal_limits
from logsis_studio import __version__
root=ROOT/'app/android/app/src/main/assets/library';root.mkdir(parents=True,exist_ok=True)
catalog=['model\tlabel\tchannels\tsha256']
for model in available_models():
    p=Project.new(model);data=p.bin_bytes();(root/(model+'.bin')).write_bytes(data)
    catalog.append('\t'.join([model,p.profile.label or model,str(p.profile.count),hashlib.sha256(data).hexdigest()]))
    lines=[]
    for c in p.profile.channels:
        if nominal_limits(c,p.nominal) is None:continue
        if '_v_' in c.role or (not c.role and (9<=c.number<=14 or 30<=c.number<=35)):
            ln=c.role.endswith(('l1n','l2n','l3n')) if c.role else c.number in [9,10,11,30,31,32]
            kind='LN' if ln else 'LL'
        elif c.role.endswith('_frequency') or (not c.role and c.number in [8,29]):kind='FREQ'
        elif c.role=='battery' or (not c.role and c.number==6):kind='BATTERY'
        else:kind='RPM'
        lines.append(f'{c.index}\t{kind}\t{c.divisor}')
    (root/(model+'.limits.tsv')).write_text('\n'.join(lines)+'\n',encoding='utf-8')
(root/'catalog.tsv').write_text('\n'.join(catalog)+'\n',encoding='utf-8')
(root/'provenance.txt').write_text('LogSis Studio '+__version__+' BIN presets. No Grafana dashboards.\nProfile SHA-256: '+hashlib.sha256((ROOT/'logsis_studio/resources/profiles.json').read_bytes()).hexdigest()+'\n',encoding='utf-8')
print('Exported',len(available_models()),'mobile BIN presets with Studio metadata.')
