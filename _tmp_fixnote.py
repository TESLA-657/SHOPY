import io
p = 'core/templates/core/noter_vendeur.html'
c = io.open(p, encoding='utf-8').read()
old = '{% if\u5df2\u7ecf\u6709_note %}'
assert old in c, 'motif absent'
io.open(p, 'w', encoding='utf-8').write(c.replace(old, '{% if deja_note %}'))
print('corrige')
