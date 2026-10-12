import glob, json, sys, time
fs = sorted(glob.glob('data/raw/*.json'))
print('count', len(fs), flush=True)
for idx, p in enumerate(fs):
    t = time.time()
    with open(p, encoding='utf8') as fh:
        s = fh.read()
    json.loads(s)
    dt = time.time() - t
    if dt > 0.5 or idx % 2000 == 0:
        print(idx, p, round(dt, 2), flush=True)
print('done', flush=True)
