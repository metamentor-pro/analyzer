import json
import traceback

d = json.load(open("data/sample_column.txt"))

reformatted = []


def transform_list_to_join(l):
    ans = []
    for i in l:
        if i is None:
            ans.append("None")
        else:
            ans.append(i)
    return ans


for item in d:
    try:
        new_item = {'date': item['date'], 'coord': item['coord'],
                    'row_title_column': ' '.join(transform_list_to_join(item['row_title_column']))}
        for column_name in ["column_310", "column_268", "column_386", "column_281", "column_362", "column_314",
                            "column_331", "column_354", "column_475", "column_364", "column_370", "column_372"]:
            new_item[column_name] = float(item[column_name][0]) if item[column_name][0] is not None else None
        reformatted.append(new_item)
    except Exception as e:
        print(traceback.format_exc())
        print(item)
        break

with open('data/data.json', 'w', encoding='utf-8') as f:
    json.dump(reformatted, f, ensure_ascii=False, indent=4)
