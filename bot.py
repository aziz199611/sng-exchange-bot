@bot.message_handler(func=lambda m: True, content_types=['text', 'photo', 'document'])
def relay(msg):
    # Пропускаем кнопки меню
    if msg.text in ["📋 Мои заявки", "💬 Поддержка", "👨‍💼 Панель менеджера", "💱 Обменять валюту"]:
        return
    
    user_id = msg.from_user.id
    state, data = db.get_state(user_id)
    
    # Ввод суммы CNY
    if state == "enter_amount":
        try:
            cny = float(msg.text.replace(",", ".").replace(" ", ""))
            if cny < 1:
                bot.send_message(msg.chat.id, "❌ Минимум 1 CNY")
                return
            
            rate = db.get_rate_for_amount(cny)
            rub = cny * rate
            
            data["cny_amount"] = cny
            data["rub_amount"] = rub
            data["rate"] = rate
            db.set_state(user_id, "confirm", data)
            
            text = ORDER_CONFIRM.format(
                rate=rate,
                cny_amount=cny,
                rub_amount=rub
            )
            bot.send_message(msg.chat.id, text, parse_mode="HTML", reply_markup=confirm_kb())
        except ValueError:
            bot.send_message(msg.chat.id, "❌ Введите число")
        return
    
    # Менеджер пишет клиенту
    if is_manager(user_id) and state == "mgr_chat" and data and "order_id" in data:
        order = db.get_order(data["order_id"])
        if order:
            try:
                if msg.photo:
                    bot.send_photo(order["user_id"], msg.photo[-1].file_id, 
                                  caption=f"👨‍💼 <b>Менеджер:</b>\n{msg.caption or ''}", parse_mode="HTML")
                elif msg.document:
                    bot.send_document(order["user_id"], msg.document.file_id, 
                                     caption=f"👨‍💼 <b>Менеджер:</b>\n{msg.caption or ''}", parse_mode="HTML")
                else:
                    bot.send_message(order["user_id"], f"👨‍💼 <b>Менеджер:</b>\n{msg.text}", parse_mode="HTML")
                bot.send_message(msg.chat.id, "✅ Отправлено")
            except Exception as e:
                bot.send_message(msg.chat.id, f"❌ Ошибка: {e}")
        return
    
    # Клиент пишет
    order = db.get_user_active_order(user_id)
    if order and order.get("manager_id"):
        try:
            header = f"💬 <b>Клиент #{order['order_number'][-4:]}</b> ({order.get('first_name', 'Клиент')}):\n\n"
            if msg.photo:
                bot.send_photo(order["manager_id"], msg.photo[-1].file_id, 
                              caption=header + (msg.caption or ""), parse_mode="HTML")
            elif msg.document:
                bot.send_document(order["manager_id"], msg.document.file_id, 
                                 caption=header + (msg.caption or ""), parse_mode="HTML")
            else:
                bot.send_message(order["manager_id"], header + msg.text, parse_mode="HTML")
            bot.send_message(msg.chat.id, "✅ Отправлено менеджеру")
        except:
            bot.send_message(msg.chat.id, "⏳ Менеджер получит ваше сообщение")
    elif order:
        for mgr in get_all_manager_ids():
            try:
                bot.send_message(mgr, f"💬 Сообщение в заявке #{order['order_number']}")
            except:
                pass
        bot.send_message(msg.chat.id, "✅ Сообщение получено. Менеджер скоро ответит.")
    else:
        bot.send_message(msg.chat.id, "💬 Нажмите «💱 Обменять валюту» чтобы создать заявку.", 
                        reply_markup=main_kb(user_id))


if name == "__main__":
    print("Bot started...")
    bot.infinity_polling()
