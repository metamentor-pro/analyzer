import openpyxl
import os
from openpyxl.utils.cell import range_boundaries
from openpyxl.styles import PatternFill


def get_data_range(sheet):
    start_row, start_col, end_row, end_col = None, None, None, None
    for row in sheet.iter_rows():
        for cell in row:
            if cell.value is not None:
                row_index = cell.row
                col_index = cell.column
                if start_row is None or row_index < start_row:
                    start_row = row_index
                if start_col is None or col_index < start_col:
                    start_col = col_index
                if end_row is None or row_index > end_row:
                    end_row = row_index
                if end_col is None or col_index > end_col:
                    end_col = col_index

    if start_row is not None and start_col is not None and end_row is not None and end_col is not None:
        start_col_name = openpyxl.utils.get_column_letter(start_col)
        end_col_name = openpyxl.utils.get_column_letter(end_col)
        data_range = f"{start_col_name}{start_row}:{end_col_name}{end_row}"
        return data_range, start_row, start_col, start_col_name, end_col_name
    else:
        return None


def move(file_path, save_path):
    wb = openpyxl.load_workbook(file_path, data_only=True)
    sheet = wb.active
    range = get_data_range(sheet)
    if range:
        sheet.move_range(range[0], rows=-range[1] + 1, cols=-range[2] + 1, translate=True)
        wb.save(save_path)


def unmerge_cells(file_path, save_path):
    wb = openpyxl.load_workbook(file_path, data_only=True)
    sheet = wb.active

    name = os.path.basename(file_path)

    range = get_data_range(sheet)

    if range is not None:
        for row in sheet[range[0]]:
            for cell in row:
                cell.fill = PatternFill(start_color=None, end_color=None, fill_type=None)

        check_range = f'{range[3]}{range[1]}:{range[4]}{range[1]}'
        is_merged = False
        for merged_range in sheet.merged_cells.ranges:
            if merged_range.coord == check_range:
                is_merged = True
                break
        if is_merged:
            name = sheet.cell(row=range[1], column=range[2]).value

        mcr_coord_list = [mcr.coord for mcr in sheet.merged_cells.ranges]
        for mcr in mcr_coord_list:
            min_col, min_row, max_col, max_row = range_boundaries(mcr)
            top_left_cell_value = sheet.cell(row=min_row, column=min_col).value
            sheet.unmerge_cells(mcr)
            if min_col == max_col:
                for row in sheet.iter_rows(min_col=min_col, min_row=min_row, max_col=max_col, max_row=max_row):
                    for cell in row:
                        cell.value = top_left_cell_value
        if is_merged:
            sheet.delete_rows(range[1])
    wb.save(save_path)
    return name


def process(path):
    save_path = path[:-5] + '_prepared.xlsx'
    name = unmerge_cells(path, save_path)
    move(save_path, save_path)
    return save_path, name


def unmerge_sheets(file_path):
    wb = openpyxl.load_workbook(file_path)
    if len(wb.sheetnames) > 1:
        new_pathes = list()
        for sheet_name in wb.sheetnames:
            new_workbook = openpyxl.Workbook()
            new_sheet = new_workbook.active
            sheet = wb[sheet_name]
            for row in sheet.iter_rows(values_only=True):
                new_sheet.append(row)
            new_path = ""
            index = file_path.rfind("/")
            if index != -1:
                new_path = file_path[:index] + "/unmerged_{}/".format(os.path.basename(file_path))

            if not os.path.exists(new_path):
                os.makedirs(new_path)

            new_workbook.save(new_path + sheet_name + '.xlsx')
            new_pathes.append(new_path + sheet_name + '.xlsx')
        return new_pathes
    return [file_path]
