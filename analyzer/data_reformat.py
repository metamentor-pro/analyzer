"""
This module provides functionality for loading data from a JSON file, transforming the data, and then writing the transformed data back to a new JSON file.

The transformation involves converting certain fields from lists to strings and handling missing values.
"""

import json
import traceback


d = json.load(open("data/sample_column.txt"))

reformatted = []


def transform_list_to_join(l: list) -> list:
    """
    Transforms a list into a new list where each element is a string.
    If an element in the input list is None, it is replaced with the string "None" in the output list.
    
    Args:
        l: The list to transform.
    
    Returns:
        The transformed list.
    """
    ans = []
    for i in l:
        if i is None:
            ans.append("None")
        else:
            ans.append(i)
    return ans


for item in d:
    try:
        new_item = {'date': item['date'],
                    'row_title_column': ' '.join(transform_list_to_join(item['row_title_column']))}
        for column_name in ["column_310", "column_268", "column_386", "column_281", "column_362", "column_314",
                            "column_331", "column_354", "column_475", "column_364", "column_370", "column_372"]:
            if item[column_name][0] is None:
                new_item[column_name] = None
            elif float(item[column_name][0]) == 0. and column_name in ["column_370"]:
                new_item[column_name] = None
            else:
                new_item[column_name] = float(item[column_name][0])
        reformatted.append(new_item)
    except Exception as e:
        print(traceback.format_exc())
        print(item)
        break

with open('data/data.json', 'w', encoding='utf-8') as f:
    json.dump(reformatted, f, ensure_ascii=False, indent=4)