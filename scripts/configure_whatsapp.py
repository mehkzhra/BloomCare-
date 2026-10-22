"""Configure the server's opt-in assessment-alert integration; never sends a message."""

import argparse
import re
from getpass import getpass

from configure_integrations import write_values


def main():
    parser = argparse.ArgumentParser(
        description="Configure Twilio WhatsApp care alerts"
    )
    parser.add_argument("--disable", action="store_true")
    args = parser.parse_args()
    if args.disable:
        write_values({"TWILIO_ALLOWED_RECIPIENTS": ""})
        print("WhatsApp alerts disabled. Restart the backend.")
        return
    account = getpass("Twilio Account SID (hidden): ").strip()
    token = getpass("Twilio Auth Token (hidden): ").strip()
    sender = input("Approved sender number, including +country code: ").strip()
    recipients = [
        value.strip()
        for value in input(
            "Opted-in approved recipient numbers, comma separated: "
        ).split(",")
        if value.strip()
    ]
    template = input(
        "Approved Content SID (HX...; blank for sandbox/active-session messages): "
    ).strip()
    number = r"\+[1-9][0-9]{7,14}"
    if not re.fullmatch(r"AC[0-9a-fA-F]{32}", account) or not token:
        raise SystemExit("Enter a valid Account SID and non-empty Auth Token.")
    if (
        not re.fullmatch(number, sender)
        or not recipients
        or any(not re.fullmatch(number, value) for value in recipients)
    ):
        raise SystemExit(
            "Use E.164 numbers such as +15555550100; recipients must have opted in."
        )
    if template and not re.fullmatch(r"HX[0-9a-fA-F]{32}", template):
        raise SystemExit(
            "The Content SID must start HX and contain 32 hexadecimal characters."
        )
    write_values(
        {
            "TWILIO_ACCOUNT_SID": account,
            "TWILIO_AUTH_TOKEN": token,
            "TWILIO_WHATSAPP_FROM": "whatsapp:" + sender,
            "TWILIO_ALLOWED_RECIPIENTS": ",".join(dict.fromkeys(recipients)),
            "TWILIO_CONTENT_SID": template or None,
        }
    )
    print("WhatsApp settings saved. Restart the backend.")
    print(
        "An approved template is required outside the WhatsApp customer-service window."
    )
    print("For the sandbox, each recipient must join it first. No test alert was sent.")
    print("Sandbox: leave Content SID blank and send within 24 hours of the join message.")
    print("Custom templates require a registered WhatsApp sender, not the sandbox number.")


if __name__ == "__main__":
    main()
