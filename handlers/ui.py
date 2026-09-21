"""Мелкие UI-хелперы."""
from html import escape as esc


async def send_or_edit(update, text, reply_markup=None, parse_mode=None):
    """Если пришёл callback — редактируем сообщение, иначе отправляем новое."""
    if update.callback_query:
        try:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                text, reply_markup=reply_markup, parse_mode=parse_mode
            )
            return
        except Exception:
            pass
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
