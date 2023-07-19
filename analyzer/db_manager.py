import sqlite3 as sq
import yaml


with open("config.yaml") as f:
    cfg = yaml.load(f, Loader=yaml.FullLoader)
db_name = cfg["db_name"]

def check_for_group(message):
    con = sq.connect(db_name)
    cur = con.cursor()

    try:
        text = message.text
        start, group_data = map(str, text.split())
        group, admin_id, group_name = map(str, text.split("_"))

    except Exception as e:
        text = message.text
        if text == "/start":

            cur.execute("UPDATE callback_manager SET group_flag = ? WHERE user_id == ? ", (0, message.chat.id))
            con.commit()
        con.close()
        return False

    if start == "/start":

        cur.execute("SELECT * FROM groups where group_name == ?",(group_name,))
        existing_record = cur.fetchone()
        if existing_record is not None:

            cur.execute("UPDATE callback_manager SET group_flag = ? WHERE user_id == ?", (1, message.chat.id))
            con.commit()
            cur.execute("UPDATE callback_manager SET group_name = ? WHERE user_id == ?", (group_name, message.chat.id))
            con.commit()
            cur.execute("UPDATE callback_manager SET admin_id = ? WHERE user_id == ?", (admin_id, message.chat.id))
            con.commit()
            con.close()
            return True
        else:
            cur.execute("UPDATE callback_manager SET group_flag = ? WHERE user_id == ?", (0, message.chat.id))
            con.commit()
            return False
    else:
        cur.execute("SELECT group_flag FROM callback_manager WHERE user_id == ? ", (message.chat_id,))
        is_group = cur.fetchone()[0]
        if is_group:
            con.close()
            return True
        else:
            con.close()
            return False


def check_group_design(chat_id=None):

    admin_id = chat_id
    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("SELECT group_name FROM groups where admin_id = ? AND design_flag == 1 ", (admin_id,))
    group_name = cur.fetchone()
    con.close()
    if group_name is not None:
        return group_name[0]
    else:
        return None


def get_settings(chat_id):

    group_name = check_group_design(chat_id)

    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("SELECT group_flag FROM callback_manager WHERE user_id == ?",(chat_id,))

    group_flag = cur.fetchone()[0]
    cur.execute("SELECT * FROM callback_manager WHERE user_id = ?", (chat_id,))
    existing_record = cur.fetchone()
    print("callback", existing_record)

    if group_flag:

        cur.execute("SELECT group_name FROM callback_manager WHERE user_id == ?", (chat_id,))
        group_name = cur.fetchone()[0]
        cur.execute("SELECT admin_id FROM callback_manager WHERE user_id == ?", (chat_id,))
        chat_id = cur.fetchone()[0]

        con = sq.connect(db_name)
        cur = con.cursor()
        cur.execute(
            "SELECT current_tables FROM groups WHERE admin_id = ? and group_name == ?", (chat_id, group_name))
        table_names = cur.fetchone()
        cur.execute("SELECT group_plot FROM groups WHERE admin_id = ? and group_name = ?", (chat_id, group_name))
        build_plots = cur.fetchone()
        con.close()

    elif group_name is not None:

        con = sq.connect(db_name)
        cur = con.cursor()
        cur.execute("SELECT current_tables FROM groups WHERE admin_id = ? and group_name == ?", (chat_id, group_name))
        table_names = cur.fetchone()
        cur.execute("SELECT group_plot FROM groups WHERE admin_id = ? and group_name = ?", (chat_id, group_name))
        build_plots = cur.fetchone()
        con.close()

    else:
        con = sq.connect(db_name)
        cur = con.cursor()
        cur.execute("SELECT current_tables FROM users WHERE user_id = ?", (chat_id,))
        table_names = cur.fetchone()
        cur.execute("SELECT build_plots FROM users WHERE user_id = ?", (chat_id,))
        build_plots = cur.fetchone()
        cur.execute("SELECT * FROM users")

        con.close()

    if table_names is not None:
        settings = {"table_name": table_names[0],
                    "build_plots": build_plots[0],
                    }
    else:
        settings = {"table_name": None,
                    "build_plots": True,
                    }
    print(settings)
    return settings


def get_context(chat_id=None):
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


def get_description(chat_id=None):
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


def get_summary(chat_id):
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
        current_summary = current_summary[0][:250] + current_summary[0][:-250]
    return current_summary


def update_summary(chat_id, new_summary):
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
        cur.execute("UPDATE groups SET group_conv = ? WHERE admin_id == ? AND group_name == ?",
                    (new_summary, admin_id, group_name))
        con.commit()
    else:
        cur.execute("UPDATE users SET conv_sum = ? WHERE user_id == ?", (new_summary, chat_id))
        con.commit()
    con.close()
