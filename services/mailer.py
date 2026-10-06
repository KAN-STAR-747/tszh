"""Отправка писем с новым паролем.

Два способа (выбирается по настройкам в mail_config.json):
  1. Почтовый сервис Brevo по HTTPS (порт 443): включается, если указан brevo_api_key.
     Работает там, где закрыты почтовые порты.
  2. SMTP (по умолчанию Gmail): сначала порт 465 (SSL), если не вышло - порт 587 (STARTTLS).
"""

import json
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage

from services import settings
from services.errors import AppError

BREVO_URL = "https://api.brevo.com/v3/smtp/email"
SUBJECT = "Новый пароль для входа"
TIMEOUT = 15  # секунд на одно соединение


def make_text(password):
    """Текст письма с новым паролем."""
    return (
        "Здравствуйте!\n\n"
        "Вы запросили восстановление аккаунта в системе управления ТСЖ.\n"
        f"Ваш новый пароль: {password}\n\n"
        "Войдите с этим паролем. Если вы не запрашивали восстановление, сообщите председателю."
    )


def send_by_brevo(config, recipient, password):
    """Отправка через HTTPS-API Brevo. Ошибки сети и отказ сервиса - OSError."""
    body = json.dumps(
        {
            "sender": {"name": config["sender_name"], "email": config["smtp_user"]},
            "to": [{"email": recipient}],
            "subject": SUBJECT,
            "textContent": make_text(password),
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        BREVO_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "api-key": config["brevo_api_key"],
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT):
        pass  # ответ 2xx - письмо принято; ошибка придёт исключением HTTPError


def send_by_smtp(config, recipient, password):
    """Отправка через SMTP: порт 465 (SSL), при неудаче соединения - порт 587 (STARTTLS)."""
    message = EmailMessage()
    message["Subject"] = SUBJECT
    message["From"] = f"{config['sender_name']} <{config['smtp_user']}>"
    message["To"] = recipient
    message.set_content(make_text(password))

    context = ssl.create_default_context()
    last_error = OSError("нет соединения")
    for port, use_ssl in ((int(config["smtp_port"]), True), (587, False)):
        try:
            if use_ssl:
                server = smtplib.SMTP_SSL(config["smtp_host"], port, context=context, timeout=10)
            else:
                server = smtplib.SMTP(config["smtp_host"], port, timeout=10)
            with server as connection:
                if not use_ssl:
                    connection.starttls(context=context)
                connection.login(config["smtp_user"], config["smtp_password"])
                connection.send_message(message)
            return
        except (OSError, smtplib.SMTPConnectError) as error:  # порт закрыт - пробуем следующий
            last_error = error
    raise last_error


def send_password(recipient, password):
    """Отправляет письмо с новым паролем на адрес recipient.

    Raises:
        AppError: почта не настроена или письмо не отправилось.
    """
    config = settings.get_settings()
    use_brevo = bool(config["brevo_api_key"])
    if not config["smtp_user"] or not (use_brevo or config["smtp_password"]):
        raise AppError("Отправка почты не настроена: заполните файл mail_config.json.")
    try:
        if use_brevo:
            send_by_brevo(config, recipient, password)
        else:
            send_by_smtp(config, recipient, password)
    except urllib.error.HTTPError as error:  # сервис ответил отказом (например, неверный ключ)
        raise AppError(
            f"Почтовый сервис отклонил письмо (код {error.code}). Проверьте ключ и отправителя."
        ) from None
    except smtplib.SMTPAuthenticationError:
        raise AppError(
            "Почта отклонила вход: проверьте пароль приложения в mail_config.json."
        ) from None
    except (smtplib.SMTPException, OSError, ValueError) as error:
        # в скобках - техническая причина (например, TimeoutError - почтовый порт закрыт сетью)
        raise AppError(
            f"Не удалось отправить письмо ({type(error).__name__}). "
            "Проверьте подключение к интернету."
        ) from None
