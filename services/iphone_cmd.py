import smtplib
from email.mime.text import MIMEText
from email.header import Header
from config import cfg

# 远程遥控：通过163邮箱SMTP发指令邮件到iPhone，触发快捷指令自动化


def send_iphone_cmd(cmd="回来"):
    """
    发送指令到iPhone。cmd: 回来 / 睡觉 等
    iPhone邮件App收到 → 快捷指令自动化检测到发件人 → 触发动作
    """
    if not cfg.MAIL_USER or not cfg.MAIL_AUTH_CODE or not cfg.MAIL_TO:
        return "远程遥控未配置（需要 MAIL_USER / MAIL_AUTH_CODE / MAIL_TO）"
    msg = MIMEText(cmd, "plain", "utf-8")
    msg["Subject"] = Header(f"遥控指令：{cmd}", "utf-8")
    msg["From"] = cfg.MAIL_USER
    msg["To"] = cfg.MAIL_TO
    try:
        port = cfg.MAIL_SMTP_PORT
        if port == 465:
            # SSL 直连
            server = smtplib.SMTP_SSL(cfg.MAIL_SMTP_HOST, port, timeout=10)
        else:
            # 587 或其它，用 STARTTLS
            server = smtplib.SMTP(cfg.MAIL_SMTP_HOST, port, timeout=10)
            server.ehlo()
            server.starttls()
            server.ehlo()
        server.login(cfg.MAIL_USER, cfg.MAIL_AUTH_CODE)
        server.sendmail(cfg.MAIL_USER, [cfg.MAIL_TO], msg.as_string())
        server.quit()
        return f"已发送指令：{cmd}"
    except Exception as e:
        return f"发送失败：{e}"