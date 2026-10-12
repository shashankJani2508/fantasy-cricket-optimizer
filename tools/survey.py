import json, glob, collections, sys

root = sys.argv[1]
c = {k: collections.Counter() for k in
     ['match_type', 'gender', 'team_type', 'outcome_keys', 'result', 'method',
      'balls_per_over', 'info_keys', 'extras', 'wicket_kinds', 'overs_field', 'replacements']}
n = 0
bad = []
for idx, p in enumerate(sorted(glob.glob(root + '/*.json'))):
    if idx % 2000 == 0:
        print('progress', idx, flush=True)
    try:
        d = json.load(open(p, encoding='utf8'))
    except Exception as e:
        bad.append((p, repr(e)[:200]))
        continue
    n += 1
    i = d.get('info', {})
    c['match_type'][i.get('match_type')] += 1
    c['gender'][i.get('gender')] += 1
    c['team_type'][i.get('team_type')] += 1
    c['balls_per_over'][i.get('balls_per_over')] += 1
    for k in i:
        c['info_keys'][k] += 1
    o = i.get('outcome', {}) or {}
    for k in o:
        c['outcome_keys'][k] += 1
    if 'result' in o:
        c['result'][o['result']] += 1
    if 'method' in o:
        c['method'][o['method']] += 1
    if 'overs' in i:
        c['overs_field'][i['overs']] += 1
    if 'replacements' in i:
        c['replacements'][tuple(sorted(i['replacements'].keys()))] += 1
    for inn in d.get('innings', []):
        for ov in inn.get('overs', []):
            for dl in ov.get('deliveries', []):
                for k in dl.get('extras', {}):
                    c['extras'][k] += 1
                for w in dl.get('wickets', []):
                    c['wicket_kinds'][w.get('kind')] += 1

print('matches', n, 'unreadable', len(bad), bad[:5])
for k, v in c.items():
    print(k, dict(v))
