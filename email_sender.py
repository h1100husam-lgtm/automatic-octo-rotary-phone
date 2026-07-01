# ═══════════════════════════════════════════
# إرسال إيميلات
# ═══════════════════════════════════════════
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class EmailSender:
    def __init__(self):
        self.email = None
        self.password = None

    def is_configured(self):
        return self.email and self.password

    def configure(self, email, password):
        self.email = email
        self.password = password

    def send(self, to_email, subject, body, html=False):
        """إرسال إيميل"""
        if not self.is_configured():
            return False, "⚠️ لم يتم إعداد الإيميل!\n💡 أرسل: /setemail your@gmail.com app_password"

        try:
            msg = MIMEMultipart()
            msg['From'] = self.email
            msg['To'] = to_email
            msg['Subject'] = subject
            content_type = 'html' if html else 'plain'
            msg.attach(MIMEText(body, content_type, 'utf-8'))

            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(self.email, self.password)
            server.send_message(msg)
            server.quit()

            return True, f"✅ تم إرسال الإيميل إلى {to_email}"

        except smtplib.SMTPAuthenticationError:
            return False, "❌ خطأ في كلمة المرور!\n💡 استخدم App Password من Google"
        except Exception as e:
            return False, f"❌ خطأ: {str(e)}"

    def send_report(self, to_email, subject, report_text):
        """إرسال تقرير منسق"""
        html_body = f"""
        <html>
        <body dir="rtl" style="font-family:Arial; padding:20px;">
            <h2 style="color:#2196F3;">📊 {subject}</h2>
            <div style="background:#f5f5f5; padding:15px; border-radius:10px;">
                <pre style="font-size:14px;">{report_text}</pre>
            </div>
            <p style="color:#888;">🤖 تم بواسطة Agent</p>
        </body>
        </html>
        """
        return self.send(to_email, subject, html_body, html=True)