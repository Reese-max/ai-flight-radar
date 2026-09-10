import sys
import argparse
import uvicorn
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from sqlmodel import Session, select, func

from config.settings import settings
from core.database import init_db, engine
from core.models import Route, Deal, FlightSearchRecord, SearchTask
from engine.scheduler import RadarScheduler
from engine.planner import ProgressivePlanner
from ai.nlp_parser import NLPIntentParser
from ai.insight_generator import DealInsightGenerator

console = Console()

def cmd_init():
    console.print("[bold green]Initializing AI Flight Radar Database...[/bold green]")
    init_db()
    count = ProgressivePlanner.generate_search_tasks()
    console.print(f"[green]✓ Database ready. Generated {count} progressive search tasks.[/green]")

def cmd_status():
    init_db()
    with Session(engine) as session:
        routes_count = session.exec(select(func.count(Route.id))).one()
        deals_count = session.exec(select(func.count(Deal.id)).where(Deal.status == "active")).one()
        records_count = session.exec(select(func.count(FlightSearchRecord.id))).one()
        tasks_count = session.exec(select(func.count(SearchTask.id))).one()
        
        console.print(Panel.fit(
            f"[bold cyan]AI Flight Radar 狀態總覽[/bold cyan]\n"
            f"• 監控中航線數：[bold yellow]{routes_count}[/bold yellow]\n"
            f"• 今日有效 Deals：[bold green]{deals_count}[/bold green]\n"
            f"• 歷史查價記錄：[bold blue]{records_count}[/bold blue]\n"
            f"• 佇列排程任務：[bold magenta]{tasks_count}[/bold magenta]\n"
            f"• 推播頻道 (ntfy)：[underline]{settings.NTFY_SERVER}/{settings.NTFY_TOPIC}[/underline]",
            title="Radar Status"
        ))

        # Show Top Deals
        deals = session.exec(select(Deal).where(Deal.status == "active").order_by(Deal.deal_score.desc()).limit(10)).all()
        if deals:
            table = Table(title="🎯 今日高評分 Deals (Top 10)")
            table.add_column("航線", style="cyan")
            table.add_column("日期區間", style="white")
            table.add_column("天數", justify="center")
            table.add_column("航空公司", style="yellow")
            table.add_column("票價 (TWD)", justify="right", style="bold green")
            table.add_column("降幅", justify="right", style="bold green")
            table.add_column("Score", justify="center", style="bold magenta")
            table.add_column("等級", style="red")

            for d in deals:
                table.add_row(
                    f"{d.origin} ➔ {d.destination}",
                    f"{d.depart_date} ~ {d.return_date}",
                    f"{d.duration_days}天",
                    d.airline,
                    f"NT${d.price_twd:,}",
                    f"↓{d.drop_pct}%",
                    str(d.deal_score),
                    d.deal_level
                )
            console.print(table)
        else:
            console.print("[dim]目前尚無已儲存的 Deals。請執行 'python main.py loop' 或 'python main.py scan' 進行掃描。[/dim]")

def cmd_scan(iterations: int = 3):
    init_db()
    console.print(f"[bold cyan]Starting single batch scan ({iterations} tasks)...[/bold cyan]")
    scheduler = RadarScheduler()
    scheduler.run_loop(max_iterations=iterations)
    console.print("[bold green]✓ Batch scan completed.[/bold green]")

def cmd_loop():
    init_db()
    console.print("[bold green]Starting AI Flight Radar Autonomous Loop (Ctrl+C to stop)...[/bold green]")
    scheduler = RadarScheduler()
    try:
        scheduler.run_loop()
    except KeyboardInterrupt:
        console.print("\n[yellow]Radar loop stopped gracefully.[/yellow]")

def cmd_server():
    init_db()
    console.print(f"[bold green]Starting Web Server at http://{settings.API_HOST}:{settings.API_PORT} ...[/bold green]")
    uvicorn.run("api.app:app", host=settings.API_HOST, port=settings.API_PORT, reload=False)

def cmd_nlp(query: str):
    console.print(f"[bold cyan]Query:[/bold cyan] {query}")
    intent = NLPIntentParser.parse(query)
    console.print(Panel(intent.summary_text, title="AI Parsed Intent"))

def main():
    parser = argparse.ArgumentParser(description="AI Flight Radar CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("init", help="Initialize DB and seed tasks")
    subparsers.add_parser("status", help="Show system status and top deals")
    
    scan_parser = subparsers.add_parser("scan", help="Run batch scan tasks")
    scan_parser.add_argument("--count", type=int, default=3, help="Number of tasks to scan")
    
    subparsers.add_parser("loop", help="Run continuous autonomous tracking loop")
    subparsers.add_parser("server", help="Start FastAPI Web Dashboard")
    
    nlp_parser_cmd = subparsers.add_parser("nlp", help="Parse natural language search query")
    nlp_parser_cmd.add_argument("query", type=str, help="Search query text")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init()
    elif args.command == "status":
        cmd_status()
    elif args.command == "scan":
        cmd_scan(args.count)
    elif args.command == "loop":
        cmd_loop()
    elif args.command == "server":
        cmd_server()
    elif args.command == "nlp":
        cmd_nlp(args.query)
    else:
        cmd_status()

if __name__ == "__main__":
    main()
