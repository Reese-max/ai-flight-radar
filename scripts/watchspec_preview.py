"""Render a local reviewed-intent artifact, optionally with a hash-bound receipt."""
from datetime import datetime, timezone
from html import escape
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai.nlp_parser import ParsedSearchIntent
from core.watchspec import ReviewFields, WatchSpec, preview_watch, promote_watch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confirm-hash", help="exact hash shown in the preceding preview")
    args = parser.parse_args()
    request = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(request, dict) or set(request) - {"watch_id", "parsed", "review", "previous", "confirmed_fields"}:
        raise ValueError("unsupported reviewed-intent request fields")
    # ParseRequest's model ignores unknown fields, so guard this boundary explicitly.
    extras = set(request["parsed"]) - set(ParsedSearchIntent.model_fields)
    if extras:
        raise ValueError(f"unreviewed parsed fields: {sorted(extras)}")
    preview = preview_watch(
        ParsedSearchIntent.model_validate(request["parsed"]),
        ReviewFields.model_validate_json(json.dumps(request["review"])),
        watch_id=request["watch_id"],
        previous=WatchSpec.model_validate_json(json.dumps(request["previous"]))
        if request.get("previous") else None,
    )
    if args.confirm_hash:
        preview["promotion_receipt"] = promote_watch(
            preview, confirmed_hash=args.confirm_hash,
            confirmed_fields=request.get("confirmed_fields", []),
            evaluated_at=datetime.now(timezone.utc),
        )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "preview.json").write_text(json.dumps(preview, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    body = escape(json.dumps(preview, ensure_ascii=False, indent=2))
    (args.output / "preview.html").write_text(
        '<!doctype html><html lang="zh-Hant"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>WatchSpec 離線研究預覽</title><main>'
        '<h1>WatchSpec 離線研究預覽</h1><p>尚未建立伺服器追蹤。排程、外部查價、通知均未啟用。'
        '報價不是可購買的最終價格。</p><p>'+escape(preview.get("summary", "條件不完整，請先覆核"))+
        '</p><pre style="white-space:pre-wrap;overflow-wrap:anywhere">'+body+'</pre></main></html>\n',
        encoding="utf-8",
    )
    print(json.dumps({"status": preview["status"], "spec_hash": preview["spec_hash"],
                      "scheduled_collection": "BLOCKED"}))


if __name__ == "__main__":
    main()
