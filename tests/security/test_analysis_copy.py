from jobfindsme.privacy import create_analysis_copy


def test_analysis_copy_redacts_selected_fields_without_mutating_source() -> None:
    source = "姓名：张三\n电话：13800138000\n邮箱：me@example.com\nPython"

    copy = create_analysis_copy(
        source_version_id="version-1",
        text=source,
        redacted_fields={"name", "phone", "email"},
    )

    assert "张三" not in copy.text
    assert "13800138000" not in copy.text
    assert "me@example.com" not in copy.text
    assert "Python" in copy.text
    assert "张三" in source


def test_analysis_copy_can_explicitly_keep_identity_fields() -> None:
    source = "邮箱：me@example.com"
    copy = create_analysis_copy(
        source_version_id="version-1",
        text=source,
        redacted_fields=set(),
    )
    assert copy.text == source


def test_common_phone_and_legacy_id_formats_are_redacted() -> None:
    source = "电话：138-0013-8000\n身份证：110101900101001"
    copy = create_analysis_copy(source_version_id="v1", text=source)
    assert "138-0013-8000" not in copy.text
    assert "110101900101001" not in copy.text


def test_project_name_and_repository_address_are_not_identity_labels() -> None:
    source = "项目名字：智能招聘系统\n项目地址：https://github.com/acme/repo"
    copy = create_analysis_copy(
        source_version_id="v1",
        text=source,
        redacted_fields={"name", "address"},
    )
    assert copy.text == source
