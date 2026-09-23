#!/usr/bin/env python3
"""Generate native IGEL parameter/UI files from the reviewed setting definitions."""
import json
from pathlib import Path
BASE=Path(__file__).resolve().parents[2]
R=BASE/'APP_Source/Apps/x3270'
settings=json.loads((BASE/'utils/x3270/settings.json').read_text())
param=(R/'data/config/config.param').read_text().split('</sessions>',1)[0]+'</sessions>\n<options>\n'
for d in settings:
    param+=f'    <{d["key"]}>\n'
    props={'value':d['default'],'type':d['type'],'runtime':'true','displayname[en_us]':d['label'],'tooltip[en_us]':d['tooltip']}
    if 'choices' in d:
        props['range']='|'.join('['+v+']' for v,_ in d['choices'])
        props['range[en_us]']=''.join('['+v+']' for _,v in d['choices'])
    for k,v in props.items():
        assert '<' not in v and '>' not in v and '\n' not in v
        param+=f'        {k}=<{v}>\n'
    param+=f'    </{d["key"]}>\n'
param+='</options>\n'
(R/'data/config/config.param').write_text(param)
ui=json.loads((R/'data/config/ui.json').read_text())
groups={'connection':'Connection','security':'TLS certificates','display':'Terminal and display','keyboard':'Keyboard'}
ui['base']['childrenIds']=['sessions',*groups]
tr=json.loads((R/'data/config/translation.json').read_text())
for key,title in groups.items():
    ui[key]={'id':key,'parentId':'base','nlsResourceId':key+'.label','title':title,'elements':{str(i):{'type':'generic','paramId':'app.x3270.options.'+d['key']} for i,d in enumerate(x for x in settings if x['group']==key)}}
    tr[key+'.label']={'en':title}
(R/'data/config/ui.json').write_text(json.dumps(ui,indent=2)+'\n')
(R/'data/config/translation.json').write_text(json.dumps(tr,indent=2)+'\n')
print('Generated',len(settings),'typed settings')
