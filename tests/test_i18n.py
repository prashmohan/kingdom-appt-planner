"""Tests for internationalization (i18n) and translation bug reporting."""

from app.i18n import (
    LANG_COOKIE_NAME,
    SUPPORTED_LANGUAGES,
    get_locale,
    get_text_dir,
    load_catalogs,
    normalize_lang,
    translate,
)


def test_catalog_completeness_and_key_parity():
    """Verify all supported language catalogs load and have identical keys."""
    catalogs = load_catalogs()
    assert set(catalogs.keys()) == set(SUPPORTED_LANGUAGES.keys())

    en_keys = set(catalogs["en"].keys())
    assert len(en_keys) > 100

    for lang_code, catalog in catalogs.items():
        missing = en_keys - set(catalog.keys())
        extra = set(catalog.keys()) - en_keys
        assert not missing, f"Catalog '{lang_code}' is missing keys: {missing}"
        assert not extra, f"Catalog '{lang_code}' has unexpected keys: {extra}"
        for k, v in catalog.items():
            assert isinstance(v, str) and len(v.strip()) > 0, (
                f"Empty translation for key '{k}' in '{lang_code}'"
            )


def test_normalize_lang_variants():
    """Verify language tag normalization handles region subtags and invalid inputs."""
    assert normalize_lang("en") == "en"
    assert normalize_lang("en-US") == "en"
    assert normalize_lang("es_MX") == "es"
    assert normalize_lang("es-419") == "es"
    assert normalize_lang("zh-CN") == "zh"
    assert normalize_lang("zh_Hans") == "zh"
    assert normalize_lang("ar-SA") == "ar"
    assert normalize_lang("AR") == "ar"
    assert normalize_lang("fr-FR") is None
    assert normalize_lang("") is None
    assert normalize_lang(None) is None


def test_translate_helper_and_fallbacks():
    """Verify translate() outside request context, with kwargs, and missing keys."""
    assert get_locale() == "en"
    assert get_text_dir("en") == "ltr"
    assert get_text_dir("ar") == "rtl"

    assert translate("index_heading", lang="en") == "Kingdom Appointment Planner"
    assert translate("index_heading", lang="es") == "Planificador de Turnos del Reino"
    assert translate("index_heading", lang="zh") == "王国官职预约规划器"
    assert translate("index_heading", lang="ar") == "مخطط مواعيد المملكة"

    # Format placeholders
    assert translate("common_kingdom_num", lang="es", server_id=1052) == "Reino #1052"
    assert translate("common_kingdom_num", lang="zh", server_id=1052) == "王国 #1052"

    # Missing format arg gracefully returns unformatted template
    assert "{server_id}" in translate("common_kingdom_num", lang="en", wrong_arg=1)

    # Unknown key falls back to key name
    assert translate("non_existent_key_xyz", lang="es") == "non_existent_key_xyz"


def test_locale_detection_priority_and_cookie(client):
    """Verify ?lang= query param, cookie persistence, and Accept-Language detection."""
    # 1. Default is English (ltr)
    resp = client.get("/")
    html = resp.get_data(as_text=True)
    assert '<html lang="en" dir="ltr"' in html
    assert "Kingdom Appointment Planner" in html

    # 2. Browser Accept-Language auto-detection (Spanish)
    resp_es = client.get("/", headers={"Accept-Language": "es-MX,es;q=0.9,en;q=0.8"})
    html_es = resp_es.get_data(as_text=True)
    assert '<html lang="es" dir="ltr"' in html_es
    assert "Planificador de Turnos del Reino" in html_es

    # 3. Browser Accept-Language auto-detection (Simplified Chinese)
    resp_zh = client.get("/", headers={"Accept-Language": "zh-CN,zh;q=0.9"})
    html_zh = resp_zh.get_data(as_text=True)
    assert '<html lang="zh" dir="ltr"' in html_zh
    assert "王国官职预约规划器" in html_zh

    # 4. Explicit ?lang=ar sets cookie and renders RTL
    resp_ar = client.get("/?lang=ar", headers={"Accept-Language": "en-US,en;q=0.9"})
    html_ar = resp_ar.get_data(as_text=True)
    assert '<html lang="ar" dir="rtl"' in html_ar
    assert "مخطط مواعيد المملكة" in html_ar
    set_cookie_header = resp_ar.headers.get("Set-Cookie", "")
    assert f"{LANG_COOKIE_NAME}=ar" in set_cookie_header

    # 5. Subsequent request without ?lang= uses persisted kvk_lang cookie
    resp_persisted = client.get("/", headers={"Accept-Language": "en-US,en;q=0.9"})
    assert '<html lang="ar" dir="rtl"' in resp_persisted.get_data(as_text=True)


def test_localized_event_and_admin_pages(client, test_event):
    """Verify player form, schedules, success pages, and admin dashboard render in all languages."""
    uid = test_event["uid"]
    secret = test_event["admin_secret"]

    for lang, expected_form_heading, expected_admin_heading in [
        ("es", "Formulario de Inscripción", "Panel de Administración"),
        ("zh", "玩家预约报名表", "管理员控制台"),
        ("ar", "نموذج التسجيل", "لوحة تحكم المسؤول"),
    ]:
        # Player Form
        pf = client.get(f"/event/{uid}?lang={lang}")
        assert pf.status_code == 200
        pf_html = pf.get_data(as_text=True)
        assert expected_form_heading in pf_html
        assert 'id="kvk-lang-switcher"' in pf_html
        assert 'id="translation-report-modal"' in pf_html
        assert 'translate="no"' in pf_html

        # Public Schedule
        ps = client.get(f"/event/{uid}/schedule?lang={lang}")
        assert ps.status_code == 200
        assert f'lang="{lang}"' in ps.get_data(as_text=True)

        # Locked / Finalized Appointments
        la = client.get(f"/event/{uid}/finalized?lang={lang}")
        assert la.status_code == 200
        assert f'lang="{lang}"' in la.get_data(as_text=True)

        # Submission Success
        ss = client.get(f"/submission-success?lang={lang}")
        assert ss.status_code == 200
        assert f'lang="{lang}"' in ss.get_data(as_text=True)

        # Event Created Success
        es_resp = client.get(f"/success/{uid}?secret={secret}&lang={lang}")
        assert es_resp.status_code == 200
        assert f'lang="{lang}"' in es_resp.get_data(as_text=True)

        # Admin Dashboard
        adm = client.get(f"/admin/{uid}?secret={secret}&lang={lang}")
        assert adm.status_code == 200
        assert expected_admin_heading in adm.get_data(as_text=True)


def test_translation_report_submission_and_superadmin_management(client, app):
    """Verify submitting translation bug reports and managing them in Superadmin."""
    app.config["SUPERADMIN_SECRET"] = "super_secret_i18n_test"

    # 1. Missing payload or fields returns 400
    bad_resp1 = client.post("/api/translation_report", json={})
    assert bad_resp1.status_code == 400

    bad_resp2 = client.post(
        "/api/translation_report",
        json={"lang": "es", "original_text": "Only original"},
    )
    assert bad_resp2.status_code == 400

    # 2. Valid JSON submission (translation issue via /api/translation_report)
    good_resp = client.post(
        "/api/translation_report",
        json={
            "report_type": "translation",
            "lang": "ar",
            "page_url": "/event/test_event_123",
            "original_text": "الذهب الخالص",
            "suggested_text": "ذهب حقيقي",
            "context_notes": "In-game Arabic item label",
        },
    )
    assert good_resp.status_code == 201
    data = good_resp.get_json()
    assert data["status"] == "ok"
    assert data["report_type"] == "translation"
    report_id = data["id"]

    # 2b. Submit a general Bug Report and a Feature Request via /api/feedback
    bug_resp = client.post(
        "/api/feedback",
        json={
            "report_type": "bug",
            "lang": "es",
            "page_url": "/event/test_event_123",
            "title": "Mobile slot grid scroll jump",
            "description": "Tapping slot 24 scrolls to top on iOS Safari",
            "context_notes": "iPhone 15 iOS 18",
        },
    )
    assert bug_resp.status_code == 201
    assert bug_resp.get_json()["report_type"] == "bug"

    feat_resp = client.post(
        "/api/feedback",
        json={
            "report_type": "feature",
            "lang": "zh",
            "page_url": "/admin/test_event_123",
            "title": "Discord webhook notification",
            "description": "Send finalized schedule to Discord automatically",
        },
    )
    assert feat_resp.status_code == 201
    assert feat_resp.get_json()["report_type"] == "feature"

    # 3. Authenticate as Superadmin and verify all 3 reports are visible
    auth_resp = client.get(
        "/superadmin?secret=super_secret_i18n_test", follow_redirects=True
    )
    assert auth_resp.status_code == 200
    sa_html = auth_resp.get_data(as_text=True)
    assert "User Feedback, Bug Reports &amp; Translation Issues" in sa_html
    assert "الذهب الخالص" in sa_html
    assert "ذهب حقيقي" in sa_html
    assert "In-game Arabic item label" in sa_html
    assert "Mobile slot grid scroll jump" in sa_html
    assert "Discord webhook notification" in sa_html
    assert "🐛 Bug" in sa_html
    assert "💡 Feature" in sa_html
    assert "🌐 i18n" in sa_html
    assert "3 Open" in sa_html

    # 4. Resolve the translation report
    res_resp = client.post(
        f"/superadmin/translation_reports/{report_id}/resolve",
        follow_redirects=True,
    )
    assert res_resp.status_code == 200
    assert "Resolved" in res_resp.get_data(as_text=True)
    assert "2 Open" in res_resp.get_data(as_text=True)

    # 5. Reopen the report
    reopen_resp = client.post(
        f"/superadmin/translation_reports/{report_id}/resolve",
        follow_redirects=True,
    )
    assert reopen_resp.status_code == 200
    assert "3 Open" in reopen_resp.get_data(as_text=True)

    # 6. Non-existent report returns 404
    not_found = client.post("/superadmin/translation_reports/99999/resolve")
    assert not_found.status_code == 404

    # 7. Delete the report
    del_resp = client.post(
        f"/superadmin/translation_reports/{report_id}/delete",
        follow_redirects=True,
    )
    assert del_resp.status_code == 200
    assert "ذهب حقيقي" not in del_resp.get_data(as_text=True)
