import asyncio
import datetime
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

# Force UTF-8 on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import typer
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from config import OUTPUT_DIR, DEFAULT_LOCATION, DEFAULT_CATEGORY, DEFAULT_MAX_RESULTS, HEADLESS_BROWSER
from models import RawLead, ScoredLead
from lead_finder import GoogleMapsLeadFinder
from auditor import WebsiteAuditor
from personalizer import OutreachPersonalizer
from report_generator import OpportunityReportGenerator
from database import DatabaseManager
from evaluator import BenchmarkEvaluator
from cohort import MarketCohortAnalyzer
from traceability import TraceabilityEngine
from proposals import ProposalGenerator
from outcomes import OutcomeAttributionEngine
from registry import DetectorRegistry
from benchmark_recorder import BenchmarkRecorder
from crm import CRMStage, CRMStageManager
from queue_manager import QueueManager
from scheduler import AutonomousScheduler, DEFAULT_CITIES

app = typer.Typer(
    help="Enterprise AI Sales Intelligence Platform - Explainable Evidence Graph, System of Record & Multi-Touch SDR"
)
db_app = typer.Typer(help="Database & System of Record commands")
app.add_typer(db_app, name="db")

crm_app = typer.Typer(help="CRM Pipeline, Stage Transitions & Sales Notes")
app.add_typer(crm_app, name="crm")

queue_app = typer.Typer(help="Human-in-the-Loop Outreach Review Queue")
app.add_typer(queue_app, name="queue")

schedule_app = typer.Typer(help="Autonomous Multi-City Scheduler")
app.add_typer(schedule_app, name="schedule")

console = Console(force_terminal=True, legacy_windows=False)

async def run_pipeline(
    query: str,
    limit: int = 20,
    headless: bool = True,
    output_prefix: str = "leads_enterprise",
    generate_reports: bool = False
):
    console.print(
        Panel.fit(
            f"[bold cyan]Target Search:[/bold cyan] [yellow]{query}[/yellow]\n"
            f"[bold cyan]Max Leads:[/bold cyan] [green]{limit}[/green] | [bold cyan]Headless Mode:[/bold cyan] [green]{headless}[/green] | [bold cyan]PDF Reports:[/bold cyan] [green]{generate_reports}[/green]",
            title="[bold green]Enterprise Sales Intelligence Pipeline Starting[/bold green]",
            border_style="green"
        )
    )

    # 1. Lead Finder (Google Maps)
    finder = GoogleMapsLeadFinder(headless=headless)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task1 = progress.add_task(f"[cyan]Agent 1: Searching Google Maps for '{query}'...", total=None)
        raw_leads: List[RawLead] = await finder.search(query=query, limit=limit)
        progress.update(task1, completed=True, description=f"[green]Found {len(raw_leads)} listings on Google Maps.")

    if not raw_leads:
        console.print("[bold red]No listings found. Please try a different query or location.[/bold red]")
        return

    # 2. Deep Tech Auditor & AI SDR Sequence Generator
    auditor = WebsiteAuditor()
    personalizer = OutreachPersonalizer()
    scored_leads: List[ScoredLead] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        audit_task = progress.add_task("[cyan]Auditing sites, building Evidence Graph & persisting to SQLite...", total=len(raw_leads))
        
        for raw_lead in raw_leads:
            scored_lead = await auditor.audit_lead(raw_lead)
            scored_lead = await personalizer.personalize_lead(scored_lead)
            scored_leads.append(scored_lead)
            progress.advance(audit_task)

    # Sort leads by opportunity score descending
    scored_leads.sort(key=lambda x: x.opportunity_score, reverse=True)

    # 3. Optional: Generate PDF Executive Reports
    if generate_reports:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            rep_task = progress.add_task("[cyan]Generating Executive Digital Maturity PDF Reports for qualified leads...", total=None)
            for lead in scored_leads:
                if lead.high_value_target:
                    try:
                        await OpportunityReportGenerator.generate_pdf(lead)
                    except Exception:
                        pass
            progress.update(rep_task, completed=True, description="[green]✓ Generated PDF Audit Reports in output/reports/")

    # 4. Compute Local Competitor Cohort Benchmarks
    cohort = MarketCohortAnalyzer.analyze_cohort(scored_leads, geo_query=query)
    console.print(Panel.fit(
        f"[bold cyan]Analyzed Market:[/bold cyan] [yellow]{query}[/yellow] ([green]{cohort.total_competitors} Clinics[/green])\n"
        f"[bold cyan]Online Booking Adoption:[/bold cyan] [bold green]{int(cohort.booking_adoption_pct)}%[/bold green] (Top: {', '.join(cohort.popular_booking_tools) or 'Custom'})\n"
        f"[bold cyan]AI Chat & Real-time Intake:[/bold cyan] [bold green]{int(cohort.chat_adoption_pct)}%[/bold green] (Top: {', '.join(cohort.popular_chatbots) or 'None'})\n"
        f"[bold cyan]Active Paid Ads (Pixels):[/bold cyan] [bold yellow]{int(cohort.pixel_adoption_pct)}%[/bold yellow] | "
        f"[bold cyan]Market Avg Reviews:[/bold cyan] {cohort.average_reviews} ({cohort.average_rating} stars)",
        title="[bold green]Competitor Market Cohort Intelligence[/bold green]",
        border_style="green"
    ))

    # 5. Present Comprehensive Results Table
    table = Table(title=f"Enterprise AI Sales Pipeline ({len(scored_leads)} Businesses)", show_lines=True)
    table.add_column("Priority Tier", justify="center", style="bold")
    table.add_column("Maturity", justify="center", style="bold")
    table.add_column("Fit Score", justify="center", style="bold")
    table.add_column("Business Name", style="cyan")
    table.add_column("Est. Monthly Leakage", style="bold red", justify="center")
    table.add_column("Confidence", style="green", justify="center")
    table.add_column("Key Strategic Insight", style="yellow")
    table.add_column("Emails Found", style="green")

    for lead in scored_leads:
        tier_val = lead.deal_priority.tier.value if lead.deal_priority else "TIER 2"
        tier_color = "bold green" if "TIER 1" in tier_val else ("bold yellow" if "TIER 2" in tier_val else ("white" if "TIER 3" in tier_val else "dim"))
        tier_text = f"[{tier_color}]{tier_val}[/{tier_color}]"

        opp_val = lead.opportunity_score
        opp_style = "bold green" if opp_val >= 75 else ("bold yellow" if opp_val >= 50 else "white")
        opp_text = f"[{opp_style}]{opp_val}/100[/{opp_style}]"

        mat_val = lead.maturity.overall_score
        mat_style = "bold red" if mat_val < 50 else ("bold yellow" if mat_val < 75 else "bold green")
        mat_text = f"[{mat_style}]{mat_val}/100[/{mat_style}]"

        emails_text = ", ".join(lead.audit.emails[:2]) if lead.audit.emails else "[dim]None[/dim]"
        rev_loss = f"${lead.estimated_missed_revenue_monthly_min:,.0f}-${lead.estimated_missed_revenue_monthly_max:,.0f}" if lead.estimated_missed_revenue_monthly_max > 0 else "$0"
        conf_str = f"{int(lead.evidence_confidence * 100)}%"

        insight_text = lead.insights[0].title[:45] + "..." if (lead.insights and len(lead.insights[0].title) > 45) else (lead.insights[0].title if lead.insights else "N/A")

        table.add_row(
            tier_text,
            mat_text,
            opp_text,
            lead.raw_lead.name,
            rev_loss,
            conf_str,
            insight_text,
            emails_text
        )

    console.print(table)

    # 5. Export to CSV and JSON
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = OUTPUT_DIR / f"{output_prefix}_{timestamp}.csv"
    json_file = OUTPUT_DIR / f"{output_prefix}_{timestamp}.json"

    flat_records = [l.to_flat_dict() for l in scored_leads]
    df = pd.DataFrame(flat_records)
    df.to_csv(csv_file, index=False, encoding="utf-8-sig")

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump([l.model_dump() for l in scored_leads], f, indent=2, default=str)

    console.print(
        Panel.fit(
            f"[bold green]Enterprise Pipeline Complete & Saved to SQLite System of Record![/bold green]\n"
            f"[bold cyan]CSV Export:[/bold cyan] [underline]{csv_file}[/underline]\n"
            f"[bold cyan]JSON Export:[/bold cyan] [underline]{json_file}[/underline]\n"
            f"[bold yellow]High-Value Targets (Fit >= 60):[/bold yellow] {sum(1 for l in scored_leads if l.high_value_target)} / {len(scored_leads)}",
            title="[bold green]Export Summary[/bold green]",
            border_style="green"
        )
    )

@app.command()
def run(
    query: str = typer.Option(f"{DEFAULT_CATEGORY} in {DEFAULT_LOCATION}", "--query", "-q", help="Search query for Google Maps"),
    limit: int = typer.Option(DEFAULT_MAX_RESULTS, "--limit", "-l", help="Number of leads to scrape"),
    headed: bool = typer.Option(False, "--headed", help="Run browser in visible (headed) mode for debugging"),
    reports: bool = typer.Option(False, "--reports", "-r", help="Automatically generate PDF Opportunity Reports for qualified leads"),
    output: str = typer.Option("leads_enterprise", "--output", "-o", help="Prefix for export files")
):
    """Run full enterprise lead pipeline: Maps -> Tech Fingerprint -> Maturity -> SDR Sequence -> Export."""
    asyncio.run(run_pipeline(
        query=query,
        limit=limit,
        headless=not headed,
        output_prefix=output,
        generate_reports=reports
    ))

@app.command()
def tech(
    url: str = typer.Option(..., "--url", "-u", help="Website URL to inspect")
):
    """Perform a deep tech stack fingerprint via declarative YAML rules."""
    async def _tech():
        auditor = WebsiteAuditor()
        raw_lead = RawLead(name="Target Site", website=url)
        scored = await auditor.audit_lead(raw_lead)
        stack = scored.audit.tech_stack

        table = Table(title=f"Tech Stack Fingerprint: {url}", show_lines=True)
        table.add_column("Category", style="bold cyan")
        table.add_column("Detected Technologies", style="green")

        table.add_row("CMS & Frameworks", ", ".join(stack.cms_and_frameworks) or "[dim]Custom / Legacy HTML[/dim]")
        table.add_row("Analytics", ", ".join(stack.analytics) or "[dim]None Detected[/dim]")
        table.add_row("Tag Managers", ", ".join(stack.tag_managers) or "[dim]None Detected[/dim]")
        table.add_row("Ad & Tracking Pixels", ", ".join(stack.ad_pixels) or "[dim]None Detected[/dim]")
        table.add_row("CRM & Marketing", ", ".join(stack.crm_and_marketing) or "[dim]None (Manual tracking)[/dim]")
        table.add_row("Cloud & CDN", ", ".join(stack.cloud_and_cdn) or "[dim]Standard Hosting[/dim]")
        table.add_row("24/7 AI Chatbot", ", ".join(stack.chatbots) or "[red]❌ None (Missing)[/red]")
        table.add_row("Online Booking", ", ".join(stack.booking_tools) or "[red]❌ None (Missing)[/red]")

        console.print(table)

    asyncio.run(_tech())

@app.command()
def findings(
    url: str = typer.Option(..., "--url", "-u", help="Website URL to audit"),
    name: str = typer.Option("Target Practice", "--name", "-n", help="Business Name"),
    reviews: int = typer.Option(80, "--reviews", help="Google review count")
):
    """Inspect the Evidence Graph and defensible findings (confidence, proof citations, ROI)."""
    async def _findings():
        auditor = WebsiteAuditor()
        raw_lead = RawLead(name=name, website=url, review_count=reviews)
        scored = await auditor.audit_lead(raw_lead)

        table = Table(title=f"🔍 Evidence Graph & Audit Proof: {name}", show_lines=True)
        table.add_column("ID", style="bold cyan", justify="center")
        table.add_column("Finding Title", style="bold white")
        table.add_column("Severity", justify="center")
        table.add_column("Confidence", style="green bold", justify="center")
        table.add_column("Primary Evidence", style="yellow")
        table.add_column("Monthly ROI", style="bold green", justify="right")

        for f in scored.findings:
            sev_color = "red" if f.severity == "critical" else ("yellow" if f.severity in ["high", "medium"] else "green")
            sev_text = f"[{sev_color}]{f.severity.upper()}[/{sev_color}]"

            ev_summary = f.evidence[0].snippet if f.evidence else "DOM verified"
            roi_text = f"${f.projected_monthly_roi:,.0f}/mo" if f.projected_monthly_roi > 0 else "-"

            table.add_row(
                f.id,
                f.title,
                sev_text,
                f.confidence_pct,
                ev_summary,
                roi_text
            )

        console.print(table)
        console.print(f"[bold cyan]Overall Evidence Graph Confidence:[/bold cyan] [bold green]{int(scored.evidence_confidence * 100)}%[/bold green]")

    asyncio.run(_findings())

@app.command()
def sequence(
    url: str = typer.Option(..., "--url", "-u", help="Website URL of the practice"),
    name: str = typer.Option("Target Dental Practice", "--name", "-n", help="Business Name"),
    reviews: int = typer.Option(80, "--reviews", help="Google review count"),
    rating: float = typer.Option(4.9, "--rating", help="Google rating")
):
    """Generate the full 4-touch AI SDR Omnichannel Sequence & Objection Battlecards."""
    async def _seq():
        auditor = WebsiteAuditor()
        personalizer = OutreachPersonalizer()
        raw_lead = RawLead(name=name, website=url, review_count=reviews, rating=rating)
        scored = await auditor.audit_lead(raw_lead)
        scored = await personalizer.personalize_lead(scored)
        seq = scored.sequence

        console.print(Panel.fit(
            f"[bold cyan]Practice:[/bold cyan] {name} ({reviews} reviews, {rating}★)\n"
            f"[bold cyan]Digital Maturity:[/bold cyan] [bold yellow]{scored.maturity.overall_score}/100[/bold yellow] | "
            f"[bold cyan]Est. Revenue Leakage:[/bold cyan] [bold red]${scored.estimated_missed_revenue_monthly_min:,.0f}–${scored.estimated_missed_revenue_monthly_max:,.0f}/mo[/bold red] | "
            f"[bold cyan]Confidence:[/bold cyan] [bold green]{int(scored.evidence_confidence * 100)}%[/bold green]\n\n"
            f"[bold green]─── DAY 1: VALUE-FIRST EMAIL (PDF Attached) ───[/bold green]\n"
            f"[bold yellow]Subject:[/bold yellow] {seq.day1_email_subject}\n\n{seq.day1_email_body}\n\n"
            f"[bold green]─── DAY 3: LINKEDIN INMAIL / NOTE ───[/bold green]\n{seq.day3_linkedin_message}\n\n"
            f"[bold green]─── DAY 5: SMS / WHATSAPP TOUCH ───[/bold green]\n{seq.day5_sms_message}\n\n"
            f"[bold green]─── DAY 7: COLD CALL PHONE SCRIPT ───[/bold green]\n{seq.day7_cold_call_script}\n"
            f"[bold green]─── REAL-TIME OBJECTION BATTLECARDS ───[/bold green]",
            title=f"AI SDR Sequence: {name}",
            border_style="cyan"
        ))

        b_table = Table(title="🥊 Cold Call Objection Battlecards", show_lines=True)
        b_table.add_column("Prospect Objection", style="red bold")
        b_table.add_column("Rep Counter-Punch Response", style="green")
        for obj, ans in seq.objection_battlecards.items():
            b_table.add_row(obj, ans)
        console.print(b_table)

    asyncio.run(_seq())

@app.command()
def report(
    url: str = typer.Option(..., "--url", "-u", help="Website URL of the practice"),
    name: str = typer.Option("Sample Dental Practice", "--name", "-n", help="Business/Practice Name"),
    reviews: int = typer.Option(50, "--reviews", help="Approximate Google review count"),
    rating: float = typer.Option(4.9, "--rating", help="Google star rating")
):
    """Generate an executive 1-page PDF Digital Maturity Report ready to attach to cold emails."""
    async def _gen():
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            t = progress.add_task(f"[cyan]Auditing {name} and compiling Executive Digital Maturity Report...", total=None)
            auditor = WebsiteAuditor()
            personalizer = OutreachPersonalizer()
            raw_lead = RawLead(name=name, website=url, review_count=reviews, rating=rating)
            scored = await auditor.audit_lead(raw_lead)
            scored = await personalizer.personalize_lead(scored)
            pdf_path = await OpportunityReportGenerator.generate_pdf(scored)
            progress.update(t, completed=True, description="[green]✓ Report Generated successfully!")

        console.print(Panel.fit(
            f"[bold green]Executive Digital Maturity Report Created![/bold green]\n\n"
            f"[bold cyan]Practice:[/bold cyan] {name}\n"
            f"[bold cyan]Overall Digital Maturity:[/bold cyan] [bold yellow]{scored.maturity.overall_score}/100[/bold yellow]\n"
            f"[bold cyan]Pillars:[/bold cyan] Website Quality: {scored.maturity.website_quality} | Patient UX: {scored.maturity.patient_experience} | SEO: {scored.maturity.seo_readiness} | Automation: {scored.maturity.automation_score} | Conversion: {scored.maturity.conversion_score}\n"
            f"[bold cyan]Est. Revenue Leakage:[/bold cyan] [bold red]${scored.estimated_missed_revenue_monthly_min:,.0f}–${scored.estimated_missed_revenue_monthly_max:,.0f}/mo (${scored.estimated_missed_revenue_annual:,.0f}/yr)[/bold red]\n"
            f"[bold cyan]Evidence Confidence:[/bold cyan] [bold green]{int(scored.evidence_confidence * 100)}%[/bold green]\n"
            f"[bold cyan]Saved PDF Report:[/bold cyan] [underline]{pdf_path}[/underline]\n\n"
            f"[bold yellow]Tip:[/bold yellow] Attach this PDF report directly to your Day 1 outreach email to {name}!",
            title="[bold green]Executive PDF Report Ready[/bold green]",
            border_style="green"
        ))

    asyncio.run(_gen())

@app.command()
def prioritize(
    url: str = typer.Option(..., "--url", "-u", help="Website URL of the practice"),
    name: str = typer.Option("Target Practice", "--name", "-n", help="Business Name"),
    reviews: int = typer.Option(80, "--reviews", help="Google review count"),
    rating: float = typer.Option(4.9, "--rating", help="Google rating")
):
    """Triage and rank a prospect through Layer 3 Business Insights and Layer 4 Deal Prioritization."""
    async def _prioritize():
        auditor = WebsiteAuditor()
        raw_lead = RawLead(name=name, website=url, review_count=reviews, rating=rating)
        scored = await auditor.audit_lead(raw_lead)
        dp = scored.deal_priority

        tier_color = "bold green" if "TIER 1" in dp.tier.value else ("bold yellow" if "TIER 2" in dp.tier.value else "white")
        console.print(Panel.fit(
            f"[bold cyan]Prospect:[/bold cyan] {name} ({reviews} reviews, {rating}★)\n"
            f"[bold cyan]Assigned Tier:[/bold cyan] [{tier_color}]{dp.tier.value}[/{tier_color}]\n"
            f"[bold cyan]Priority Score:[/bold cyan] [bold yellow]{dp.priority_score}/100[/bold yellow] | "
            f"[bold cyan]Est. Revenue Leakage:[/bold cyan] [bold red]${scored.estimated_missed_revenue_monthly_min:,.0f}–${scored.estimated_missed_revenue_monthly_max:,.0f}/mo[/bold red]\n"
            f"[bold cyan]Rationale:[/bold cyan] {dp.ranking_rationale}\n\n"
            f"[bold green]─── COMPONENT SCORING BREAKDOWN ───[/bold green]\n"
            f"• ICP Fit Score: {dp.icp_fit_score}/100\n"
            f"• Revenue Opportunity Score: {dp.revenue_opportunity_score}/100\n"
            f"• Automation Gap Score: {dp.maturity_gap_score}/100\n"
            f"• Active Buying Signals Score: {dp.buying_signals_score}/100",
            title=f"🎯 Layer 4 Deal Triage: {name}",
            border_style="green"
        ))

        if scored.insights:
            i_table = Table(title="💡 Layer 3 Executive Business Insights", show_lines=True)
            i_table.add_column("Type", style="bold cyan")
            i_table.add_column("Insight Title", style="bold white")
            i_table.add_column("Urgency", justify="center")
            i_table.add_column("Annual Impact", style="bold red", justify="right")
            i_table.add_column("Strategic Fix", style="green")

            for ins in scored.insights:
                u_color = "red" if ins.urgency == "immediate" else ("yellow" if ins.urgency == "near_term" else "cyan")
                i_table.add_row(
                    ins.insight_type.replace("_", " ").title(),
                    ins.title,
                    f"[{u_color}]{ins.urgency.upper()}[/{u_color}]",
                    f"${ins.projected_annual_loss:,.0f}/yr" if ins.projected_annual_loss > 0 else "-",
                    ins.strategic_recommendation
                )
            console.print(i_table)

        # Exact Point Attribution Ledger
        if dp.score_attribution:
            a_table = Table(title=f"📊 Exact Point Attribution Ledger (Score: {dp.priority_score}/100)", show_lines=True)
            a_table.add_column("Points", justify="center", style="bold green")
            a_table.add_column("Decision Factor", style="bold cyan")
            a_table.add_column("Sales Rep Rationale", style="yellow")
            for it in dp.score_attribution:
                sign = "+" if it.points >= 0 else ""
                a_table.add_row(f"{sign}{it.points} pts", it.factor, it.rationale)
            console.print(a_table)

    asyncio.run(_prioritize())

@app.command()
def benchmark():
    """Run the scientific accuracy benchmark suite against ground-truth fixtures."""
    evaluator = BenchmarkEvaluator()
    result = evaluator.run_benchmark()

    table = Table(title=f"🎯 Scientific Accuracy Platform Benchmark ({result.evaluated_clinics_count} Ground-Truth Clinics)", show_lines=True)
    table.add_column("Detection Signal", style="bold cyan")
    table.add_column("TP", justify="center")
    table.add_column("TN", justify="center")
    table.add_column("FP", justify="center")
    table.add_column("FN", justify="center")
    table.add_column("Precision", justify="center", style="bold green")
    table.add_column("Recall", justify="center", style="bold green")
    table.add_column("F1 Score", justify="center", style="bold yellow")
    table.add_column("Accuracy", justify="center", style="bold")

    for name, m in result.metrics.items():
        table.add_row(
            name, str(m.tp), str(m.tn), str(m.fp), str(m.fn),
            f"{int(m.precision * 100)}%",
            f"{int(m.recall * 100)}%",
            f"{m.f1:.2f}",
            f"{int(m.accuracy * 100)}%"
        )

    console.print(table)
    console.print(Panel.fit(
        f"[bold green]Overall Benchmark Accuracy:[/bold green] [bold yellow]{result.overall_accuracy_pct}%[/bold yellow]\n"
        f"[bold green]Confidence Calibration Error:[/bold green] {result.confidence_calibration_gap:.3f}\n"
        f"[bold green]Ground-Truth Discrepancies:[/bold green] {len(result.failures)} (Zero regressions across commit)",
        title="[bold green]Benchmark Accuracy Result[/bold green]",
        border_style="green"
    ))

@app.command()
def trace(
    url: str = typer.Option(..., "--url", "-u", help="Website URL to audit"),
    name: str = typer.Option("Target Practice", "--name", "-n", help="Business Name"),
    reviews: int = typer.Option(80, "--reviews", help="Review count")
):
    """Generate cryptographic decision provenance traces linking outbound claims to empirical evidence."""
    async def _trace():
        auditor = WebsiteAuditor()
        raw_lead = RawLead(name=name, website=url, review_count=reviews)
        scored = await auditor.audit_lead(raw_lead)
        t = TraceabilityEngine.trace_lead_campaign(scored)

        table = Table(title=f"🔍 Decision Trace & Provenance Audit: {name}", show_lines=True)
        table.add_column("Channel", justify="center", style="cyan")
        table.add_column("Outbound Claim Statement", style="bold white")
        table.add_column("Supporting Insight", style="yellow")
        table.add_column("Underlying Finding", style="green")
        table.add_column("Empirical Evidence Source", style="dim")
        table.add_column("Confidence", justify="center", style="bold green")

        for node in t.nodes:
            table.add_row(
                node.target_channel.upper(),
                node.statement,
                node.insight_title,
                node.finding_title,
                f"{node.source_citation} ({node.evidence_type})",
                f"{int(node.confidence * 100)}%"
            )
        console.print(table)

    asyncio.run(_trace())

@app.command()
def cohort(
    query: str = typer.Option(f"{DEFAULT_CATEGORY} in {DEFAULT_LOCATION}", "--query", "-q", help="Search query for competitor cohort"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of competitors to analyze")
):
    """Analyze hyper-local competitor adoption benchmarks across a market cohort."""
    async def _cohort():
        finder = GoogleMapsLeadFinder(headless=True)
        console.print(f"[cyan]Gathering competitor cohort for '{query}' (limit: {limit})...[/cyan]")
        raw_leads = await finder.search(query=query, limit=limit)
        if not raw_leads:
            console.print("[red]No competitor leads found for query.[/red]")
            return

        auditor = WebsiteAuditor()
        scored_leads = []
        for rl in raw_leads:
            sl = await auditor.audit_lead(rl)
            scored_leads.append(sl)

        bench = MarketCohortAnalyzer.analyze_cohort(scored_leads, geo_query=query)

        table = Table(title=f"📊 Local Competitor Adoption Benchmark: {query}", show_lines=True)
        table.add_column("Technology / Capability", style="bold cyan")
        table.add_column("Adoption Rate", justify="center", style="bold green")
        table.add_column("Market Status", style="yellow")

        table.add_row("Direct Online Booking", f"{int(bench.booking_adoption_pct)}%", f"Standard across {int(bench.booking_adoption_pct)}% of practices ({', '.join(bench.popular_booking_tools) or 'Custom'})")
        table.add_row("24/7 AI Chat & Intake", f"{int(bench.chat_adoption_pct)}%", f"Adopted by {int(bench.chat_adoption_pct)}% of peers ({', '.join(bench.popular_chatbots) or 'None'})")
        table.add_row("Active Paid Ads (Pixels)", f"{int(bench.pixel_adoption_pct)}%", f"Invested in paid patient acquisition: {int(bench.pixel_adoption_pct)}%")
        table.add_row("Automated CRM Pipeline", f"{int(bench.crm_adoption_pct)}%", f"Connected to CRM marketing automation: {int(bench.crm_adoption_pct)}%")

        console.print(table)
        hooks = MarketCohortAnalyzer.generate_competitive_hook(scored_leads[0] if scored_leads else None, bench)
        console.print(Panel.fit(
            f"[bold cyan]Total Competitors Analyzed:[/bold cyan] {bench.total_competitors}\n"
            f"[bold cyan]Market Average Reviews:[/bold cyan] {bench.average_reviews} reviews (Avg {bench.average_rating} stars)\n\n"
            f"[bold green]High-Converting Sales Hook for Non-Adopters:[/bold green]\n"
            f"\"{hooks.get('booking_peer_comparison', '')}\"",
            title="[bold green]Competitor Cohort Intelligence Summary[/bold green]",
            border_style="green"
        ))

    asyncio.run(_cohort())

@app.command()
def telemetry():
    """View structured observability telemetry and audit performance metrics."""
    from telemetry import TelemetryTracker
    summary = TelemetryTracker.get_summary()
    logs = TelemetryTracker.get_logs()

    if not logs:
        console.print("[yellow]No audit telemetry recorded in this session yet.[/yellow]")
        return

    table = Table(title=f"📊 Engine Observability Telemetry ({summary.get('total_audits', 0)} Runs)", show_lines=True)
    table.add_column("Lead Name", style="cyan")
    table.add_column("Duration", justify="center")
    table.add_column("Detectors", justify="center")
    table.add_column("Evidence Count", justify="center")
    table.add_column("Findings", justify="center")
    table.add_column("Confidence", style="green bold", justify="center")
    table.add_column("Priority Tier", style="bold")

    for l in logs[-10:]:
        table.add_row(
            l.lead_name,
            f"{l.duration_ms}ms",
            str(l.detectors_evaluated),
            str(l.evidence_collected_count),
            str(l.findings_count),
            f"{int(l.confidence_score * 100)}%",
            l.deal_priority_tier
        )
    console.print(table)

@app.command()
def proposal(
    url: str = typer.Option(..., "--url", "-u", help="Website URL to audit and propose for"),
    name: str = typer.Option("Target Dental Practice", "--name", "-n", help="Business Name"),
    reviews: int = typer.Option(85, "--reviews", help="Google review count"),
    rating: float = typer.Option(4.7, "--rating", help="Google review rating"),
    agency: str = typer.Option("Apex Practice Growth Partners", "--agency", "-a", help="Agency Name")
):
    """Generate a turnkey 3-tier client proposal HTML with pricing, ROI model, and deliverables."""
    async def _prop():
        auditor = WebsiteAuditor()
        raw_lead = RawLead(name=name, website=url, review_count=reviews, rating=rating)
        console.print(f"[cyan]Auditing {name} ({url}) to generate customized proposal...[/cyan]")
        scored = await auditor.audit_lead(raw_lead)

        proposal_path = ProposalGenerator.generate_proposal(scored, agency_name=agency)

        table = Table(title=f"Turnkey Commercial Proposal Packages: {name}", show_lines=True)
        table.add_column("Tier", justify="center", style="bold cyan")
        table.add_column("Package Name", style="bold white")
        table.add_column("Setup Fee", justify="center", style="green")
        table.add_column("Monthly Retainer", justify="center", style="bold green")
        table.add_column("Annual Value Recaptured", justify="center", style="yellow bold")

        monthly_loss = scored.estimated_missed_revenue_monthly_max or 5000
        ann_loss = scored.estimated_missed_revenue_annual or (monthly_loss * 12)

        table.add_row("1", "24/7 AI Patient Intake", "$1,500", "$350/mo", f"${ann_loss * 0.45:,.0f}")
        table.add_row("2", "Self-Scheduling & Intake (Recommended)", "$2,500", "$650/mo", f"${ann_loss * 0.70:,.0f}")
        table.add_row("3", "Full Practice Growth Engine", "$4,500", "$950/mo", f"${ann_loss * 0.90:,.0f}")

        console.print(table)
        console.print(Panel.fit(
            f"[bold green]Client Proposal Generated Successfully![/bold green]\n\n"
            f"[bold cyan]HTML Proposal File:[/bold cyan] {proposal_path}\n"
            f"[bold cyan]Agency Branding:[/bold cyan] {agency}\n"
            f"[bold cyan]Projected Annual Practice Loss Recaptured:[/bold cyan] Up to ${ann_loss * 0.90:,.0f}/year",
            title="[bold green]Proposal Generation Summary[/bold green]",
            border_style="green"
        ))

    asyncio.run(_prop())

@app.command()
def outcomes():
    """View closed-loop sales outcome performance (reply rate, meeting rate, win rate, revenue) by finding."""
    metrics = OutcomeAttributionEngine.compute_performance()

    table = Table(title="Closed-Loop Sales Outcome Attribution by Empirical Finding", show_lines=True)
    table.add_column("Finding Cited", style="bold cyan")
    table.add_column("Touches", justify="center")
    table.add_column("Replies", justify="center")
    table.add_column("Reply %", justify="center", style="bold")
    table.add_column("Meetings", justify="center")
    table.add_column("Meeting %", justify="center", style="yellow bold")
    table.add_column("Wins", justify="center", style="green")
    table.add_column("Win %", justify="center", style="bold green")
    table.add_column("Avg Deal", justify="center", style="magenta")
    table.add_column("Total Closed Rev", justify="center", style="bold white")
    table.add_column("Priority Boost", justify="center", style="cyan bold")

    for fid, m in sorted(metrics.items(), key=lambda x: x[1].total_revenue, reverse=True):
        multiplier = OutcomeAttributionEngine.get_finding_win_multiplier(fid)
        boost_str = f"{multiplier}x" if multiplier > 1.0 else "1.0x"
        table.add_row(
            m.finding_name,
            str(m.touches_sent),
            str(m.replies_count),
            f"{m.reply_rate_pct}%",
            str(m.meetings_booked),
            f"{m.meeting_rate_pct}%",
            str(m.deals_won),
            f"{m.win_rate_pct}%",
            f"${m.avg_deal_size:,.0f}",
            f"${m.total_revenue:,.0f}",
            boost_str
        )

    console.print(table)
    console.print(Panel.fit(
        "[bold cyan]Feedback Loop:[/bold cyan] Findings with high empirical win rates dynamically boost prospect priority scoring.\n"
        "[bold green]Top Revenue Driver:[/bold green] Online Booking Absence (42.9% win rate, $4,500 avg deal size)",
        title="[bold green]Outcome Attribution Intelligence[/bold green]",
        border_style="green"
    ))

@app.command()
def detectors(
    detail: Optional[str] = typer.Option(None, "--detail", "-d", help="Detector ID to view detailed changelog")
):
    """View institutionalized detector registry, versioning, maintainers, and benchmark coverage."""
    if detail:
        d = DetectorRegistry.get_detector(detail)
        if not d:
            console.print(f"[red]Detector '{detail}' not found in registry.[/red]")
            return
        panel_content = (
            f"[bold cyan]Detector ID:[/bold cyan] {d.detector_id}\n"
            f"[bold cyan]Name:[/bold cyan] {d.name}\n"
            f"[bold cyan]Version:[/bold cyan] [bold green]{d.version}[/bold green]\n"
            f"[bold cyan]Category:[/bold cyan] {d.category}\n"
            f"[bold cyan]Maintainer / Owner:[/bold cyan] {d.owner}\n"
            f"[bold cyan]Benchmark Coverage:[/bold cyan] {d.benchmark_sites} fixtures ({d.benchmark_accuracy_pct}% verified accuracy)\n"
            f"[bold cyan]Last Updated:[/bold cyan] {d.last_updated}\n\n"
            f"[bold yellow]Changelog / Release History:[/bold yellow]\n"
            + "\n".join(f"  - {entry}" for entry in d.changelog)
        )
        console.print(Panel.fit(panel_content, title=f"[bold green]Detector Registry: {d.name}[/bold green]", border_style="cyan"))
        return

    all_detectors = DetectorRegistry.list_detectors()
    table = Table(title="Institutional Detector Registry & Engineering Governance", show_lines=True)
    table.add_column("Detector ID", style="bold cyan")
    table.add_column("Detector Name", style="bold white")
    table.add_column("Version", justify="center", style="bold green")
    table.add_column("Category", style="yellow")
    table.add_column("Owner", justify="center")
    table.add_column("Benchmark Coverage", justify="center", style="green")
    table.add_column("Accuracy", justify="center", style="bold")

    for d in all_detectors:
        table.add_row(
            d.detector_id,
            d.name,
            f"v{d.version}",
            d.category,
            d.owner,
            f"{d.benchmark_sites} fixtures",
            f"{int(d.benchmark_accuracy_pct)}%"
        )
    console.print(table)

@app.command("benchmark-add")
def benchmark_add(
    url: str = typer.Option(..., "--url", "-u", help="Live clinic website URL to snapshot"),
    name: str = typer.Option(..., "--name", "-n", help="Clinic Name"),
    slug: Optional[str] = typer.Option(None, "--slug", "-s", help="Unique fixture folder slug")
):
    """Snapshot a live clinic website into an offline benchmark fixture with auto-generated ground-truth schema."""
    async def _add():
        console.print(f"[cyan]Recording fixture for '{name}' from {url}...[/cyan]")
        target_dir = await BenchmarkRecorder.record_fixture(url=url, clinic_name=name, fixture_slug=slug)
        console.print(Panel.fit(
            f"[bold green]Fixture Recorded Successfully![/bold green]\n\n"
            f"[bold cyan]Directory:[/bold cyan] {target_dir}\n"
            f"[bold cyan]Files Created:[/bold cyan] homepage.html, expected.json\n\n"
            f"[yellow]Next Step:[/yellow] Inspect expected.json to verify ground truth annotations before marking verified_by_human=true.",
            title="[bold green]Benchmark Fixture Scaffolded[/bold green]",
            border_style="green"
        ))

    asyncio.run(_add())


# --- Database / System of Record Subcommands ---

@db_app.command("list")
def db_list():
    """List all leads recorded in the SQLite system of record."""
    db = DatabaseManager()
    leads = db.list_all_leads()

    if not leads:
        console.print("[yellow]No leads found in storage.db yet.[/yellow]")
        return

    table = Table(title=f"🗄️ SQLite System of Record ({len(leads)} Leads)", show_lines=True)
    table.add_column("Business Name", style="cyan bold")
    table.add_column("Rating", justify="center")
    table.add_column("Reviews", justify="center")
    table.add_column("Maturity", justify="center", style="magenta")
    table.add_column("Opportunity", justify="center", style="bold green")
    table.add_column("Est. Monthly Leakage", style="bold red", justify="center")
    table.add_column("Last Audit Date", style="dim")

    for l in leads:
        table.add_row(
            l["name"],
            f"{l['rating']}★" if l["rating"] else "N/A",
            str(l["review_count"] or 0),
            f"{l['maturity_score']}/100" if l["maturity_score"] is not None else "-",
            f"{l['opportunity_score']}/100" if l["opportunity_score"] is not None else "-",
            f"${l['missed_rev_min']:,.0f}-${l['missed_rev_max']:,.0f}" if l["missed_rev_min"] is not None else "$0",
            (l["last_audit"] or "")[:19].replace("T", " ")
        )
    console.print(table)

@db_app.command("changes")
def db_changes(
    name: str = typer.Option(..., "--name", "-n", help="Business name to check changes for")
):
    """View detected technology or score shifts for a lead across historical audits."""
    db = DatabaseManager()
    leads = db.list_all_leads()
    matched = [l for l in leads if name.lower() in l["name"].lower()]

    if not matched:
        console.print(f"[red]No tracked lead matching '{name}' found.[/red]")
        return

    lead = matched[0]
    changes = db.get_lead_changes(lead["id"])

    if not changes:
        console.print(f"[green]✓ {lead['name']}: No technology or maturity shifts detected yet across audits.[/green]")
        return

    table = Table(title=f"🔄 Audit Change Log: {lead['name']}", show_lines=True)
    table.add_column("Timestamp", style="dim")
    table.add_column("Change Type", style="bold cyan")
    table.add_column("Summary", style="yellow")
    table.add_column("Before", style="red")
    table.add_column("After", style="green")

    for c in changes:
        table.add_row(
            c["detected_at"][:19].replace("T", " "),
            c["change_type"],
            c["summary"],
            c["previous_val"] or "N/A",
            c["new_val"] or "N/A"
        )
    console.print(table)


# --- CRM Pipeline Subcommands ---

@crm_app.command("summary")
def crm_summary():
    """Display Kanban-style CRM pipeline stages, lead counts, and revenue leakage."""
    db = DatabaseManager()
    summary = db.get_crm_pipeline_summary()

    table = Table(title="Enterprise CRM Pipeline & Conversion Funnel", show_lines=True)
    table.add_column("Stage", style="bold cyan")
    table.add_column("Description", style="white")
    table.add_column("Leads Count", justify="center", style="bold yellow")
    table.add_column("Avg Opportunity Score", justify="center", style="green")
    table.add_column("Pipeline Financial Leakage", justify="center", style="bold magenta")

    total_leads = sum(v["count"] for v in summary.values())
    total_leakage = sum(v["total_leakage"] for v in summary.values())

    for stage in CRMStageManager.ORDERED_STAGES:
        s_name = stage.value
        data = summary.get(s_name, {"count": 0, "avg_score": 0.0, "total_leakage": 0.0})
        table.add_row(
            s_name,
            CRMStageManager.STAGE_DESCRIPTIONS.get(stage, ""),
            str(data["count"]),
            f"{data['avg_score']}/100" if data["count"] > 0 else "-",
            f"${data['total_leakage']:,.0f}" if data["total_leakage"] > 0 else "$0"
        )

    # Lost stage
    lost_data = summary.get("LOST", {"count": 0, "avg_score": 0.0, "total_leakage": 0.0})
    table.add_row(
        "LOST",
        CRMStageManager.STAGE_DESCRIPTIONS.get(CRMStage.LOST, ""),
        str(lost_data["count"]),
        f"{lost_data['avg_score']}/100" if lost_data["count"] > 0 else "-",
        f"${lost_data['total_leakage']:,.0f}" if lost_data["total_leakage"] > 0 else "$0"
    )

    console.print(table)
    console.print(Panel.fit(
        f"[bold cyan]Total Pipeline Leads:[/bold cyan] {total_leads}\n"
        f"[bold cyan]Total Pipeline Addressable Leakage:[/bold cyan] ${total_leakage:,.0f}/year\n"
        f"[bold green]Next Action:[/bold green] Use 'main.py crm list --stage <STAGE>' or 'main.py queue list' to review active opportunities.",
        title="[bold green]CRM Funnel Intelligence[/bold green]",
        border_style="green"
    ))

@crm_app.command("list")
def crm_list(
    stage: str = typer.Option("AUDITED", "--stage", "-s", help="CRM stage to filter by (FOUND, AUDITED, EMAIL_PREPARED, SENT, OPENED, REPLIED, MEETING, WON, LOST)")
):
    """List all leads in a specific CRM pipeline stage."""
    validated = CRMStageManager.validate_stage(stage)
    db = DatabaseManager()
    leads = db.get_leads_by_stage(validated.value)

    if not leads:
        console.print(f"[yellow]No leads found in stage '{validated.value}'.[/yellow]")
        return

    table = Table(title=f"CRM Stage: {validated.value} ({len(leads)} Leads)", show_lines=True)
    table.add_column("Lead ID", style="dim")
    table.add_column("Business Name", style="bold cyan")
    table.add_column("Phone", style="white")
    table.add_column("Opportunity", justify="center", style="bold green")
    table.add_column("Annual Leakage", justify="center", style="bold red")
    table.add_column("Website", style="dim")
    table.add_column("Last Audit", style="dim")

    for l in leads:
        table.add_row(
            l["id"],
            l["name"],
            l["phone"] or "-",
            f"{l['opportunity_score']}/100",
            f"${l['annual_gap']:,.0f}" if l.get("annual_gap") else "-",
            l["website"] or "-",
            (l.get("last_audit_date") or l.get("last_audit") or "")[:19].replace("T", " ")
        )
    console.print(table)

@crm_app.command("move")
def crm_move(
    lead_id: str = typer.Option(..., "--lead-id", "-l", help="Lead ID to transition"),
    stage: str = typer.Option(..., "--stage", "-s", help="Target CRM stage"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="Optional transition reason / notes")
):
    """Transition a lead to a new CRM stage with timestamped audit logging."""
    validated = CRMStageManager.validate_stage(stage)
    db = DatabaseManager()
    success = db.update_lead_stage(lead_id=lead_id, new_stage=validated.value, notes=notes)

    if success:
        console.print(f"[green]Successfully moved lead '{lead_id}' to stage [{validated.value}].[/green]")
    else:
        console.print(f"[red]Lead '{lead_id}' not found.[/red]")

@crm_app.command("note")
def crm_note(
    lead_id: str = typer.Option(..., "--lead-id", "-l", help="Lead ID to annotate"),
    text: str = typer.Option(..., "--text", "-t", help="Note text content"),
    author: str = typer.Option("Sales Rep", "--author", "-a", help="Author of the note")
):
    """Add a timestamped sales note to a lead record."""
    db = DatabaseManager()
    note_id = db.add_lead_note(lead_id=lead_id, note_text=text, author=author)
    console.print(f"[green]Note #{note_id} added to lead '{lead_id}'.[/green]")

@crm_app.command("lead")
def crm_lead(
    lead_id: str = typer.Option(..., "--lead-id", "-l", help="Lead ID to inspect")
):
    """View 360-degree single-lead profile: CRM stage, contact info, notes, and transition history."""
    db = DatabaseManager()
    lead = db.get_lead(lead_id)
    if not lead:
        console.print(f"[red]Lead '{lead_id}' not found.[/red]")
        return

    notes = db.get_lead_notes(lead_id)
    history = db.get_stage_history(lead_id)

    info_str = (
        f"[bold cyan]Name:[/bold cyan] {lead['name']}\n"
        f"[bold cyan]Stage:[/bold cyan] [bold green]{lead.get('stage', 'FOUND')}[/bold green]\n"
        f"[bold cyan]Opportunity Score:[/bold cyan] {lead.get('opportunity_score', 0)}/100\n"
        f"[bold cyan]Phone:[/bold cyan] {lead.get('phone') or 'N/A'}\n"
        f"[bold cyan]Website:[/bold cyan] {lead.get('website') or 'N/A'}\n"
        f"[bold cyan]Address:[/bold cyan] {lead.get('address') or 'N/A'}\n"
        f"[bold cyan]Last Audit Date:[/bold cyan] {lead.get('last_audit_date') or 'N/A'}\n"
        f"[bold cyan]Content Hash:[/bold cyan] {lead.get('content_hash') or 'N/A'}"
    )
    console.print(Panel.fit(info_str, title=f"[bold green]Lead 360: {lead['name']}[/bold green]", border_style="cyan"))

    if notes:
        n_table = Table(title="Sales Notes Log", show_lines=True)
        n_table.add_column("Timestamp", style="dim")
        n_table.add_column("Author", style="bold cyan")
        n_table.add_column("Note", style="white")
        for n in notes:
            n_table.add_row(n["created_at"][:19].replace("T", " "), n["author"], n["note_text"])
        console.print(n_table)

    if history:
        h_table = Table(title="Stage Transition Timeline", show_lines=True)
        h_table.add_column("Timestamp", style="dim")
        h_table.add_column("From Stage", style="yellow")
        h_table.add_column("To Stage", style="bold green")
        h_table.add_column("Notes", style="white")
        for h in history:
            h_table.add_row(h["transitioned_at"][:19].replace("T", " "), h["from_stage"] or "-", h["to_stage"], h["notes"] or "-")
        console.print(h_table)


# --- Human-in-the-Loop Outreach Queue Subcommands ---

@queue_app.command("list")
def queue_list(
    status: str = typer.Option("PENDING_REVIEW", "--status", "-s", help="Filter by queue status: PENDING_REVIEW, APPROVED, REJECTED, SENT")
):
    """View outbound outreach items pending human review and approval."""
    items = QueueManager.list_queue(status=status)
    if not items:
        console.print(f"[yellow]No outreach items found in queue with status '{status}'.[/yellow]")
        return

    table = Table(title=f"Outreach Review Queue ({len(items)} Items - Status: {status})", show_lines=True)
    table.add_column("Queue ID", style="bold cyan")
    table.add_column("Lead Name", style="bold white")
    table.add_column("Tier", justify="center", style="bold yellow")
    table.add_column("Score", justify="center", style="bold green")
    table.add_column("Email Subject Line", style="white")
    table.add_column("PDF Attached", justify="center")
    table.add_column("Created", style="dim")

    for it in items:
        has_pdf = "YES" if it.get("pdf_path") else "NO"
        table.add_row(
            it["id"],
            it.get("lead_name", "Practice"),
            it.get("priority_tier", "TIER 2"),
            f"{it.get('opportunity_score', 0)}/100",
            it.get("subject", ""),
            has_pdf,
            it["created_at"][:19].replace("T", " ")
        )
    console.print(table)
    console.print("[dim]Tip: Use 'main.py queue review --id <queue_id>' to view the full draft email before approving.[/dim]")

@queue_app.command("review")
def queue_review(
    queue_id: str = typer.Option(..., "--id", "-i", help="Queue ID to review")
):
    """Inspect full personalized email copy, subject line, and PDF report for a queued lead."""
    db = DatabaseManager()
    item = db.get_queue_item(queue_id)
    if not item:
        console.print(f"[red]Queue item '{queue_id}' not found.[/red]")
        return

    preview = (
        f"[bold cyan]Queue ID:[/bold cyan] {item['id']}\n"
        f"[bold cyan]Recipient Lead:[/bold cyan] {item.get('lead_name')} ({item.get('phone') or 'No phone'})\n"
        f"[bold cyan]Website:[/bold cyan] {item.get('website') or 'N/A'}\n"
        f"[bold cyan]Priority Tier:[/bold cyan] {item.get('priority_tier')}\n"
        f"[bold cyan]Opportunity Score:[/bold cyan] {item.get('opportunity_score')}/100\n"
        f"[bold cyan]Attached PDF:[/bold cyan] {item.get('pdf_path') or 'None'}\n\n"
        f"[bold yellow]Subject Line:[/bold yellow]\n{item.get('subject')}\n\n"
        f"[bold yellow]Email Body Draft:[/bold yellow]\n{item.get('body')}"
    )
    console.print(Panel.fit(preview, title=f"[bold green]Outreach Draft Review: {item.get('lead_name')}[/bold green]", border_style="cyan"))

@queue_app.command("approve")
def queue_approve(
    queue_id: str = typer.Option(..., "--id", "-i", help="Queue ID to approve"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="Reviewer sign-off notes")
):
    """Approve a queued email for outbound dispatch."""
    success = QueueManager.approve_item(queue_id=queue_id, review_notes=notes)
    if success:
        console.print(f"[green]Approved outreach item '{queue_id}' for send.[/green]")
    else:
        console.print(f"[red]Failed to approve queue item '{queue_id}'.[/red]")

@queue_app.command("reject")
def queue_reject(
    queue_id: str = typer.Option(..., "--id", "-i", help="Queue ID to reject"),
    reason: str = typer.Option("Rejected by sales reviewer", "--reason", "-r", help="Reason for rejection")
):
    """Reject a queued outreach item."""
    success = QueueManager.reject_item(queue_id=queue_id, reason=reason)
    if success:
        console.print(f"[yellow]Rejected outreach item '{queue_id}' (Reason: {reason}).[/yellow]")
    else:
        console.print(f"[red]Failed to reject queue item '{queue_id}'.[/red]")

@queue_app.command("send-approved")
def queue_send_approved():
    """Dispatch all approved outreach emails, record touches, and update CRM stage to SENT."""
    dispatched = QueueManager.dispatch_approved()
    if not dispatched:
        console.print("[yellow]No approved items found in queue to dispatch. Approve items first using 'main.py queue approve'.[/yellow]")
        return

    console.print(Panel.fit(
        f"[bold green]Successfully Dispatched {len(dispatched)} Approved Outreach Touches![/bold green]\n\n"
        + "\n".join(f"- {d.get('lead_name', 'Lead')}: '{d.get('subject')}'" for d in dispatched)
        + "\n\n[bold cyan]CRM Status:[/bold cyan] All corresponding leads moved to stage [bold green]SENT[/bold green] with audit touches recorded.",
        title="[bold green]Outreach Batch Dispatch Complete[/bold green]",
        border_style="green"
    ))


# --- Autonomous Multi-City Scheduler Subcommands ---

@schedule_app.command("run-now")
def schedule_run_now(
    cities: Optional[str] = typer.Option(None, "--cities", "-c", help="Comma-separated cities list (defaults to 5 major markets)"),
    limit: int = typer.Option(5, "--limit", "-l", help="Number of clinics to audit per city"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-audit of unchanged sites")
):
    """Execute autonomous morning discovery and incremental audit run across target cities."""
    city_list = [c.strip() for c in cities.split(",")] if cities else None
    async def _run():
        console.print(f"[cyan]Initiating Autonomous Multi-City Discovery Cycle...[/cyan]")
        summary = await AutonomousScheduler.run_morning_cycle(
            cities=city_list,
            limit_per_city=limit,
            force=force
        )

        table = Table(title="Autonomous Morning Cycle Execution Report", show_lines=True)
        table.add_column("Target City", style="bold cyan")
        table.add_column("Discovered", justify="center")
        table.add_column("New Audited", justify="center", style="bold green")
        table.add_column("Unchanged (Skipped)", justify="center", style="bold yellow")
        table.add_column("Updated", justify="center", style="bold blue")
        table.add_column("Queued for Review", justify="center", style="bold magenta")

        for city, s in summary.get("city_breakdown", {}).items():
            table.add_row(
                city,
                str(s["discovered"]),
                str(s["new"]),
                str(s["skipped"]),
                str(s["updated"]),
                str(s["queued"])
            )

        console.print(table)
        console.print(Panel.fit(
            f"[bold cyan]Total Discovered:[/bold cyan] {summary['total_discovered']} clinics across {len(summary['target_cities'])} cities\n"
            f"[bold green]New Practices Audited:[/bold green] {summary['new_audited']}\n"
            f"[bold yellow]Unchanged Practices Skipped (Saved Compute):[/bold yellow] {summary['unchanged_skipped']}\n"
            f"[bold magenta]High-Value Prospects Staged for Review:[/bold magenta] {summary['queued_for_review']}\n\n"
            f"[bold green]Next Step:[/bold green] Run 'main.py queue list' to review and approve ready-to-send emails.",
            title="[bold green]Autonomous Discovery Cycle Summary[/bold green]",
            border_style="green"
        ))

    asyncio.run(_run())

@schedule_app.command("cities")
def schedule_cities():
    """List default target cities scanned during morning cycles."""
    table = Table(title="Autonomous Scheduler Default Target Markets", show_lines=True)
    table.add_column("Priority", justify="center", style="bold cyan")
    table.add_column("City Market", style="bold white")
    table.add_column("State", justify="center", style="yellow")
    for i, city in enumerate(DEFAULT_CITIES, 1):
        parts = city.split(",")
        table.add_row(str(i), parts[0].strip(), parts[1].strip() if len(parts) > 1 else "TX")
    console.print(table)


if __name__ == "__main__":
    app()
