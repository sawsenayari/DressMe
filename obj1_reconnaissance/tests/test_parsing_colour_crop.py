import numpy as np
from PIL import Image
from recognition.parsing import parse_answer
from recognition.colour import dominant_colours
from recognition.imaging import check_crop, normalise_crop


def test_parse_valid_and_synonyms():
    a = parse_answer('```json\n{"category":"Hoodie","color":"navy","gender":"men","season":"autumn","occasion":"sports","confidence":85}\n```')
    assert a["valid"] and a["category"] == "sweater" and a["color"] == "blue" and a["gender"] == "male" and a["season"] == "fall" and a["confidence"] == 0.85


def test_parse_invalid():
    assert not parse_answer("no json here")["valid"]
    assert not parse_answer('{"category":"spaceship","confidence":0.9}')["valid"]


def test_colour_witness_primary_colours():
    for rgb, name in (((200, 30, 30), "red"), ((30, 60, 200), "blue"), ((20, 20, 20), "black"), ((30, 160, 60), "green")):
        im = Image.new("RGB", (512, 512), (255, 255, 255)); im.paste(Image.new("RGB", (300, 300), rgb), (100, 100))
        assert dominant_colours(im)[0][0] == name, (rgb, dominant_colours(im))


def test_crop_quality_and_normalise():
    empty = Image.new("RGB", (512, 512), (255, 255, 255)); assert "garment_too_small_or_empty" in check_crop(empty)["reasons"]
    full = Image.new("RGB", (512, 512), (10, 10, 10)); assert "background_not_removed" in check_crop(full)["reasons"]
    n = normalise_crop(Image.new("RGB", (300, 600), (0, 0, 0))); assert n.size == (512, 512)
