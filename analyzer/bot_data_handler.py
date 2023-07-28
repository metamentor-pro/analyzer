import aiosqlite

from db_manager import *
import interactor


async def get_context(chat_id: int =None) -> List:
    settings = await get_settings(chat_id)
    con = aiosqlite.connect(db_name)
    group_flag = await con.execute("SELECT group_flag FROM callback_manager WHERE user_id == ?", (chat_id,))
    table_name = list(map(str, settings["table_name"].split(",")))

    group_flag = group_flag.fetchone()[0]
    context_list = []

    if group_flag == True:
        group_name = await con.execute("SELECT group_name FROM callback_manager WHERE user_id == ?", (chat_id,))
        group_name = group_name.fetchone()[0]
        chat_id = await con.execute("SELECT admin_id FROM callback_manager WHERE user_id == ?", (chat_id,))
        chat_id = chat_id.fetchone()[0]
        for table in table_name:
            context = await  con.execute("SELECT context from group_tables WHERE admin_id == ? AND  group_name == ?", (chat_id, group_name))
            context = context.fetchone()
            if not context or context[0] is None:
                context_line = table + ":"
            else:
                context_line = table + ":" + context[0]
            context_list.append(context_line)

    else:
        for table in table_name:
            context = await con.execute("SELECT context FROM tables WHERE user_id == ? AND table_name == ?", (chat_id, table))
            context = context.fetchone()
            if not context or context[0] is None:
                context_line = table + ":"
            else:
                context_line = table + ":" + context[0]
            context_list.append(context_line)
    return context_list


async def get_description(chat_id: int = None) -> List:
    settings = await get_settings(chat_id)
    table_name = list(map(str, settings["table_name"].split(",")))
    table_name_path = table_name.copy()
    table_description = []

    for table in range(len(table_name_path)):
        table_name_path[table] = "data/" + table_name_path[table]
    con = aiosqlite.connect(db_name)
    group_flag = await con.execute("SELECT group_flag FROM callback_manager WHERE user_id == ?", (chat_id,))
    group_flag = group_flag.fetchone()[0]
    if group_flag == True:
        group_name = await con.execute("SELECT group_name FROM callback_manager WHERE user_id == ?", (chat_id,))
        group_name = group_name.fetchone()[0]
        admin_id = await con.execute("SELECT admin_id FROM callback_manager WHERE user_id == ?", (chat_id,))
        admin_id = admin_id.fetchone()[0]
        for table in table_name:
            con = aiosqlite.connect(db_name)
            existing_record = await con.execute("SELECT * FROM group_tables WHERE admin_id == ? AND table_name == ? AND group_name == ?", (admin_id, table, group_name))
            existing_record = existing_record.fetchone()

            if existing_record is not None:

                description = await con.execute("SELECT table_description FROM group_tables WHERE admin_id == ? AND table_name == ? AND group_name  == ?",  (admin_id, table, group_name))
                description = description.fetchone()

                if not description or description[0] is None:
                    table_description_line = table + ":"
                else:
                    table_description_line = table + ":" + description[0]

                table_description.append(table_description_line)

            await con.commit()

    else:
        for table in table_name:
            con = sq.connect(db_name)
            cur = con.cursor()
            cur.execute("SELECT * FROM tables WHERE user_id == ? AND table_name == ?", (chat_id, table))
            existing_record = cur.fetchone()

            if existing_record is not None:

                cur.execute(
                    "SELECT table_description FROM tables WHERE user_id == ? AND table_name == ?", (chat_id, table))
                description = cur.fetchone()

                if not description or description[0] is None:
                    table_description_line = table + ":"
                else:
                    table_description_line = table + ":" + description[0]

                table_description.append(table_description_line)

                print("table description:", table_description)
            con.commit()
    return table_description


async def get_summary(chat_id: int) -> str:
    con = aiosqlite.connect(db_name)
    group_flag = await con.execute("SELECT group_flag FROM callback_manager WHERE user_id == ?", (chat_id,))

    group_flag = group_flag.fetchone()[0]
    await con.commit()
    if group_flag == True:
        group_name = await  con.execute("SELECT group_name FROM callback_manager WHERE user_id == ?", (chat_id,))
        group_name = group_name.fetchone()[0]
        admin_id = await con.execute("SELECT admin_id FROM callback_manager WHERE user_id == ?", (chat_id,))
        admin_id = admin_id.fetchone()[0]
        current_summary = await con.execute("SELECT group_conv FROM groups WHERE admin_id == ? AND group_name == ?", (admin_id, group_name))
        current_summary = current_summary.fetchone()
    else:

        current_summary = await con.execute("SELECT conv_sum FROM users WHERE user_id = ?", (chat_id,))
        current_summary = current_summary.fetchone()

    if not current_summary or current_summary[0] is None:
        current_summary = ""
    else:
        current_summary = current_summary[0][:250] + current_summary[0][-500:]
    return current_summary

async def settings_prep(chat_id: int):
    settings = await get_settings(chat_id)
    if settings["table_name"] is None:
        return False
    table_name = list(map(str, settings["table_name"].split(",")))
    for i in range(len(table_name)):
        prep_name = list(table_name[i].split("_"))
        table_name[i] = "_".join(prep_name[1:])
    return ",".join(table_name)


async def delete_last_table(chat_id : int = None) -> List[str]:
    settings = await get_settings(chat_id)
    table_name = list(map(str, settings["table_name"].split(",")))
    table_name = table_name[:-1]
    if len(table_name) == 0:
        settings["table_name"] = ''
    else:
        settings["table_name"] = ''
        for i in range(len(table_name) - 1):
            settings["table_name"] += table_name[i] + ","
        settings["table_name"] += table_name[-1]

    con = aiosqlite.connect(db_name)

    group_name = check_group_design(chat_id)
    if group_name is not None:
        await con.execute("UPDATE groups SET current_tables = ? WHERE admin_id == ? AND group_name == ?",
                    (settings["table_name"], chat_id, group_name))
        await con.commit()
    else:
        await con.execute("UPDATE users SET current_tables = ? WHERE user_id == ?", (settings["table_name"], chat_id))
        await con.commit()

    return table_name


async def exit_from_group_db(chat_id: int = None) -> None:
    con = aiosqlite.connect(db_name)
    await con.execute("UPDATE callback_manager SET group_flag = 0 WHERE user_id == ?", (chat_id,))
    await con.commit()


async def exit_from_model(chat_id: int = None) -> None:
    con = aiosqlite.connect(db_name)
    await con.execute("UPDATE callback_manager SET group_flag = 0 WHERE user_id == ?", (chat_id,))
    await con.commit()


async def make_insertion(chat_id: int = None) -> bool:
    print("making_insertion")
    async with aiosqlite.connect(db_name) as db:
        result = await db.execute("SELECT * FROM callback_manager WHERE user_id = ?", (chat_id,))
        existing_record = await result.fetchone()
        try:
            if not existing_record:
                await db.execute("INSERT  INTO callback_manager(user_id) VALUES(?)", (int(chat_id),))
            await db.commit()
            existing_record = await db.execute("SELECT * FROM users WHERE user_id = ?", (chat_id,))
            existing_record = await existing_record.fetchone()
            if not existing_record:
                await db.execute("""INSERT INTO users(user_id) values(?)""", (chat_id,))
                await db.commit()

                print("making_insertion1")
                return True
            await db.commit()

        except Exception as e:
            print(traceback.format_exc())
            print("error is:", e)
            logging.error(traceback.format_exc())

        print("making_insertion2")
        return False


async def model_call(chat_id, user_question, callback):
    settings = await get_settings(chat_id)
    table_name = list(map(str, settings["table_name"].split(",")))
    print("available tables for model:", table_name)
    table_name_path = table_name.copy()
    for table in range(len(table_name_path)):
        table_name_path[table] = "data/" + table_name_path[table].strip()

    table_description = get_description(chat_id)
    context_list = get_context(chat_id)
    current_summary = get_summary(chat_id)

    build_plots = settings["build_plots"]

    answer_from_model = interactor.run_loop_bot(table_name_path, build_plots, user_question, current_summary,
                                                table_description, context_list, callback=callback)
    return answer_from_model