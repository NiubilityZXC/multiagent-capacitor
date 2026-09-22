"""Every canonical field must be checked through independent access paths."""
from types import SimpleNamespace

import pytest

from experiments.audit_cap import ren_target_workbook as target
from experiments.audit_cap.ren_workbook_reader import schema_rows
from tests.test_ren_target_workbook import book, fixture
from tests.test_ren_workbook_reader import ALLOWED


FIELDS = [(name, column) for name, size in [('step', 8), ('cycle', 5), ('record_1', 9)]
          for column in range(size)]


@pytest.mark.parametrize('name,column', FIELDS)
def test_each_field_reconstructed_from_cells_and_rows(name, column):
    xlrd = pytest.importorskip('xlrd')
    data = book(fixture(True))
    schema = schema_rows(data, ALLOWED)
    class Module:
        def open_workbook(self, **kwargs):
            result = xlrd.open_workbook(**kwargs)
            read_sheet = result.sheet_by_index
            def modified(index):
                sheet = read_sheet(index)
                if sheet.name == name:
                    original = sheet.cell
                    def cell(row, col):
                        cell = original(row, col)
                        if row == 1 and col == column:
                            value = '0:00:09' if cell.ctype == 1 else cell.value + 7
                            return SimpleNamespace(ctype=cell.ctype, value=value)
                        return cell
                    sheet.cell = cell
                return sheet
            result.sheet_by_index = modified
            return result
    with pytest.raises(ValueError, match='mismatch'):
        list(target.events(data, ALLOWED, schema, Module()))


def test_late_parser_warning_cannot_complete():
    xlrd = pytest.importorskip('xlrd')
    data = book(fixture())
    schema = schema_rows(data, ALLOWED)
    class Module:
        def open_workbook(self, **kwargs):
            result = xlrd.open_workbook(**kwargs)
            drop = result.unload_sheet
            def unload(index):
                drop(index)
                if index == 2:
                    kwargs['logfile'].write('synthetic late warning')
            result.unload_sheet = unload
            return result
    with pytest.raises(ValueError, match='parser warning'):
        list(target.events(data, ALLOWED, schema, Module()))
