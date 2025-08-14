
import os, random, string

def random_code(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))

def age_group(age: int) -> str:
    if age <= 9: return "7-9"
    if age <= 12: return "10-12"
    if age <= 15: return "13-15"
    if age <= 18: return "16-18"
    return "18+"

def ensure_dirs():
    for p in ["/data", "/data/avatars", "/data/drills"]:
        try:
            os.makedirs(p, exist_ok=True)
        except Exception:
            pass

def twilio_enabled() -> bool:
    return all([os.environ.get("TWILIO_ACCOUNT_SID"), os.environ.get("TWILIO_AUTH_TOKEN"), os.environ.get("TWILIO_FROM_NUMBER")])

def send_sms(to_number: str, body: str):
    if not twilio_enabled() or not to_number:
        return
    try:
        from twilio.rest import Client
        client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
        client.messages.create(body=body, from_=os.environ["TWILIO_FROM_NUMBER"], to=to_number)
    except Exception:
        pass
