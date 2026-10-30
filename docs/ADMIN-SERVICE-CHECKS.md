# Administrator service checks

Administration includes account search/filtering, patient/doctor access activation, doctor approval and revocation, appointment oversight, and operational activity history.

Service checks require administrator access and are rate limited. Opening the page sends no diagnostic email or AI request.

- Email: explicitly submits a harmless test to the signed-in administrator’s registered email. Provider acceptance does not prove inbox delivery; check inbox/spam. No password-reset token is generated.
- AI: sends a minimal test prompt with no patient data.
- WhatsApp: validates required saved settings only. Does not verify provider authentication or delivery, and sends no message. Manual report sharing remains available without Twilio.
- Video: validates saved ICE JSON and reports direct/STUN/TURN configuration. The separate camera/microphone preview stays local; stop it when finished. Neither check proves a complete call. Verify an accepted appointment on two devices and different networks.

Setup panels explain which settings to change in the hosting environment; they are not credential editors. Change keys privately in hosting, restart the application, refresh status and repeat the relevant check. Invalid Groq credentials and malformed ICE JSON require valid replacement configuration.
