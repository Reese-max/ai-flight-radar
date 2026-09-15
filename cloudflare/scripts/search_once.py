"""One provider call, isolated by collector.py's timeout. No database writes."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

def normalize(offers,task):
    valid = [o for o in offers if
        type(o.price_twd) is int and 0 < o.price_twd <= 1000000 and
        o.origin==task['origin'] and o.destination==task['destination'] and
        o.depart_date==task['depart_date'] and o.return_date==task['return_date'] and
        o.trip_type=='round-trip' and o.is_direct and o.stops==0]
    if not valid:
        return {'outcome':'error' if offers else 'empty'}
    best = min(valid,key=lambda o:o.price_twd)
    airline = best.primary_airline
    if not isinstance(airline,str) or not 1 <= len(airline) <= 120 or any(ord(c)<32 for c in airline):
        airline = None
    return {'outcome':'ok','price_twd':best.price_twd,'searched_at':datetime.now(timezone.utc).isoformat(),
            'airline':airline,'offer_count':min(len(valid),1000)}

def main():
    try:
        from collector import validate_task
        task = validate_task(json.loads(sys.stdin.read(16385)))
        from providers.selector import get_provider
        offers = get_provider().search(task['origin'],task['destination'],task['depart_date'],task['return_date'],max_stops=0)
        print(json.dumps(normalize(offers,task)))
    except Exception:
        # Never print upstream HTML, response bodies, secrets, or raw exceptions.
        print(json.dumps({'outcome':'error'}))

if __name__ == '__main__':
    main()
