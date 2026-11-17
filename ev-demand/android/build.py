"""Build Android without Gradle: Android SDK 35, ECJ 3.39, Python 3 and Java 21.
Signing material must be outside the repository; see README.md.
"""
import hashlib,json,os,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parent
SDK=Path(os.environ['ANDROID_HOME'])
BT=SDK/'build-tools/35.0.0'
JAR=SDK/'platforms/android-35/android.jar'
ECJ=Path(os.environ['ECJ_JAR'])
KEY=Path(os.environ['DMAX_ANDROID_KEYSTORE']).resolve()
PASSWORD=Path(os.environ['DMAX_ANDROID_PASSWORD_FILE']).resolve()
if KEY.is_relative_to(REPO) or PASSWORD.is_relative_to(REPO):raise SystemExit('Keep signing material outside the repository')
BUILD=ROOT/'build';BUILD.mkdir(exist_ok=True)
def run(*args):subprocess.run([str(a) for a in args],check=True,cwd=ROOT)
run(sys.executable,ROOT/'prepare_assets.py')
resources=BUILD/'resources.zip'
if resources.exists():resources.unlink()
run(BT/'aapt2','compile','--dir',ROOT/'res','-o',resources)
base=BUILD/'base.apk'
run(BT/'aapt2','link','-o',base,'-I',JAR,'--manifest',ROOT/'AndroidManifest.xml','-A',BUILD/'assets',resources)
classes=BUILD/'classes';classes.mkdir(exist_ok=True)
for p in classes.rglob('*.class'):p.unlink()
run('java','-jar',ECJ,'-8','-proc:none','-classpath',JAR,'-d',classes,*sorted((ROOT/'src').rglob('*.java')))
classjar=BUILD/'classes.jar'
with zipfile.ZipFile(classjar,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(classes.rglob('*.class')):z.write(p,p.relative_to(classes))
dex=BUILD/'dex';dex.mkdir(exist_ok=True)
run(BT/'d8','--release','--min-api','29','--lib',JAR,'--output',dex,classjar)
with zipfile.ZipFile(base,'a',zipfile.ZIP_DEFLATED) as z:z.write(dex/'classes.dex','classes.dex')
aligned=BUILD/'aligned.apk';run(BT/'zipalign','-f','-p','4',base,aligned)
output=BUILD/'D-Max-Android-1.0.0.apk'
run(BT/'apksigner','sign','--ks',KEY,'--ks-key-alias','dmaxandroid','--ks-pass','file:'+str(PASSWORD),'--out',output,aligned)
run(BT/'apksigner','verify','--verbose','--print-certs',output)
run(BT/'aapt2','dump','badging',output)
digest=hashlib.sha256(output.read_bytes()).hexdigest();output.with_suffix('.apk.sha256').write_text(digest+'  '+output.name+'\n')
print(json.dumps({'artifact':str(output),'sha256':digest,'bytes':output.stat().st_size}))
