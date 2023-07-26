from db_manager import *
import interactor


def get_context(chat_id: int =None) -> List:
    settings = get_settings(chat_id)
    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("SELECT group_flag FROM callback_manager WHERE user_id == ?", (chat_id,))
    table_name = list(map(str, settings["table_name"].split(",")))

    group_flag = cur.fetchone()[0]
    context_list = []

    if group_flag == True:
        cur.execute("SELECT group_name FROM callback_manager WHERE user_id == ?", (chat_id,))
        group_name = cur.fetchone()[0]
        cur.execute("SELECT admin_id FROM callback_manager WHERE user_id == ?", (chat_id,))
        chat_id = cur.fetchone()[0]
        for table in table_name:
            cur.execute("SELECT context from group_tables WHERE admin_id == ? AND  group_name == ?", (chat_id, group_name))
            context = cur.fetchone()
            if not context or context[0] is None:
                context_line = table + ":"
            else:
                context_line = table + ":" + context[0]
            context_list.append(context_line)

    else:
        for table in table_name:
            cur.execute("SELECT context FROM tables WHERE user_id == ? AND table_name == ?", (chat_id, table))
            context = cur.fetchone()
            if not context or context[0] is None:
                context_line = table + ":"
            else:
                context_line = table + ":" + context[0]
            context_list.append(context_line)
    con.close()
    return context_list


def get_description(chat_id: int = None) -> List:
    settings = get_settings(chat_id)
    table_name = list(map(str, settings["table_name"].split(",")))
    table_name_path = table_name.copy()
    table_description = []

    for table in range(len(table_name_path)):
        table_name_path[table] = "data/" + table_name_path[table]
    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("SELECT group_flag FROM callback_manager WHERE user_id == ?", (chat_id,))

    group_flag = cur.fetchone()[0]
    if group_flag == True:
        cur.execute("SELECT group_name FROM callback_manager WHERE user_id == ?", (chat_id,))
        group_name = cur.fetchone()[0]
        cur.execute("SELECT admin_id FROM callback_manager WHERE user_id == ?", (chat_id,))
        admin_id = cur.fetchone()[0]
        con.close()
        for table in table_name:
            con = sq.connect(db_name)

            cur = con.cursor()
            cur.execute("SELECT * FROM group_tables WHERE admin_id == ? AND table_name == ? AND group_name == ?", (admin_id, table, group_name))
            existing_record = cur.fetchone()

            if existing_record is not None:

                cur.execute("SELECT table_description FROM group_tables WHERE admin_id == ? AND table_name == ? AND group_name  == ?",  (admin_id, table, group_name))
                description = cur.fetchone()

                if not description or description[0] is None:
                    table_description_line = table + ":"
                else:
                    table_description_line = table + ":" + description[0]

                table_description.append(table_description_line)

            con.commit()

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
    con.close()
    return table_description


def get_summary(chat_id: int) -> str:
    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("SELECT group_flag FROM callback_manager WHERE user_id == ?", (chat_id,))

    group_flag = cur.fetchone()[0]
    con.commit()
    if group_flag == True:
        cur.execute("SELECT group_name FROM callback_manager WHERE user_id == ?", (chat_id,))
        group_name = cur.fetchone()[0]
        cur.execute("SELECT admin_id FROM callback_manager WHERE user_id == ?", (chat_id,))
        admin_id = cur.fetchone()[0]
        cur.execute("SELECT group_conv FROM groups WHERE admin_id == ? AND group_name == ?", (admin_id, group_name))
        current_summary = cur.fetchone()
    else:

        cur.execute("SELECT conv_sum FROM users WHERE user_id = ?", (chat_id,))
        current_summary = cur.fetchone()

    if not current_summary or current_summary[0] is None:
        current_summary = ""
    else:
        current_summary = current_summary[0][:250] + current_summary[0][-500:]
    return current_summary

def settings_prep(chat_id: int):
    settings = get_settings(chat_id)
    if settings["table_name"] is None:
        return False
    table_name = list(map(str, settings["table_name"].split(",")))
    for i in range(len(table_name)):
        prep_name = list(table_name[i].split("_"))
        table_name[i] = "_".join(prep_name[1:])
    return ",".join(table_name)


def delete_last_table(chat_id : int = None) -> List[str]:
    settings = get_settings(chat_id)
    table_name = list(map(str, settings["table_name"].split(",")))
    table_name = table_name[:-1]
    if len(table_name) == 0:
        settings["table_name"] = ''
    else:
        settings["table_name"] = ''
        for i in range(len(table_name) - 1):
            settings["table_name"] += table_name[i] + ","
        settings["table_name"] += table_name[-1]

    con = sq.connect(db_name)
    cur = con.cursor()
    group_name = check_group_design(chat_id)
    if group_name is not None:
        cur.execute("UPDATE groups SET current_tables = ? WHERE admin_id == ? AND group_name == ?",
                    (settings["table_name"], chat_id, group_name))
        con.commit()
    else:
        cur.execute("UPDATE users SET current_tables = ? WHERE user_id == ?", (settings["table_name"], chat_id))
        con.commit()

    con.close()
    return table_name



def exit_from_group_db(chat_id: int = None) -> None:
    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("UPDATE callback_manager SET group_flag = 0 WHERE user_id == ?", (chat_id,))
    con.commit()
    con.close()


def exit_from_model(chat_id: int = None) -> None:
    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("UPDATE callback_manager SET group_flag = 0 WHERE user_id == ?", (chat_id,))
    con.commit()
    con.close()

def make_insertion(chat_id: int = None) -> bool:
    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("SELECT * FROM callback_manager WHERE user_id = ?", (chat_id,))
    existing_record = cur.fetchone()
    try:
        if not existing_record:
            cur.execute("INSERT  INTO callback_manager(user_id) VALUES(?)", (int(chat_id),))
        con.commit()
    except Exception as e:
        print(traceback.format_exc())
        print("error is:", e)
        logging.error(traceback.format_exc())
        con.close()

    cur.execute("SELECT * FROM users WHERE user_id = ?", (chat_id,))
    existing_record = cur.fetchone()

    try:
        if not existing_record:
            cur.execute("""INSERT INTO users(user_id) values(?)""", (chat_id,))
            con.commit()
            con.close()
            return True
        con.commit()
        con.close()
    except Exception as e:
        print(traceback.format_exc())
        print("error is:", e)
        logging.error(traceback.format_exc())
        con.close()


def model_call(chat_id, user_question, callback):
    settings = get_settings(chat_id)
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