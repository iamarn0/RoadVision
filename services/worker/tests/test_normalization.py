from app.normalization.plates import normalize_plate


def test_normalize_uppercases_and_strips_punct() -> None:
    result = normalize_plate(" mh-12 ab 1234 ")
    assert result.normalized_plate_text == "MH12AB1234"
    assert result.raw_ocr_text == "mh-12 ab 1234"


def test_normalize_does_not_blindly_map_o_to_zero() -> None:
    result = normalize_plate("MHO2AB1234")
    assert "O" in result.normalized_plate_text
    assert result.normalized_plate_text == "MHO2AB1234"


def test_short_plate_marked_uncertain() -> None:
    result = normalize_plate("AB")
    assert result.uncertain is True
