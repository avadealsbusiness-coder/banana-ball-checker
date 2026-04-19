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
EMAIL_FROM         = os.environ["EMAIL_FROM"]
EMAIL_APP_PASSWORD = os.environ["EMAIL_APP_PASSWORD"]
EMAIL_TO           = os.environ["EMAIL_TO"]
CITIES             = os.environ.get("CITIES", "Savannah, GA,New York City, NY,Denver, CO")

STATUS_FILE = "last_status.json"


def check_waitlists(cities_str):
    """Ask Claude to check the current waitlist status for each city."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    today = datetime.now().strftime("%B %d, %Y")

    prompt = (
        "You are a Savannah Bananas ticket monitor assistant. Today's date is " + today + ".\n\n"
        "The user wants to monitor waitlists/lotteries for Banana Ball games in these cities: " + cities_str + ".\n\n"
        "Based on what you know about the Savannah Bananas 2026/2027 tour and their ticketing system:\n"
        "1. For each city listed, give the current ticket status:\n"
        "   - open     = lottery or waitlist is currently accepting signups RIGHT NOW\n"
        "   - waitlist = primary lottery closed but a waitlist is still open\n"
        "   - closed   = no active signup opportunity at this time\n"
        "   - unknown  = cannot determine current status\n"
        "2. Give a short 1-2 sentence summary per city.\n"
        "3. Give an overall summary (2-3 sentences) of the current ticketing situation.\n"
        "4. List any upcoming important dates or deadlines.\n\n"
        "Respond ONLY with valid JSON, no markdown fences, no preamble:\n"
        "{\"cities\":[{\"city\":\"City Name\",\"status\":\"open|waitlist|closed|unknown\",\"summary\":\"...\"}],"
        "\"overall\":\"...\",\"importantDates\":[\"date and event 1\",\"date and event 2\"]}"
    )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def load_last_status():
    """Load the previous run's status to avoid duplicate emails."""
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_status(result):
    """Save current status so next run can compare."""
    statuses = {c["city"]: c["status"] for c in result["cities"]}
    with open(STATUS_FILE, "w") as f:
        json.dump(statuses, f, indent=2)
    print("Status saved: " + str(statuses))


def send_alert_email(open_cities, result):
    """Send an email alert listing all newly-open cities."""
    city_lines = "\n".join(
        "  - " + c["city"] + " [" + c["status"].upper() + "]: " + c["summary"]
        for c in open_cities
    )
    city_names = ", ".join(c["city"] for c in open_cities)
    subject = "BANANA BALL WAITLIST OPEN -- " + city_names
    overall = result.get("overall", "")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    dates = result.get("importantDates", [])
    if dates:
        dates_lines = "\n".join("  - " + d for d in dates)
        dates_section = "IMPORTANT DATES:\n" + dates_lines + "\n\n"
    else:
        dates_section = ""

    body = (
        "Hi Luke,\n\n"
        "A Savannah Bananas waitlist or lottery has just opened "
        "in one or more of your tracked cities!\n\n"
        "OPEN NOW:\n" + city_lines + "\n\n"
        "OVERALL STATUS:\n" + overall + "\n\n"
        "SIGN UP HERE:\nhttps://thesavannahbananas.com/tickets/\n\n"
        "IMPORTANT REMINDERS:\n"
        "  - The lottery is 100% random -- timing does NOT affect your odds\n"
        "  - Official tickets start at $35 -- only buy from FansFirstTickets.com\n"
        "  - Beware of StubHub, Vivid Seats, and social media scams\n\n"
        + dates_section
        + "Alert sent at " + now_str + " by your Banana Ball Monitor.\n\n"
        "Go Bananas!\n"
        "-- Courtesy of Luke & Claude"
    )

    msg = MIMEMultipart()
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_APP_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

    print("Alert email sent to " + EMAIL_TO)


def main():
    print("=== Banana Ball Checker -- " + datetime.now().strftime("%Y-%m-%d %H:%M UTC") + " ===")
    print("Checking cities: " + CITIES)

    result = check_waitlists(CITIES)
    print("API response: " + json.dumps(result, indent=2))

    last = load_last_status()

    newly_open = []
    for city in result["cities"]:
        current  = city["status"]
        previous = last.get(city["city"], "unknown")
        print("  " + city["city"] + ": " + previous + " -> " + current)
        if current in ("open", "waitlist") and previous not in ("open", "waitlist"):
            newly_open.append(city)

    if newly_open:
        print("NEW openings detected -- sending email...")
        send_alert_email(newly_open, result)
    else:
        print("No new openings. No email sent.")

    save_status(result)
    print("=== Done ===")


if __name__ == "__main__":
    main()
