import io
import unittest
import zipfile

from PIL import Image

from checker.engine import (
    MAX_FILE_BYTES,
    MAX_TEXT_BYTES,
    InvalidUpload,
    docx_text,
    evaluate,
    fingerprint,
    inspect_upload,
    validate_rule,
    word_count,
)


def rule(kind="word_count", slot="article", **config):
    return {"id": 1, "revision": 1, "kind": kind, "slot": slot, "config": config,
            "approved": True, "ambiguous": False}


def text_asset(text):
    return inspect_upload("article.txt", text.encode(), "article")


def image_bytes(width=100, height=50, fmt="PNG"):
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "#137b70").save(buffer, fmt)
    return buffer.getvalue()


def make_docx(xml=None, extra=None):
    buffer = io.BytesIO()
    xml = xml or '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Hello world</w:t></w:r></w:p></w:body></w:document>'
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr("word/document.xml", xml)
        for path, value in (extra or {}).items():
            z.writestr(path, value)
    return buffer.getvalue()


class RuleTests(unittest.TestCase):
    def test_word_count_inclusive_boundaries(self):
        r = rule(min=3, max=5)
        for n, status in [(2, "failed"), (3, "passed"), (4, "passed"), (5, "passed"), (6, "failed")]:
            with self.subTest(n=n):
                self.assertEqual(evaluate(r, text_asset("word " * n))["status"], status)

    def test_minimum_only(self):
        self.assertEqual(evaluate(rule(min=2), text_asset("one two three"))["status"], "passed")

    def test_maximum_only(self):
        self.assertEqual(evaluate(rule(max=2), text_asset("one two"))["status"], "passed")

    def test_zero_is_a_bound(self):
        self.assertEqual(evaluate(rule(max=0), text_asset("one"))["status"], "failed")

    def test_unicode_hyphens_and_punctuation(self):
        self.assertEqual(word_count("  café  don't post-event 2026\nstudent’s _work_ 🎉"), 6)

    def test_phrase_case_unicode_and_whitespace(self):
        r = rule("required_phrase", phrase="CS Expo 2026")
        self.assertEqual(evaluate(r, text_asset("Join ＣＳ\nexpo   2026!"))["status"], "passed")
        self.assertEqual(evaluate(r, text_asset("CS Expo 2027"))["status"], "failed")

    def test_phrase_does_not_remove_punctuation(self):
        r = rule("required_phrase", phrase="#CSExpo2026")
        self.assertEqual(evaluate(r, text_asset("CSExpo2026"))["status"], "failed")

    def test_missing_for_each_rule(self):
        for r in [rule(min=1), rule("dimensions", "image", width=1, height=1),
                  rule("manual", "image"), rule("required_file"), rule("required_phrase", phrase="Expo")]:
            with self.subTest(kind=r["kind"]):
                self.assertEqual(evaluate(r, None)["status"], "missing")

    def test_unapproved_or_ambiguous_cannot_pass(self):
        for flag, value in [("approved", False), ("ambiguous", True)]:
            r = rule(min=1)
            r[flag] = value
            self.assertEqual(evaluate(r, text_asset("one"))["status"], "needs_review")

    def test_subjective_check_never_auto_passes(self):
        r = rule("manual", "image")
        asset = inspect_upload("image.png", image_bytes(), "image")
        self.assertEqual(evaluate(r, asset)["status"], "needs_review")

    def test_dimensions_exact_boundaries(self):
        r = rule("dimensions", "image", width=100, height=50)
        for w, h, status in [(99, 50, "failed"), (100, 50, "passed"), (101, 50, "failed"), (100, 51, "failed")]:
            with self.subTest(w=w, h=h):
                self.assertEqual(evaluate(r, inspect_upload("p.png", image_bytes(w, h), "image"))["status"], status)

    def test_present_file_passes_required_file_check(self):
        self.assertEqual(evaluate(rule("required_file"), text_asset("Hello"))["status"], "passed")

    def test_invalid_configuration_needs_review(self):
        cases = [rule(min=5, max=2), rule(), rule(max=True), rule("dimensions", "article", width=1, height=1),
                 rule("required_phrase", phrase=""), rule("unknown"), rule(min=-1),
                 rule("dimensions", "image", width=0, height=10), rule("dimensions", "image", width=20000001, height=1)]
        for r in cases:
            with self.subTest(rule=r):
                self.assertEqual(evaluate(r, None)["status"], "needs_review")

    def test_wrong_config_type_rejected(self):
        with self.assertRaises(ValueError):
            validate_rule("word_count", "article", [])

    def test_fingerprint_stable_across_dictionary_order(self):
        self.assertEqual(fingerprint([{"id": 1, "revision": 2}], []),
                         fingerprint([{"revision": 2, "id": 1}], []))

    def test_fingerprint_changes_on_requirement_change(self):
        self.assertNotEqual(fingerprint([rule(min=1)], []), fingerprint([rule(min=2)], []))

    def test_fingerprint_changes_on_file_change(self):
        self.assertNotEqual(fingerprint([], [text_asset("one")]), fingerprint([], [text_asset("two")]))

    def test_fingerprint_changes_on_approval_and_revision(self):
        r = rule(min=1)
        original = fingerprint([r], [])
        r["approved"] = False
        self.assertNotEqual(original, fingerprint([r], []))
        r["approved"] = True
        r["revision"] += 1
        self.assertNotEqual(original, fingerprint([r], []))


class UploadTests(unittest.TestCase):
    def test_txt_utf8_and_bom(self):
        result = inspect_upload("draft.TXT", b"\xef\xbb\xbfHello world", "caption")
        self.assertEqual(result["metadata"]["words"], 2)
        self.assertEqual(len(result["sha256"]), 64)

    def test_file_size_at_limit_and_one_byte_over(self):
        # A valid padded JPEG stays small when decoded; bound applies to original bytes.
        image = image_bytes(fmt="JPEG")
        inspect_upload("p.jpg", image + b" " * (MAX_FILE_BYTES - len(image)), "image")
        with self.assertRaisesRegex(InvalidUpload, "5 MiB"):
            inspect_upload("p.jpg", image + b" " * (MAX_FILE_BYTES + 1 - len(image)), "image")

    def test_text_size_at_limit_and_one_byte_over(self):
        inspect_upload("p.txt", b"a" + b" " * (MAX_TEXT_BYTES - 1), "article")
        with self.assertRaisesRegex(InvalidUpload, "2 MiB"):
            inspect_upload("p.txt", b"a" * (MAX_TEXT_BYTES + 1), "article")

    def test_invalid_text(self):
        for data in [b"", b"  \n ", b"invalid\xff", b"binary\x00text"]:
            with self.subTest(data=data), self.assertRaises(InvalidUpload):
                inspect_upload("p.txt", data, "article")

    def test_wrong_slot_and_extension(self):
        for name, data, slot in [("a.exe", b"x", "article"), ("x.jpg", image_bytes(), "article"),
                                 ("x.txt", b"hello", "image"), ("x.txt", b"hello", "other")]:
            with self.subTest(name=name, slot=slot), self.assertRaises(InvalidUpload):
                inspect_upload(name, data, slot)

    def test_spoofed_image_rejected(self):
        for data in [b"<script>alert(1)</script>", b"\x89PNG\r\n\x1a\nnot an image"]:
            with self.assertRaises(InvalidUpload):
                inspect_upload("image.png", data, "image")

    def test_mismatched_image_extension(self):
        with self.assertRaisesRegex(InvalidUpload, "extension"):
            inspect_upload("image.jpg", image_bytes(), "image")

    def test_jpeg_accepted(self):
        self.assertEqual(inspect_upload("image.jpeg", image_bytes(fmt="JPEG"), "logo")["metadata"]["width"], 100)

    def test_truncated_image(self):
        with self.assertRaises(InvalidUpload):
            inspect_upload("image.png", image_bytes()[:50], "image")

    def test_image_pixel_limit(self):
        with self.assertRaisesRegex(InvalidUpload, "20 megapixels"):
            inspect_upload("image.png", image_bytes(5000, 4001), "image")

    def test_animated_png_rejected(self):
        buffer = io.BytesIO()
        first = Image.new("RGB", (3, 3), "red")
        first.save(buffer, "PNG", save_all=True, append_images=[Image.new("RGB", (3, 3), "blue")], duration=100)
        with self.assertRaisesRegex(InvalidUpload, "Animated"):
            inspect_upload("animated.png", buffer.getvalue(), "image")

    def test_docx_text(self):
        self.assertEqual(inspect_upload("a.docx", make_docx(), "article")["metadata"]["text"], "Hello world")

    def test_docx_table_paragraphs(self):
        xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>First</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Second</w:t><w:tab/><w:t>third</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>'
        self.assertEqual(docx_text(make_docx(xml)), "First\nSecond third")

    def test_docx_wrong_archive(self):
        for data in [b"not a zip", image_bytes()]:
            with self.assertRaises(InvalidUpload):
                inspect_upload("a.docx", data, "article")

    def test_docx_path_traversal_encrypted_macros_and_external_links(self):
        cases = [{"../escape": "x"}, {"word/vbaProject.bin": "x"},
                 {"word/embeddings/object.bin": "x"},
                 {"word/_rels/document.xml.rels": '<Relationships><Relationship TargetMode="External" Target="https://example.com"/></Relationships>'}]
        for extra in cases:
            with self.subTest(extra=list(extra)), self.assertRaises(InvalidUpload):
                docx_text(make_docx(extra=extra))

    def test_docx_entity_rejected_in_utf8_and_utf16(self):
        xml = '<!DOCTYPE x [<!ENTITY danger "expanded">]><x>&danger;</x>'
        for data in [xml, xml.encode("utf-16")]:
            with self.assertRaisesRegex(InvalidUpload, "DTD/entity"):
                docx_text(make_docx(data))

    def test_docx_expansion_limit(self):
        with self.assertRaisesRegex(InvalidUpload, "Expanded"):
            docx_text(make_docx(extra={"large.txt": b"x" * (20 * 1024 * 1024)}))

    def test_docx_too_many_parts(self):
        with self.assertRaisesRegex(InvalidUpload, "too many"):
            docx_text(make_docx(extra={f"part{i}.xml": "<x/>" for i in range(201)}))

    def test_docx_missing_body(self):
        with self.assertRaisesRegex(InvalidUpload, "body"):
            docx_text(make_docx('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>'))

    def test_docx_tracked_changes_and_fields_rejected(self):
        for element in ["ins", "del", "txbxContent", "fldChar", "instrText", "altChunk"]:
            xml = f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:{element}/></w:body></w:document>'
            with self.subTest(element=element), self.assertRaises(InvalidUpload):
                docx_text(make_docx(xml))


if __name__ == "__main__":
    unittest.main()
