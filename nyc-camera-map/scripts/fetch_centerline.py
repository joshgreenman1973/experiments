"""Download the NYC street centerline file, which the intersection gazetteer needs.

122,244 segments, paged 50,000 at a time. Only the fields the gazetteer uses are
requested, which keeps the download to about 40MB rather than several hundred.
"""
import json
import os
import time
import urllib.parse
import urllib.request

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'raw')
RESOURCE = 'https://data.cityofnewyork.us/resource/inkn-q76z.json?'
FIELDS = 'the_geom,stname_label,full_street_name,boroughcode,rw_type,physicalid'


def main():
    os.makedirs(RAW, exist_ok=True)
    out = []
    offset = 0
    while True:
        url = RESOURCE + urllib.parse.urlencode({
            '$select': FIELDS, '$limit': 50000,
            '$offset': offset, '$order': 'physicalid'})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(url, timeout=240) as r:
                    batch = json.load(r)
                break
            except Exception as e:
                print('retry', e, flush=True)
                time.sleep(6)
        else:
            raise SystemExit('FAILED to fetch centerline at offset %d' % offset)
        if not batch:
            break
        out.extend(batch)
        offset += len(batch)
        print('fetched', offset, flush=True)
        if len(batch) < 50000:
            break
    if len(out) < 100000:
        raise SystemExit('FAIL: only %d centerline segments' % len(out))
    json.dump(out, open(os.path.join(RAW, 'centerline.json'), 'w'))
    print('total segments', len(out))


if __name__ == '__main__':
    main()
