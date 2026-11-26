from collections.abc import Mapping
from decimal import Decimal

from .contracts import MeasureIssue


from dataclasses import dataclass


def form_number(form, sheet, name, minimum, maximum):
    from .service import number

    table = form.get(sheet)
    if not isinstance(table, Mapping):
        raise MeasureIssue(sheet, 'FORM_SECTION_REQUIRED')
    return Decimal(str(number(table.get(name), name, minimum, maximum)))


@dataclass(frozen=True, slots=True)
class CoderLotPrintSheet:
    web_cm_per_minute: Decimal
    nozzle_microns: Decimal
    ink_use_minutes: Decimal
    film_millinewton: Decimal
    reflection_basis_points: Decimal
    camera_snapshots: Decimal

    def fields(self):
        return {
            'speed': float(self.web_cm_per_minute) / 100,
            'head_gap': float(self.nozzle_microns) / 1000,
            'ink_age': float(self.ink_use_minutes) / 60,
            'film_tension': float(self.film_millinewton) / 1000,
            'specular': float(self.reflection_basis_points) / 100,
            'frames': float(self.camera_snapshots),
        }

    def validation(self):
        fields = self.fields()
        speed = fields['speed']
        head_gap = fields['head_gap']
        ink_age = fields['ink_age']
        film_tension = fields['film_tension']
        specular = fields['specular']
        frames = fields['frames']
        film_per_frame = speed/max(1,frames)
        visible_frames = frames*(1-specular/100)
        ink_travel = ink_age*speed*60
        loaded_head = film_tension*head_gap
        alerts = []
        if visible_frames<1.4 and film_per_frame>34:
            alerts.append(('camera_snapshots', 'REFERENCE_FRAME_REQUIRED'))
        if loaded_head>2800 and ink_travel>800000:
            alerts.append(('nozzle_microns', 'INSPECT_NOZZLE_CLEARANCE'))
        if film_tension>205 and specular>66:
            alerts.append(('film_millinewton', 'CHECK_FILM_TENSION_UNIT'))
        return tuple(alerts)


def read_coder_lot_print(form):
    return CoderLotPrintSheet(
        web_cm_per_minute=form_number(form, '喷嘴参数', 'web_cm_per_minute', 4000, 23500),
        nozzle_microns=form_number(form, '喷嘴参数', 'nozzle_microns', 2000, 14000),
        ink_use_minutes=form_number(form, '生产走膜', 'ink_use_minutes', 60, 5700),
        film_millinewton=form_number(form, '生产走膜', 'film_millinewton', 42000, 220000),
        reflection_basis_points=form_number(form, '取像记录', 'reflection_basis_points', 300, 7000),
        camera_snapshots=form_number(form, '取像记录', 'camera_snapshots', 4, 65),
    )


def explicit_rows(form):
    if not isinstance(form, Mapping):
        raise MeasureIssue('form', 'FORM_OBJECT_REQUIRED')
    note = read_coder_lot_print(form)
    return note.fields(), note.validation()


def check_native_history(source):
    if not isinstance(source, Mapping) or 'form' not in source:
        return source
    if any(key in source for key in ('speed', 'head_gap', 'ink_age', 'film_tension', 'specular', 'frames')):
        raise MeasureIssue('form','MIXED_FORM_AND_FLAT_READING')
    converted, flags = explicit_rows(source['form'])
    if flags:
        raise MeasureIssue(*flags[0])
    return {**source, **converted}
