"""Standalone frozen HTML and CSV; escaped evidence and visible chart gaps."""
import csv
import io
import json
from html import escape
from decimal import Decimal

def chart_svg(report):
    rows=report["sessions"]
    values=[Decimal(str(r[k])) for r in rows for k in ("equity_minor","spy_equity_minor") if r.get(k) is not None]
    if not values:
        return '<p>No observed equity curve yet.</p>'
    initial=Decimal(report["initial_capital_minor"])
    lo,hi=min(values+[initial]),max(values+[initial])
    spread=hi-lo or Decimal(100)
    lo-=spread/10
    spread*=Decimal("1.2")
    paths=[]
    for field,color,label in (("equity_minor","#2563eb","Paper account"),("spy_equity_minor","#c2410c","SPY total return")):
        segment=[]
        for i,row in enumerate(rows):
            value=row.get(field)
            if value is None or not row.get("covered"):
                if segment:
                    paths.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{" ".join(segment)}"/>')
                segment=[]
                continue
            x=40+700*i/max(1,len(rows)-1)
            y=220-float((Decimal(str(value))-lo)/spread)*180
            segment.append(f"{x:.2f},{y:.2f}")
            paths.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="{color}"><title>{escape(row["session_date"])}: {label} {escape(str(value))} cents</title></circle>')
        if segment:
            paths.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{" ".join(segment)}"/>')
    return '<svg viewBox="0 0 780 260" role="img" aria-label="Account and SPY equity; gaps are not connected"><path d="M40 30V230H750" fill="none" stroke="#999"/>'+''.join(paths)+'</svg>'

def export_report(report,format):
    if format=="csv":
        columns=("session_date","cutoff_ns","covered","equity_minor","ledger_equity_minor","spy_equity_minor",
                 "completed_trades","commission_minor","fees_minor","posted_borrow_minor","unposted_borrow_minor",
                 "reasons","report_id","run_id","fixed_10_status","fixed_20_status","covered_10_status","covered_20_status")
        out=io.StringIO(newline="")
        writer=csv.DictWriter(out,fieldnames=columns,lineterminator="\r\n")
        writer.writeheader()
        for row in report["sessions"]:
            values={**row,**row.get("costs",{}),"reasons":";".join(row.get("reasons",[])),
                    "report_id":report["report_id"],"run_id":report["run_id"],
                    **{key+"_status":value["status"] for key,value in report["milestones"].items()}}
            safe={}
            for key in columns:
                value=values.get(key)
                if isinstance(value,str) and value.startswith(("=","+","-","@")):
                    # Keep genuine numeric negatives numeric; protect spreadsheet text.
                    try: Decimal(value)
                    except Exception: value="'"+value
                safe[key]=value
            writer.writerow(safe)
        return "text/csv; charset=utf-8",out.getvalue()
    if format!="html":
        raise ValueError("PERFORMANCE_EXPORT_FORMAT_INVALID")
    def text(value):
        return escape(str(value if value is not None else "Unavailable"))
    milestones="".join("<tr><th>"+text(v["clock"])+" day "+str(v["day"])+"</th><td>"+text(v["session_date"])+
        "</td><td>"+text(v["status"])+"</td><td>"+text(", ".join(v["reasons"]))+"<br>"+text("; ".join(k+": "+("Unavailable" if value is None else "Yes" if value else "No") for k,value in v["conditions"].items()))+"</td></tr>" for v in report["milestones"].values())
    daily="".join("<tr><th>"+text(r["session_date"])+"</th><td>"+text(r.get("equity_minor"))+
        "</td><td>"+text(r.get("spy_equity_minor"))+"</td><td>"+text(r["completed_trades"])+
        "</td><td>"+text(r["covered"])+"</td><td>"+text(", ".join(r.get("reasons",[])+r.get("coverage",{}).get("reasons",[])))+"</td></tr>"
        for r in report["sessions"])
    body='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Paper evaluation report</title>'
    body+='<style>body{font:16px system-ui;margin:2rem auto;max-width:1000px;padding:0 1rem;color:#172033}table{border-collapse:collapse;width:100%;margin:1rem 0}th,td{border:1px solid #ccd2dc;padding:.5rem;text-align:left}svg{width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>'
    body+=('<h1>Paper evaluation report</h1><p>Frozen report '+text(report["report_id"])+'</p><p>Run '+text(report["run_id"])+
        ' · Experiment '+text(report["experiment_id"])+'</p><p>Starting capital: '+text(report["initial_capital_minor"])+' USD cents. All curve values are USD cents.</p>')
    body+='<h2>Milestones</h2><table><thead><tr><th>Clock</th><th>Session</th><th>Result</th><th>Reasons</th></tr></thead><tbody>'+milestones+'</tbody></table>'
    body+='<h2>Equity curve</h2><p>Blue: Paper account. Orange: SPY total return. Missing coverage is shown as a gap.</p>'+chart_svg(report)
    body+='<h2>Daily values</h2><table><thead><tr><th>Session</th><th>Net account value</th><th>SPY value</th><th>Completed trades</th><th>Covered</th><th>Reasons</th></tr></thead><tbody>'+daily+'</tbody></table>'
    body+='<h2>Assumptions</h2><ul>'+''.join('<li>'+text(a)+'</li>' for a in report["assumptions"])+'</ul>'
    body+='<h2>Frozen data and cost breakdown</h2><pre>'+text(json.dumps(report,sort_keys=True,indent=2))+'</pre></html>'
    return "text/html; charset=utf-8",body
