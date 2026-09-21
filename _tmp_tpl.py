import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')
import django
django.setup()
import glob
from django.template import engines
e = engines['django']
bad = []
files = sorted(glob.glob('core/templates/core/*.html'))
for f in files:
    name = 'core/' + os.path.basename(f)
    try:
        e.get_template(name)
    except Exception as ex:
        bad.append((name, str(ex)[:110]))
print('fichiers:', len(files))
print('erreurs:', len(bad))
for b in bad:
    print('FAIL', b[0], '::', b[1])
print('fini')
