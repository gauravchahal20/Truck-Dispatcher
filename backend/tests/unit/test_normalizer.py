import pytest
from app.services.normalizer import Normalizer

def test_normalize_company_name():
    assert Normalizer.normalize_company_name("Lone Star Eagle Express LLC") == "lone star eagle"
    assert Normalizer.normalize_company_name("Blue Ridge Freight Lines, Inc.") == "blue ridge"
    assert Normalizer.normalize_company_name("Apex Logistics Group Corp.") == "apex"
    assert Normalizer.normalize_company_name("Keystone Heavy Haul L.L.C.") == "keystone heavy haul"

def test_normalize_domain():
    assert Normalizer.normalize_domain("https://www.lonestareaglexpress.com/about-us") == "lonestareaglexpress.com"
    assert Normalizer.normalize_domain("http://midwestapextransport.com:8080") == "midwestapextransport.com"
    assert Normalizer.normalize_domain("keystoneheavyhaul.com") == "keystoneheavyhaul.com"

def test_normalize_phone():
    assert Normalizer.normalize_phone("(214) 555-0182") == "+12145550182"
    assert Normalizer.normalize_phone("1-800-555-0199") == "+18005550199"
    assert Normalizer.normalize_phone("4045550144") == "+14045550144"

def test_format_phone_display():
    assert Normalizer.format_phone_display("+12145550182") == "+1 (214) 555-0182"
    assert Normalizer.format_phone_display("2145550182") == "+1 (214) 555-0182"
    assert Normalizer.format_phone_display("2145550182", include_country_code=False) == "(214) 555-0182"
    assert Normalizer.to_e164("(214) 555-0182") == "+12145550182"
    assert Normalizer.get_dial_link("(214) 555-0182") == "tel:+12145550182"


def test_normalize_usdot():
    assert Normalizer.normalize_usdot("USDOT# 3849102") == "3849102"
    assert Normalizer.normalize_usdot("3512940") == "3512940"
    assert Normalizer.normalize_usdot("003458870") == "3458870"
    assert Normalizer.normalize_usdot(" 00012345 ") == "12345"
    assert Normalizer.normalize_usdot("00000000") is None
    assert Normalizer.normalize_usdot(None) is None

def test_normalize_docket():
    assert Normalizer.normalize_docket("MC1572973") == "1572973"
    assert Normalizer.normalize_docket("MC-424836") == "424836"
    assert Normalizer.normalize_docket("MC066124") == "66124"
    assert Normalizer.normalize_docket("781620") == "781620"
    assert Normalizer.normalize_docket("") is None
    assert Normalizer.normalize_docket("MC-000123") == "123"
    assert Normalizer.normalize_docket(None) is None

def test_normalize_email():
    assert Normalizer.normalize_email("  Dispatch@AcmeTrucking.com ") == "dispatch@acmetrucking.com"
    assert Normalizer.normalize_email("invalid-email-string") is None

def test_normalize_state():
    assert Normalizer.normalize_state("Texas") == "TX"
    assert Normalizer.normalize_state("tx") == "TX"
    assert Normalizer.normalize_state("California") == "CA"
    assert Normalizer.normalize_state("OH") == "OH"
