import openpyxl
from openpyxl.utils.cell import range_boundaries


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
        return data_range, start_row, start_col
    else:
        return None


def move(file_path, save_path):
    wb = openpyxl.load_workbook(file_path)
    sheet = wb.active
    range = get_data_range(sheet)
    if range:
        sheet.move_range(range[0], rows=-range[1] + 1, cols=-range[2] + 1, translate=True)
        wb.save(save_path)


def unmerge(file_path, save_path):
    wb = openpyxl.load_workbook(file_path)
    for st_name in wb.sheetnames:
        st = wb[st_name]
        mcr_coord_list = [mcr.coord for mcr in st.merged_cells.ranges]
        for mcr in mcr_coord_list:
            min_col, min_row, max_col, max_row = range_boundaries(mcr)
            top_left_cell_value = st.cell(row=min_row, column=min_col).value
            st.unmerge_cells(mcr)
            if min_col == max_col:
                for row in st.iter_rows(min_col=min_col, min_row=min_row, max_col=max_col, max_row=max_row):
                    for cell in row:
                        cell.value = top_left_cell_value
    sheet = wb.active
    sheet.title = "Sheet1"
    wb.save(save_path)


def process(path):
    save_path = path[:-5] + '_prep.xlsx'
    unmerge(path, save_path)
    move(save_path, save_path)
    return  save_path


