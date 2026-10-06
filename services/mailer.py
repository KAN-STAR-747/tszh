"""Отправка писем с новым паролем.

Три способа (выбирается по настройкам в mail_config.json, сверху вниз):
  1. Скрипт Google Apps Script по HTTPS (порт 443): включается, если указан apps_script_url.
     Письмо уходит с вашей почты Gmail, регистрироваться нигде не нужно.
  2. Почтовый сервис Brevo по HTTPS: включается, если указан brevo_api_key.
  3. SMTP (по умолчанию Gmail): сначала порт 465 (SSL), если не вышло - порт 587 (STARTTLS).
Способы 1 и 2 работают там, где почтовые порты закрыты сетью.
"""

import json
import smtplib
import socket
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage

from services import settings
from services.errors import AppError

BREVO_URL = "https://api.brevo.com/v3/smtp/email"
TIMEOUT = 15  # секунд на одно соединение


def password_letter(password):
    """Тема и текст письма с новым паролем."""
    return "Новый пароль для входа", (
        "Здравствуйте!\n\n"
        "Вы запросили восстановление аккаунта в системе управления ТСЖ.\n"
        f"Ваш новый пароль: {password}\n\n"
        "Войдите с этим паролем. Если вы не запрашивали восстановление, сообщите председателю."
    )


def code_letter(code):
    """Тема и текст письма с кодом подтверждения регистрации."""
    return "Код подтверждения регистрации", (
        "Здравствуйте!\n\n"
        "Вы регистрируетесь в системе управления ТСЖ.\n"
        f"Ваш код подтверждения: {code}\n\n"
        "Введите его в программе. Код действует 10 минут. "
        "Если вы не регистрировались, просто проигнорируйте это письмо."
    )


def send_by_apps_script(config, recipient, subject, text):
    """Отправка через скрипт Google (google_mail_script.gs). Отказ скрипта - AppError."""
    body = json.dumps(
        {
            "token": config["apps_script_token"],
            "to": recipient,
            "subject": subject,
            "body": text,
            "name": config["sender_name"],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        config["apps_script_url"], data=body, headers={"Content-Type": "application/json"}
    )
    # Google отвечает перенаправлением на страницу с результатом: urllib проходит по нему сам
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        answer = json.load(response)
    if not answer.get("ok"):
        raise AppError(f"Скрипт Google не отправил письмо: {answer.get('error', 'неизвестно')}.")


def send_by_brevo(config, recipient, subject, text):
    """Отправка через HTTPS-API Brevo. Ошибки сети и отказ сервиса - OSError."""
    body = json.dumps(
        {
            "sender": {"name": config["sender_name"], "email": config["smtp_user"]},
            "to": [{"email": recipient}],
            "subject": subject,
            "textContent": text,
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


def send_by_smtp(config, recipient, subject, text):
    """Отправка через SMTP: порт 465 (SSL), при неудаче соединения - порт 587 (STARTTLS)."""
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{config['sender_name']} <{config['smtp_user']}>"
    message["To"] = recipient
    message.set_content(text)

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
    """Отправляет письмо с новым паролем на адрес recipient."""
    send_mail(recipient, *password_letter(password))


def send_code(recipient, code):
    """Отправляет письмо с кодом подтверждения регистрации на адрес recipient."""
    send_mail(recipient, *code_letter(code))


def send_mail(recipient, subject, text):
    """Отправляет письмо выбранным в настройках способом.

    Raises:
        AppError: почта не настроена или письмо не отправилось.
    """
    config = settings.get_settings()
    use_script = bool(config["apps_script_url"])
    use_brevo = bool(config["brevo_api_key"])
    smtp_ready = bool(config["smtp_user"] and config["smtp_password"])
    if not (use_script or (use_brevo and config["smtp_user"]) or smtp_ready):
        raise AppError("Отправка почты не настроена: заполните файл mail_config.json.")
    try:
        if use_script:
            send_by_apps_script(config, recipient, subject, text)
        elif use_brevo:
            send_by_brevo(config, recipient, subject, text)
        else:
            send_by_smtp(config, recipient, subject, text)
    except urllib.error.HTTPError as error:  # сервис ответил отказом (например, неверный ключ)
        raise AppError(
            f"Почтовый сервис отклонил письмо (код {error.code}). Проверьте ключ и отправителя."
        ) from None
    except smtplib.SMTPAuthenticationError:
        raise AppError(
            "Gmail отклонил вход. Если включён VPN, отключите его: Gmail часто блокирует вход "
            "с адресов VPN. Также проверьте пароль приложения в mail_config.json."
        ) from None
    except (smtplib.SMTPException, OSError, ValueError) as error:
        raise AppError(describe_error(error, use_script or use_brevo)) from None


def describe_error(error, over_https):
    """Понятное объяснение сбоя отправки (в скобках - техническая причина).

    Args:
        error: пойманное исключение.
        over_https (bool): письмо шло по HTTPS (скрипт Google или Brevo), а не по SMTP.
    """
    reason = type(error).__name__
    if isinstance(error, ssl.SSLError):
        hint = (
            "Не удалось установить защищённое соединение: VPN или антивирус подменяет сертификат."
        )
    elif isinstance(error, socket.gaierror):
        hint = (
            "Не найден адрес почтового сервера: проверьте интернет и DNS (при VPN смените сервер)."
        )
    elif over_https:
        hint = "Нет соединения с почтовым сервисом. Проверьте интернет или отключите VPN."
    else:
        hint = (
            "Нет соединения с почтовым сервером: почтовые порты закрыты сетью или VPN. "
            "Отключите VPN либо настройте отправку через скрипт Google (apps_script_url "
            "в mail_config.json) - она работает и с VPN."
        )
    return f"Не удалось отправить письмо ({reason}). {hint}"
