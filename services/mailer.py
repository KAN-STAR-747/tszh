"""Отправка писем с новым паролем (SMTP, по умолчанию почта Gmail)."""

import smtplib
import ssl
from email.message import EmailMessage

from services import settings
from services.errors import AppError


def send_password(recipient, password):
    """Отправляет письмо с новым паролем на адрес recipient.

    Raises:
        AppError: почта не настроена или письмо не отправилось.
    """
    config = settings.get_settings()
    if not config["smtp_user"] or not config["smtp_password"]:
        raise AppError(
            "Отправка почты не настроена: укажите пароль почты в файле mail_config.json."
        )

    message = EmailMessage()
    message["Subject"] = "Новый пароль для входа"
    message["From"] = f"{config['sender_name']} <{config['smtp_user']}>"
    message["To"] = recipient
    message.set_content(
        "Здравствуйте!\n\n"
        "Вы запросили восстановление аккаунта в системе управления ТСЖ.\n"
        f"Ваш новый пароль: {password}\n\n"
        "Войдите с этим паролем. Если вы не запрашивали восстановление, сообщите председателю."
    )
    try:
        with smtplib.SMTP_SSL(
            config["smtp_host"],
            int(config["smtp_port"]),
            context=ssl.create_default_context(),
            timeout=20,
        ) as server:
            server.login(config["smtp_user"], config["smtp_password"])
            server.send_message(message)
    except smtplib.SMTPAuthenticationError:
        raise AppError(
            "Почта отклонила вход: проверьте пароль приложения в mail_config.json."
        ) from None
    except (smtplib.SMTPException, OSError, ValueError):
        raise AppError("Не удалось отправить письмо. Проверьте подключение к интернету.") from None
