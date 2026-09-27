"""Email: надсилання через SMTP (Gmail — app password, або будь-який інший SMTP).

credentials: {smtp_host, smtp_port, smtp_user, smtp_password, from_name?}
Для Gmail: smtp_host=smtp.gmail.com, smtp_port=465, smtp_user=ваша пошта,
smtp_password= пароль застосунку (не звичайний пароль облікового запису).
"""

from email.mime.text import MIMEText

from app.integrations.base import BaseAdapter


class SmtpEmailAdapter(BaseAdapter):
    provider = "email"

    def send_email(self, to: str, subject: str, text: str) -> dict:
        if not self.configured:
            return self.stub("send_email", {"to": to, "subject": subject, "text": text[:80]})

        def _do():
            import smtplib
            host = self.creds.get("smtp_host", "smtp.gmail.com")
            port = int(self.creds.get("smtp_port", 465))
            user = self.creds.get("smtp_user")
            password = self.creds.get("smtp_password")
            from_name = self.creds.get("from_name", "AI Leleka CRM")

            msg = MIMEText(text, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = f"{from_name} <{user}>"
            msg["To"] = to

            with smtplib.SMTP_SSL(host, port, timeout=self.timeout) as server:
                server.login(user, password)
                server.sendmail(user, [to], msg.as_string())
            return {"sent_to": to}
        return self._call(_do)
