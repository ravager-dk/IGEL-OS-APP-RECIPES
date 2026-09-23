#!/usr/bin/env python3
"""Exercise the shipped Bash launcher against a stub IGEL registry and native argument capture."""
import json,os,pathlib,subprocess,tempfile,unittest
BASE=pathlib.Path(__file__).resolve().parents[2]
SCRIPT=BASE/'APP_Source/Apps/x3270/input/all/config/bin/x3270-launch.sh'
SETTINGS=json.loads((BASE/'utils/x3270/settings.json').read_text())
class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.w=pathlib.Path(self.tmp.name)
        self.app=self.w/'app';(self.app/'bin').mkdir(parents=True);(self.app/'usr/local/bin').mkdir(parents=True)
        self.home=self.w/'home';(self.home/'.x3270').mkdir(parents=True)
        self.capture=self.w/'capture.json';self.reg=self.w/'registry.json'
        for name,body in {
            'x3270':'''import json,os,sys
from pathlib import Path
Path(os.environ['CAPTURE']).write_text(json.dumps({'argv':sys.argv[1:],'rdb':os.environ.get('X3270RDB'),'no_profile':os.environ.get('NOX3270PRO')}))
''',
            'xset':'''import os,sys
from pathlib import Path
with Path(os.environ['XSET_LOG']).open('a') as f:f.write(repr(sys.argv[1:])+'\\n')
''',
            'get':'''import os,json,sys
from pathlib import Path
values=json.loads(Path(os.environ['REGISTRY']).read_text());key=sys.argv[1].removeprefix('app.x3270.options.')
if key not in values:sys.exit(1)
print(values[key])
''',
            'logger':'pass\n',
        }.items():
            p=self.app/('usr/local/bin' if name=='x3270' else 'bin')/name;p.write_text('#!/usr/bin/env python3\n'+body);p.chmod(0o755)
        self.launcher=self.w/'launch';self.launcher.write_text(SCRIPT.read_text().replace('APP=/services/x3270','APP='+str(self.app)))
        self.env=dict(os.environ,DISPLAY=':117',HOME=str(self.home),PATH=str(self.app/'bin')+':'+os.environ['PATH'],REGISTRY=str(self.reg),CAPTURE=str(self.capture),XSET_LOG=str(self.w/'xset.log'))
    def tearDown(self):self.tmp.cleanup()
    def run_launcher(self,updates=None,args=(),managed=True,fail=False):
        cfg={x['key']:x['default'] for x in SETTINGS};cfg['mode']='profile' if managed else 'local';cfg.update(updates or {})
        self.reg.write_text(json.dumps(cfg));self.capture.unlink(missing_ok=True)
        p=subprocess.run(['bash',str(self.launcher),*args],env=self.env,capture_output=True,text=True)
        if fail:
            self.assertNotEqual(p.returncode,0);self.assertFalse(self.capture.exists());return p.stderr
        self.assertEqual(p.returncode,0,p.stderr)
        return json.loads(self.capture.read_text())
    def test_community_runtime_layout(self):
        self.run_launcher(managed=False)
        log=(self.w/'xset.log').read_text()
        self.assertIn(str(self.app/'usr/local/share/fonts/X11/misc'),log)
        self.assertNotIn('LD_LIBRARY_PATH',SCRIPT.read_text())
        self.assertNotIn('x3270.extended:',SCRIPT.read_text())
        session=(BASE/'APP_Source/Apps/x3270/input/all/config/sessions/x32700').read_text()
        self.assertIn('/services/x3270/config/bin/x3270-launch.sh "$@"',session)
    def test_recipe_metadata(self):
        r=BASE/'APP_Source/Apps/x3270'
        self.assertEqual(json.loads((r/'app.json').read_text())['version'],'4.5.6+1.7')
        self.assertEqual(json.loads((r/'igel/thirdparty.json').read_text())[0]['url'],'file:///tmp/x3270.tar.bz2')
        short,separator,long=(r/'data/descriptions/en').read_text().partition('\n\n')
        self.assertTrue(separator and short.strip() and long.strip())
        for p in r.rglob('*.json'):json.loads(p.read_text())
        for p in r.rglob('*'):
            if p.is_file() and p.read_bytes().startswith(b'#!/bin/bash'):
                subprocess.run(['bash','-n',str(p)],check=True)
    def test_defaults_and_explicit_false(self):
        d=self.run_launcher();a=d['argv']
        for value in ['3279-4','bracket','x3270.extendedDataStream: true','x3270.reconnect: false','x3270.once: false','x3270.verifyHostCert: true','x3270.keypadOn: false','base']:self.assertIn(value,a)
        self.assertEqual(d['no_profile'],'1');self.assertIsNone(d['rdb'])
    def test_tls_lu_ipv6(self):
        for h in ['2001:db8::1','[2001:db8::1]']:
            d=self.run_launcher({'host':h,'port':'00992','transport':'tls','lu':'TERM01','tn3270e':'false','disconnect':'reconnect'})
            self.assertEqual(d['argv'][-1],'L:N:TERM01@[2001:db8::1]:992')
            self.assertIn('x3270.startTls: false',d['argv']);self.assertIn('x3270.reconnect: true',d['argv'])
    def test_plain_and_exit(self):
        a=self.run_launcher({'host':'mainframe.example.com','transport':'plain','disconnect':'exit'})['argv']
        self.assertEqual(a[-1],'[mainframe.example.com]:23');self.assertIn('x3270.once: true',a);self.assertIn('x3270.startTls: false',a)
    def test_all_dropdown_values(self):
        for setting in SETTINGS:
            for value,_ in setting.get('choices',[]):
                with self.subTest(key=setting['key'],value=value):self.run_launcher({'host':'host.example',setting['key']:value})
    def test_bool_representations(self):
        for key in [d['key'] for d in SETTINGS if d['type']=='bool']:
            for value in ['true','false','1','0','TRUE','FALSE']:
                with self.subTest(key=key,value=value):self.run_launcher({key:value})
            self.run_launcher({key:'maybe'},fail=True)
    def test_invalid_values(self):
        bad={'port':['0','65536','-1','hello','99999999999999999','$(touch /tmp/no)'],
             'model':['3279-6','-e'],'codepage':['cp99999'],'font':['arbitrary'],
             'host':['-e','L:host','host@bad','host name','host;touch /tmp/no','$(whoami)','host\nx3270.once: true'],
             'lu':['LU@host','A,B','a b'],'transport':['other'],'disconnect':['other'],'mode':['other']}
        for key,values in bad.items():
            for value in values:
                with self.subTest(key=key,value=value):self.run_launcher({'host':'host.example',key:value},fail=True)
    def test_keymap_and_ca_with_spaces(self):
        km=self.w/'map with spaces.xrm';km.write_text((BASE/'APP_Source/Apps/x3270/examples/company-keymap.xrm').read_text())
        ca=self.w/'CA bundle.pem';ca.write_text('fixture')
        d=self.run_launcher({'keymap_file':str(km),'ca_file':str(ca)})
        self.assertEqual(d['rdb'],km.read_text().rstrip('\n'));self.assertIn(str(ca),d['argv']);self.assertEqual(d['argv'][-2:],['-keymap','ums'])
        self.run_launcher({'keymap_file':str(km),'keymap_name':'missing'},fail=True)
        self.run_launcher({'keymap_file':str(km),'keymap_name':'base'},fail=True)
        km.write_text('x3270.keymap.ums: '+('a'*65537));self.run_launcher({'keymap_file':str(km)},fail=True)
    def test_missing_files_fail_without_launch(self):
        for key in ['ca_file','keymap_file']:
            for value in ['/does/not/exist','relative.xrm',str(self.w)]:self.run_launcher({key:value},fail=True)
    def test_local_defaults_and_manual_args(self):
        session=self.home/'.x3270/session.x3270';session.write_text('x3270.model: 3278-2\n')
        self.assertEqual(self.run_launcher(managed=False)['argv'],[])
        self.assertEqual(self.run_launcher(args=['L:host name:992'],managed=False)['argv'][-1],'L:host name:992')
        d=self.run_launcher();self.assertNotIn(str(session),d['argv'])
        self.run_launcher(args=['-e','/bin/sh'],fail=True)
    def test_missing_display_and_version(self):
        self.env.pop('DISPLAY');self.run_launcher(fail=True)
        self.assertEqual(self.run_launcher(args=['-v'])['argv'],['-v'])
    def test_blank_host_validation(self):
        self.run_launcher({'disconnect':'reconnect'},fail=True);self.run_launcher({'lu':'TERM'},fail=True)
    def test_ums_ui_types_and_bindings(self):
        ui=json.loads((BASE/'APP_Source/Apps/x3270/data/config/ui.json').read_text())
        bound={e['paramId'] for page in ui.values() for e in page.get('elements',{}).values() if e.get('type')=='generic'}
        self.assertEqual(bound,{'app.x3270.options.'+d['key'] for d in SETTINGS})
        param=(BASE/'APP_Source/Apps/x3270/data/config/config.param').read_text()
        for d in SETTINGS:
            node=param.split('<'+d['key']+'>')[1].split('</'+d['key']+'>')[0]
            self.assertIn('type=<'+d['type']+'>',node)
            if 'choices' in d:self.assertIn('range=<'+ '|'.join('['+v+']' for v,_ in d['choices'])+'>',node)
if __name__=='__main__':unittest.main(verbosity=2)
