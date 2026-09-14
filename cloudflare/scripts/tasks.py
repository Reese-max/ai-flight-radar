"""Create a reviewable task plan. No writes/network unless --execute."""
import argparse
from datetime import datetime,timedelta
import json
import os
from pathlib import Path
import sys
import time
from zoneinfo import ZoneInfo
from collector import Client,SafeFailure,ORIGINS,DESTINATIONS

ROUTES = [(o,d) for o in sorted(ORIGINS) for d in sorted(DESTINATIONS)]

def plan(today,offset=30,nights=4):
    if type(offset) is not int or not 1 <= offset <= 300 or type(nights) is not int or not 1 <= nights <= 30:
        raise SafeFailure('Invalid plan duration')
    dep,ret = today+timedelta(days=offset),today+timedelta(days=offset+nights)
    return {'tasks':[{'origin':o,'destination':d,'depart_date':dep.isoformat(),'return_date':ret.isoformat()} for o,d in ROUTES]}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path)
    p.add_argument('--file',type=Path)
    p.add_argument('--execute',action='store_true')
    args = p.parse_args()
    if args.file:
        if args.file.stat().st_size > 16384:
            raise SafeFailure('Task plan exceeds size cap')
        data = json.loads(args.file.read_text(encoding='utf-8'))
    else:
        data = plan(datetime.now(ZoneInfo('Asia/Taipei')).date())
    if not isinstance(data,dict) or set(data) != {'tasks'} or not isinstance(data['tasks'],list) or not 1 <= len(data['tasks']) <= 96:
        raise SafeFailure('Plan must contain 1-96 task objects')
    rendered = json.dumps(data,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        with args.output.open('x',encoding='utf-8') as stream:
            stream.write(rendered)
    if not args.execute:
        print(rendered,end='')
        print('Dry-run plan only; no task was sent.',file=sys.stderr)
        return
    if not args.file:
        raise SafeFailure('Review a saved --file before executing; implicit plans are never submitted')
    client = Client(os.getenv('RADAR_URL',''),os.getenv('RADAR_ADMIN_KEY',''),role='admin')
    client.verify()
    tasks = data['tasks']
    for i in range(0,len(tasks),24):
        print(json.dumps(client.call('/api/admin/tasks',{'tasks':tasks[i:i+24]})))
        if i+24 < len(tasks):
            time.sleep(65)  # admin seed budget is one call per minute

if __name__ == '__main__':
    try:
        main()
    except (SafeFailure,OSError,ValueError) as exc:
        print(str(exc) if isinstance(exc,SafeFailure) else 'Task plan could not be read or created',file=sys.stderr)
        raise SystemExit(2)
