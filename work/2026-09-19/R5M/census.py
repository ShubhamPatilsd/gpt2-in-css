# R5M: element census of index.html by class-prefix (digits normalised), plus registered-property / animation / keyframes counts from runtime.css.
import re, sys, collections
B = sys.argv[1] if len(sys.argv) > 1 else 'bundles/combined7'
html = open(f'{B}/index.html').read()
css = open(f'{B}/runtime.css').read()
tags = re.findall(r'<([a-zA-Z][\w-]*)([^>]*)>', html)
print('elements (open tags):', len(tags))
byclass = collections.Counter()
bytag = collections.Counter()
for t, attrs in tags:
    bytag[t] += 1
    m = re.search(r'class="([^"]*)"', attrs)
    if m:
        first = m.group(1).split()[0] if m.group(1).split() else ''
        byclass[re.sub(r'\d+', 'N', first)] += 1
    else:
        i = re.search(r'id="([^"]*)"', attrs)
        byclass['#' + re.sub(r'\d+', 'N', i.group(1)) if i else f'<{t}> (no class)'] += 1
print('by tag:', bytag.most_common(12))
print('by first-class pattern (top 40):')
for k, v in byclass.most_common(40): print(f'  {v:8d} {k}')
props = re.findall(r'@property\s+(--[\w-]+)\s*\{([^}]*)\}', css)
inh = sum(1 for p, b in props if 'inherits:true' in b.replace(' ', ''))
print('@property:', len(props), 'inherits:true', inh)
pp = collections.Counter(re.sub(r'\d+', 'N', p) for p, b in props)
print(' top @property patterns:', pp.most_common(25))
print('@keyframes:', len(re.findall(r'@keyframes', css)))
print('animation-name decls:', len(re.findall(r'animation-name:', css)), 'view-timeline decls:', len(re.findall(r'view-timeline(?:-name)?:', css)), 'timeline-scope:', len(re.findall(r'timeline-scope:', css)))
print('transition decls:', len(re.findall(r'transition(?:-property)?:', css)))
print('var() count:', css.count('var('), 'css bytes', len(css), 'html bytes', len(html))
