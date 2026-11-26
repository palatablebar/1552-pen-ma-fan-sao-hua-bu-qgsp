from dataclasses import replace
from statistics import mean, median
from collections import Counter
from math import fsum

from .contracts import FEATURE_NAMES, FEATURE_KEYS, RAW_KEYS


def current_visible_frames(vector):
    specular = vector.input_values[4]
    frames = vector.input_values[5]
    return float(frames*(1-specular/100))


def compare_visible_frames(training, target):
    usual_visible_frames = take_sample(training, current_visible_frames)
    recent_visible_frames = take_sample(target, current_visible_frames)
    if len(usual_visible_frames) < 4 or not recent_visible_frames:
        return {'作业量': '按反光折算可见帧', '有效读数': len(recent_visible_frames), '判断': '参考不足'}
    anchor_visible_frames = median(usual_visible_frames)
    measured_visible_frames = median(recent_visible_frames)
    ordered_visible_frames = sorted(usual_visible_frames)
    low_visible_frames, high_visible_frames = ordered_visible_frames[len(ordered_visible_frames)//10], ordered_visible_frames[(len(ordered_visible_frames)*9)//10]
    change_visible_frames = measured_visible_frames-anchor_visible_frames
    outside_visible_frames = sum(value<low_visible_frames or value>high_visible_frames for value in recent_visible_frames)
    return {'作业量': '按反光折算可见帧', '训练参考': round(anchor_visible_frames, 4), '现场中位': round(measured_visible_frames, 4),
            '变动': round(change_visible_frames, 4), '越界量': outside_visible_frames, '有效读数': len(recent_visible_frames)}


def current_frame_gap(vector):
    frames = vector.input_values[5]
    return float(max(0,21-frames))


def compare_frame_gap(training, target):
    usual_frame_gap = take_sample(training, current_frame_gap)
    recent_frame_gap = take_sample(target, current_frame_gap)
    if len(usual_frame_gap) < 4 or not recent_frame_gap:
        return {'作业量': '返扫基准帧缺口', '有效读数': len(recent_frame_gap), '判断': '参考不足'}
    anchor_frame_gap = median(usual_frame_gap)
    measured_frame_gap = median(recent_frame_gap)
    ordered_frame_gap = sorted(usual_frame_gap)
    low_frame_gap, high_frame_gap = ordered_frame_gap[len(ordered_frame_gap)//10], ordered_frame_gap[(len(ordered_frame_gap)*9)//10]
    change_frame_gap = measured_frame_gap-anchor_frame_gap
    outside_frame_gap = sum(value<low_frame_gap or value>high_frame_gap for value in recent_frame_gap)
    return {'作业量': '返扫基准帧缺口', '训练参考': round(anchor_frame_gap, 4), '现场中位': round(measured_frame_gap, 4),
            '变动': round(change_frame_gap, 4), '越界量': outside_frame_gap, '有效读数': len(recent_frame_gap)}


def current_shipping_speed(vector):
    speed = vector.input_values[0]
    return float(speed/60)


def compare_shipping_speed(training, target):
    usual_shipping_speed = take_sample(training, current_shipping_speed)
    recent_shipping_speed = take_sample(target, current_shipping_speed)
    if len(usual_shipping_speed) < 4 or not recent_shipping_speed:
        return {'作业量': '每秒膜带移动', '有效读数': len(recent_shipping_speed), '判断': '参考不足'}
    anchor_shipping_speed = median(usual_shipping_speed)
    measured_shipping_speed = median(recent_shipping_speed)
    band_shipping_speed = max(1.0, abs(anchor_shipping_speed)*.2, median(abs(value-anchor_shipping_speed) for value in usual_shipping_speed))
    change_shipping_speed = (measured_shipping_speed-anchor_shipping_speed) / band_shipping_speed
    outside_shipping_speed = sum(abs(value-anchor_shipping_speed)>2.5*band_shipping_speed for value in recent_shipping_speed)
    return {'作业量': '每秒膜带移动', '训练参考': round(anchor_shipping_speed, 4), '现场中位': round(measured_shipping_speed, 4),
            '变动': round(change_shipping_speed, 4), '越界量': outside_shipping_speed, '有效读数': len(recent_shipping_speed)}


def current_film_offset(vector):
    film_tension = vector.input_values[3]
    return float(film_tension-115)


def compare_film_offset(training, target):
    usual_film_offset = take_sample(training, current_film_offset)
    recent_film_offset = take_sample(target, current_film_offset)
    if len(usual_film_offset) < 4 or not recent_film_offset:
        return {'作业量': '牵引力偏离', '有效读数': len(recent_film_offset), '判断': '参考不足'}
    anchor_film_offset = median(usual_film_offset)
    measured_film_offset = median(recent_film_offset)
    ordered_film_offset = sorted(usual_film_offset)
    low_film_offset, high_film_offset = ordered_film_offset[len(ordered_film_offset)//10], ordered_film_offset[(len(ordered_film_offset)*9)//10]
    change_film_offset = measured_film_offset-anchor_film_offset
    outside_film_offset = sum(value<low_film_offset or value>high_film_offset for value in recent_film_offset)
    return {'作业量': '牵引力偏离', '训练参考': round(anchor_film_offset, 4), '现场中位': round(measured_film_offset, 4),
            '变动': round(change_film_offset, 4), '越界量': outside_film_offset, '有效读数': len(recent_film_offset)}


def current_ink_buffer(vector):
    ink_age = vector.input_values[2]
    return float(95-ink_age)


def compare_ink_buffer(training, target):
    usual_ink_buffer = take_sample(training, current_ink_buffer)
    recent_ink_buffer = take_sample(target, current_ink_buffer)
    if len(usual_ink_buffer) < 4 or not recent_ink_buffer:
        return {'作业量': '距下次冲洗小时', '有效读数': len(recent_ink_buffer), '判断': '参考不足'}
    anchor_ink_buffer = median(usual_ink_buffer)
    measured_ink_buffer = median(recent_ink_buffer)
    ordered_ink_buffer = sorted(usual_ink_buffer)
    low_ink_buffer, high_ink_buffer = ordered_ink_buffer[len(ordered_ink_buffer)//10], ordered_ink_buffer[(len(ordered_ink_buffer)*9)//10]
    change_ink_buffer = measured_ink_buffer-anchor_ink_buffer
    outside_ink_buffer = sum(value<low_ink_buffer or value>high_ink_buffer for value in recent_ink_buffer)
    return {'作业量': '距下次冲洗小时', '训练参考': round(anchor_ink_buffer, 4), '现场中位': round(measured_ink_buffer, 4),
            '变动': round(change_ink_buffer, 4), '越界量': outside_ink_buffer, '有效读数': len(recent_ink_buffer)}


def current_spray_span(vector):
    speed = vector.input_values[0]
    head_gap = vector.input_values[1]
    return float(head_gap*speed/100)


def compare_spray_span(training, target):
    usual_spray_span = take_sample(training, current_spray_span)
    recent_spray_span = take_sample(target, current_spray_span)
    if len(usual_spray_span) < 4 or not recent_spray_span:
        return {'作业量': '喷距与传动乘积', '有效读数': len(recent_spray_span), '判断': '参考不足'}
    anchor_spray_span = median(usual_spray_span)
    measured_spray_span = median(recent_spray_span)
    band_spray_span = max(1.0, abs(anchor_spray_span)*.2, median(abs(value-anchor_spray_span) for value in usual_spray_span))
    change_spray_span = (measured_spray_span-anchor_spray_span) / band_spray_span
    outside_spray_span = sum(abs(value-anchor_spray_span)>2.5*band_spray_span for value in recent_spray_span)
    return {'作业量': '喷距与传动乘积', '训练参考': round(anchor_spray_span, 4), '现场中位': round(measured_spray_span, 4),
            '变动': round(change_spray_span, 4), '越界量': outside_spray_span, '有效读数': len(recent_spray_span)}


def current_speckle_cost(vector):
    head_gap = vector.input_values[1]
    specular = vector.input_values[4]
    return float(specular*head_gap/14)


def compare_speckle_cost(training, target):
    usual_speckle_cost = take_sample(training, current_speckle_cost)
    recent_speckle_cost = take_sample(target, current_speckle_cost)
    if len(usual_speckle_cost) < 4 or not recent_speckle_cost:
        return {'作业量': '反光与喷高代理', '有效读数': len(recent_speckle_cost), '判断': '参考不足'}
    anchor_speckle_cost = median(usual_speckle_cost)
    measured_speckle_cost = median(recent_speckle_cost)
    band_speckle_cost = max(1.0, abs(anchor_speckle_cost)*.2, median(abs(value-anchor_speckle_cost) for value in usual_speckle_cost))
    change_speckle_cost = (measured_speckle_cost-anchor_speckle_cost) / band_speckle_cost
    outside_speckle_cost = sum(abs(value-anchor_speckle_cost)>2.5*band_speckle_cost for value in recent_speckle_cost)
    return {'作业量': '反光与喷高代理', '训练参考': round(anchor_speckle_cost, 4), '现场中位': round(measured_speckle_cost, 4),
            '变动': round(change_speckle_cost, 4), '越界量': outside_speckle_cost, '有效读数': len(recent_speckle_cost)}


def current_expected_read_rate(vector):
    speed = vector.input_values[0]
    specular = vector.input_values[4]
    frames = vector.input_values[5]
    return float(60*frames*(1-specular/100)/speed)


def compare_expected_read_rate(training, target):
    usual_expected_read_rate = take_sample(training, current_expected_read_rate)
    recent_expected_read_rate = take_sample(target, current_expected_read_rate)
    if len(usual_expected_read_rate) < 4 or not recent_expected_read_rate:
        return {'作业量': '单分钟每帧可见性', '有效读数': len(recent_expected_read_rate), '判断': '参考不足'}
    anchor_expected_read_rate = median(usual_expected_read_rate)
    measured_expected_read_rate = median(recent_expected_read_rate)
    ordered_expected_read_rate = sorted(usual_expected_read_rate)
    low_expected_read_rate, high_expected_read_rate = ordered_expected_read_rate[len(ordered_expected_read_rate)//10], ordered_expected_read_rate[(len(ordered_expected_read_rate)*9)//10]
    change_expected_read_rate = measured_expected_read_rate-anchor_expected_read_rate
    outside_expected_read_rate = sum(value<low_expected_read_rate or value>high_expected_read_rate for value in recent_expected_read_rate)
    return {'作业量': '单分钟每帧可见性', '训练参考': round(anchor_expected_read_rate, 4), '现场中位': round(measured_expected_read_rate, 4),
            '变动': round(change_expected_read_rate, 4), '越界量': outside_expected_read_rate, '有效读数': len(recent_expected_read_rate)}


def take_sample(vectors, measure):
    return tuple(measure(record) for record in vectors if not record.missing)


def measure_print_quality_terms_band(history, daybook):
    yield compare_visible_frames(history, daybook)
    yield compare_frame_gap(history, daybook)
    yield compare_shipping_speed(history, daybook)
    yield compare_film_offset(history, daybook)
    yield compare_ink_buffer(history, daybook)
    yield compare_spray_span(history, daybook)
    yield compare_speckle_cost(history, daybook)
    yield compare_expected_read_rate(history, daybook)


def evaluate_shift(training, current):
    return list(measure_print_quality_terms_band(training, current))
