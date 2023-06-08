import extract_msg

def msg_to_string(path: str):
    msg = extract_msg.Message(path)
    msg_sender = msg.sender
    msg_date = msg.date
    msg_subj = msg.subject
    msg_message = msg.body

    msgs = [msg_sender, msg_date, msg_subj, msg_message]
    msg_string = ""
    for i in msgs:
        msg_string += i + "\n"
    return msg_string


memo = msg_to_string("data/memo.msg")
memo2 = msg_to_string("data/memo2.msg")
