from ocforge.catalog import logcheck


def test_clean_log_has_no_findings():
    text = "\n".join(f"boot line {i}: everything is fine" for i in range(20))
    assert logcheck.scan(text) == []


def test_unambiguous_error_flagged_anywhere_in_the_log():
    # Not the last line -- an unambiguous signature is flagged regardless.
    lines = ["line before"] * 10 + ["Couldn't allocate runtime area, error allocating 0x1197b"]
    lines += ["line after"] * 10
    findings = logcheck.scan("\n".join(lines))
    assert len(findings) == 1
    assert findings[0].title == "Couldn't allocate runtime area (KASLR slide)"
    assert findings[0].line_no == 11


def test_kernel_panic_signature():
    text = "some header\npanic(cpu 0 caller 0xffffff801234): a real panic string\nmore"
    findings = logcheck.scan(text)
    assert any(f.title == "Kernel panic" for f in findings)


def test_stall_signature_only_flagged_at_the_end_of_the_log():
    # In the middle -- a completely normal line on any boot, not flagged.
    lines = ["a"] * 20 + ["IOConsoleUsers: gIOScreenLock is unlocked"] + ["b"] * 20
    assert logcheck.scan("\n".join(lines)) == []


def test_stall_signature_flagged_when_its_the_last_line():
    lines = ["a"] * 20 + ["IOConsoleUsers: gIOScreenLock is unlocked"]
    findings = logcheck.scan("\n".join(lines))
    assert len(findings) == 1
    assert findings[0].title == "Stalled at IOConsoleUsers (no display handoff)"


def test_stall_signature_flagged_within_the_trailing_window_with_blank_lines():
    # Trailing blank lines shouldn't count against the "last few lines" window.
    lines = ["a"] * 20 + ["kextd stall[0]: AppleACPICPU waiting on key"] + [""] * 3
    findings = logcheck.scan("\n".join(lines))
    assert len(findings) == 1
    assert findings[0].title == "Stalled waiting on AppleACPICPU (SMC)"


def test_each_signature_reported_at_most_once():
    text = "\n".join(["no vault provided!"] * 5)
    assert len(logcheck.scan(text)) == 1


def test_multiple_distinct_signatures_all_reported():
    text = "no vault provided!\nCannot perform kext summary\nInvalid frame pointer"
    titles = {f.title for f in logcheck.scan(text)}
    assert titles == {"No vault provided", "Cannot perform kext summary", "Invalid frame pointer"}


def test_empty_log_is_fine():
    assert logcheck.scan("") == []
