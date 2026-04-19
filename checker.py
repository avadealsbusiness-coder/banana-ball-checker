"""
Banana Ball Waitlist Checker
Courtesy of Luke & Claude

Runs every 15 minutes via GitHub Actions.
Sends an email alert when any tracked city's waitlist opens.
"""

import os
import json
import smtplib
import anthropic
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── CONFIG (set these as GitHub Secrets) ──────────────────────
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
EMAIL_FROM         = os.environ["EMAIL_FROM"]          # your Gmail address
EMAIL_APP_PASSWORD = os.environ["EMAIL_APP_PASSWORD"]  # Gmail App Password
EMAIL_TO           = os.environ["EMAIL_TO"]            # where to send alerts (can be same as FROM)
CITIES             = os.environ.get("CITIES", "Savannah, GA,New York City, NY,Denver, CO")

STATUS_FILE = "last_status.json"

def check_waitlists(cities_str: str) -> dict:
    """Ask Claude to check the current waitlist status for each city."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    today = datetime.now().strftime("%B %d, %Y")

    prompt = f"""You are a Savannah Bananas ticket monitor assistant. Today's date is {today}.

The user wants to monitor waitlists/lotteries for Banana Ball games in these cities: {cities_str}.

Based on what you know about the Savannah Bananas 2026/2027 tour and their ticketing system:
1. For each city listed, give the current ticket status:
   - "open"     = lottery or waitlist is currently accepting signups RIGHT NOW
   - "waitlist" = primary lottery closed but a waitlist is still open
   - "closed"   = no active signup opportunity at this time
   - "unknown"  = cannot determine current status
2. Give a short 1-2 sentence summary per city.
3. Give an overall summary (2-3 sentences) of the current ticketing situation.
4. List any upcoming important dates or deadlines.

Respond ONLY with valid JSON, no markdown fences, no preamble:
{{
  "cities": [
    {{"city": "City Name", "status": "open|waitlist|closed|unknown", "summary": "..."}}
  ],
  "overall": "...",
  "importantDates": ["date and event 1", "date and event 2"]
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def load_last_status() -> dict:
    """Load the previous run's status from file (to avoid duplicate emails)."""
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_status(result: dict):
    """Save current status so next run can compare."""
    statuses = {c["city"]: c["status"] for c in result["cities"]}
    with open(STATUS_FILE, "w") as f:
        json.dump(statuses, f, indent=2)
    print(f"Status saved: {statuses}")


def send_alert_email(open_cities: list, result: dict):
    """Send an email alert listing all newly-open cities."""
    city_lines = "\n".join(
        f"  • {c['city']} [{c['status'].upper()}]: {c['summary']}"
        for c in open_cities
    )

    subject = f"🍌 BANANA BALL WAITLIST OPEN — {', '.join(c['city'] for c in open_cities)}"

    body = f"""Hi Luke,

A Savannah Bananas waitlist or lottery has just opened in one or more of your tracked cities!

OPEN NOW:
{city_lines}

OVERALL STATUS:
{result.get('overall', '')}

SIGN UP HERE:
https://thesavannahbananas.com/tickets/

IMPORTANT REMINDERS:
  • The lottery is 100% random — timing of signup does NOT affect your odds
  • Official tickets start at $35 — only buy from FansFirstTickets.com
  • Beware of StubHub, Vivid Seats, and social media ticket scams

{('IMPORTANT DATES:\n' + chr(10).join('  • ' + d for d in result.get('importantDates', []))) if result.get('importantDates') else ''}

This alert was sent at {datetime.now().strftime("%Y-%m-%d %H:%M UTC")} by your Banana Ball Monitor.

Go Bananas! 🍌⚾
— Courtesy of Luke & Claude
"""

    msg = MIMEMultipart()
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_APP_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

    print(f"Alert email sent to {EMAIL_TO} for: {[c['city'] for c in open_cities]}")


def main():
    print(f"=== Banana Ball Checker — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')} ===")
    print(f"Checking cities: {CITIES}")

    # 1. Check current status
    result = check_waitlists(CITIES)
    print(f"API response: {json.dumps(result, indent=2)}")

    # 2. Load last known status
    last = load_last_status()

    # 3. Find cities that are newly open (status changed to open/waitlist)
    newly_open = []
    for city in result["cities"]:
        current = city["status"]
        previous = last.get(city["city"], "unknown")
        print(f"  {city['city']}: {previous} → {current}")
        if current in ("open", "waitlist") and previous not in ("open", "waitlist"):
            newly_open.append(city)

    # 4. Send alert if anything newly opened
    if newly_open:
        print(f"NEW openings detected: {[c['city'] for c in newly_open]} — sending email...")
        send_alert_email(newly_open, result)
    else:
        print("No new openings. No email sent.")

    # 5. Save current status for next run
    save_status(result)
    print("=== Done ===")


if __name__ == "__main__":
    main()
