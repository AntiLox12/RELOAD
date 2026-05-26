import sys

from telegram.ext import CallbackQueryHandler, ConversationHandler, MessageHandler, filters


def _bot():
    main_mod = sys.modules.get("__main__")
    if main_mod is not None and getattr(main_mod, "__file__", "").endswith("Bot_new.py"):
        return main_mod

    import Bot_new

    return Bot_new


def can_handle_callback(data: str) -> bool:
    exact = {
        "settings_plantation_reminder",
        "market_plantation",
        "plantation_my_beds",
        "plantation_shop",
        "plantation_fertilizers_shop",
        "plantation_fertilizers_inv",
        "plantation_harvest",
        "plantation_harvest_all",
        "plantation_water",
        "plantation_stats",
        "plantation_bed_prices",
        "plantation_buy_bed",
        "plantation_join_project",
        "plantation_my_contribution",
        "plantation_water_all",
        "plantation_leaderboard",
    }
    prefixes = (
        "snooze_remind_",
        "plantation_buy_",
        "fert_filter_",
        "fert_buy_",
        "fert_apply_pick_",
        "fert_apply_mode_",
        "fert_apply_do_",
        "fert_apply_max_",
        "fert_pick_for_bed_",
        "plantation_choose_",
        "plantation_plant_",
        "plantation_water_",
        "plantation_harvest_bed_",
    )
    return data in exact or data.startswith(prefixes)


async def handle_callback(update, context, data: str):
    bot = _bot()

    if data == "settings_plantation_reminder":
        return await bot.toggle_plantation_reminder(update, context)
    if data == "market_plantation":
        return await bot.show_market_plantation(update, context)
    if data == "plantation_my_beds":
        return await bot.show_plantation_my_beds(update, context)
    if data == "plantation_shop":
        return await bot.show_plantation_shop(update, context)
    if data == "plantation_fertilizers_shop":
        return await bot.show_plantation_fertilizers_shop(update, context)
    if data == "plantation_fertilizers_inv":
        return await bot.show_plantation_fertilizers_inventory(update, context)
    if data == "plantation_harvest":
        return await bot.show_plantation_harvest(update, context)
    if data == "plantation_harvest_all":
        return await bot.handle_plantation_harvest_all(update, context)
    if data == "plantation_water":
        return await bot.show_plantation_water(update, context)
    if data == "plantation_stats":
        return await bot.show_plantation_stats(update, context)
    if data == "plantation_bed_prices":
        return await bot.show_plantation_bed_prices(update, context)
    if data == "plantation_buy_bed":
        return await bot.handle_plantation_buy_bed(update, context)
    if data == "plantation_join_project":
        return await bot.show_plantation_join_project(update, context)
    if data == "plantation_my_contribution":
        return await bot.show_plantation_my_contribution(update, context)
    if data == "plantation_water_all":
        return await bot.show_plantation_water_all(update, context)
    if data == "plantation_leaderboard":
        return await bot.show_plantation_leaderboard(update, context)
    if data.startswith("snooze_remind_"):
        return await bot.snooze_reminder_handler(update, context)
    if data.startswith("plantation_buy_"):
        _, _, sid, qty = data.split("_")
        return await bot.handle_plantation_buy(update, context, int(sid), int(qty))
    if data.startswith("fert_filter_"):
        return await bot.show_plantation_fertilizers_shop(update, context, filter_category=data.split("_")[-1])
    if data.startswith("fert_buy_"):
        _, _, fertilizer_id, quantity = data.split("_")
        return await bot.handle_fertilizer_buy(update, context, int(fertilizer_id), int(quantity))
    if data.startswith("fert_apply_pick_"):
        return await bot.show_fertilizer_apply_pick_bed(update, context, int(data.split("_")[-1]))
    if data.startswith("fert_apply_mode_"):
        _, _, _, bed_index, fertilizer_id = data.split("_")
        return await bot.show_fertilizer_apply_mode(update, context, int(bed_index), int(fertilizer_id))
    if data.startswith("fert_apply_do_"):
        _, _, _, bed_index, fertilizer_id = data.split("_")
        return await bot.handle_fertilizer_apply(update, context, int(bed_index), int(fertilizer_id))
    if data.startswith("fert_apply_max_"):
        _, _, _, bed_index, fertilizer_id = data.split("_")
        return await bot.handle_fertilizer_apply_max(update, context, int(bed_index), int(fertilizer_id))
    if data.startswith("fert_pick_for_bed_"):
        return await bot.show_fertilizer_pick_for_bed(update, context, int(data.split("_")[-1]))
    if data.startswith("plantation_choose_"):
        return await bot.show_plantation_choose_seed(update, context, int(data.split("_")[-1]))
    if data.startswith("plantation_plant_"):
        _, _, bed_index, seed_type_id = data.split("_")
        return await bot.handle_plantation_plant(update, context, int(bed_index), int(seed_type_id))
    if data.startswith("plantation_water_"):
        return await bot.handle_plantation_water(update, context, int(data.split("_")[-1]))
    if data.startswith("plantation_harvest_bed_"):
        return await bot.handle_plantation_harvest(update, context, int(data.split("_")[-1]))


def register_handlers(application):
    bot = _bot()

    fertilizer_custom_buy_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(bot.start_fertilizer_custom_buy_wrapper, pattern="^fert_buy_custom_")],
        states={
            bot.FERTILIZER_CUSTOM_QTY: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), bot.handle_fertilizer_custom_qty_input)
            ],
        },
        fallbacks=[CallbackQueryHandler(bot.cancel_fertilizer_custom_buy, pattern="^fert_custom_cancel$|^plantation_fertilizers_shop$")],
        allow_reentry=True,
    )
    application.add_handler(fertilizer_custom_buy_handler)

    seed_custom_buy_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(bot.start_seed_custom_buy_wrapper, pattern="^seed_buy_custom_")],
        states={
            bot.SEED_CUSTOM_QTY: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), bot.handle_seed_custom_qty_input),
                CallbackQueryHandler(bot.seed_custom_retry, pattern="^seed_custom_retry$"),
                CallbackQueryHandler(bot.seed_custom_buy_max, pattern="^seed_custom_buy_max$"),
                CallbackQueryHandler(bot.cancel_seed_custom_buy, pattern="^seed_custom_cancel$"),
            ],
        },
        fallbacks=[CallbackQueryHandler(bot.cancel_seed_custom_buy, pattern="^seed_custom_cancel$|^plantation_shop$")],
        allow_reentry=True,
    )
    application.add_handler(seed_custom_buy_handler)

    application.add_handler(CallbackQueryHandler(bot.toggle_plantation_reminder, pattern="^toggle_plantation_rem$"))
    application.add_handler(CallbackQueryHandler(bot.snooze_reminder_handler, pattern="^snooze_remind_"))


def schedule_jobs(application):
    bot = _bot()

    if not application.job_queue:
        return

    application.job_queue.run_repeating(bot.global_farmer_harvest_job, interval=10 * 60, first=60)
    application.job_queue.run_repeating(bot.global_farmer_fertilize_job, interval=5 * 60, first=75)
    application.job_queue.run_repeating(bot.global_negative_effects_job, interval=60, first=90)
    application.job_queue.run_repeating(bot.farmer_summary_job, interval=5 * 60, first=90)

    async def restore_plantation_reminders_on_startup(context):
        await bot.restore_plantation_reminders(context.application)

    application.job_queue.run_once(restore_plantation_reminders_on_startup, when=5)
