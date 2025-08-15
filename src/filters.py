import arrow
from flask import Blueprint


bp = Blueprint("filters", "filters")

@bp.app_template_filter("string_to_color")
def string_to_color(input_string):
    hash_value = 5381
    for char in input_string:
        hash_value = ((hash_value << 5) + hash_value) + ord(char)
    
    color_value = hash_value & 0xFFFFFF
    hex_color = f"#{color_value:06x}"
    
    return hex_color

@bp.app_template_filter("humanize")
def humanize(datestring):
    return arrow.get(datestring).humanize()