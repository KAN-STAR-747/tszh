// Скрипт Google Apps Script: отправляет письма с вашей почты Gmail по запросу программы.
// Инструкция: script.google.com -> Новый проект -> вставить этот код -> задать TOKEN ->
// Развернуть -> Новое развёртывание -> Веб-приложение (запуск: от моего имени, доступ: у всех).

// секретное слово: то же самое должно быть в mail_config.json (apps_script_token)
const TOKEN = "ЗАМЕНИТЕ_НА_СЕКРЕТНОЕ_СЛОВО";

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    if (data.token !== TOKEN) {
      return answer({ ok: false, error: "неверный токен" });
    }
    MailApp.sendEmail({
      to: data.to,
      subject: data.subject,
      body: data.body,
      name: data.name || "Система управления ТСЖ",
    });
    return answer({ ok: true });
  } catch (error) {
    return answer({ ok: false, error: String(error) });
  }
}

function answer(result) {
  return ContentService.createTextOutput(JSON.stringify(result)).setMimeType(
    ContentService.MimeType.JSON
  );
}
