import glob,json,collections
fs=sorted(glob.glob('data/raw/*.json'))
mx='';miss=collections.Counter();tgt=collections.Counter();so=0;sub=0;h=collections.Counter()
for p in fs:
    d=json.load(open(p,encoding='utf8'));i=d['info'];dt=i['dates'][0]
    mx=max(mx,dt)
    if dt<'2023-10-12': continue
    if 'missing' in i: miss[json.dumps(i['missing'])[:80]]+=1
    if i.get('balls_per_over')==5: h[i.get('event',{}).get('name')]+=1
    for inn in d['innings']:
        if 'target' in inn: tgt[json.dumps(sorted(inn['target'].keys()))]+=1
        if inn.get('super_over'): so+=1
        for ov in inn.get('overs',[]):
            for dl in ov['deliveries']:
                for w in dl.get('wickets',[]):
                    for f in w.get('fielders',[]):
                        if f.get('substitute'): sub+=1
print('max date',mx);print('missing',miss.most_common(5));print('target',tgt);print('super overs',so,'sub fielders',sub);print('5-ball',h.most_common(5))
