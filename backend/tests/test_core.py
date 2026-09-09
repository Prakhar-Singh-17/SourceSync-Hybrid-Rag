"""Tests for the pure retrieval logic in app.core.

Every test here runs offline: no Qdrant, no Gemini, no API key. That is the
point of keeping app.core free of I/O.
"""

import io
import unittest
import zipfile

from app.core.chunking import split_code, split_prose
from app.core.documents import Page, extract_pages, passages_from_document
from app.core.errors import SourceError, SourceTooLarge
from app.core.fusion import reciprocal_rank_fusion
from app.core.models import Passage, Retrieved
from app.core.repository import (
    eligible_members,
    passages_from_file,
    validate_github_url,
)
from app.core.sparse import sparse_vector, term_id, tokenize


def passage(identifier: str) -> Retrieved:
    return Retrieved(id=identifier, text=identifier, source_name="test")


class FusionTests(unittest.TestCase):
    def test_rrf_scores_match_the_formula(self) -> None:
        fused = reciprocal_rank_fusion([passage("a")], [passage("b")], k=60)
        self.assertAlmostEqual(fused[0].fused_score, 1 / 61)
        self.assertAlmostEqual(fused[1].fused_score, 1 / 61)

    def test_agreement_between_retrievers_wins(self) -> None:
        # "b" is second in both lists; "a" and "c" are first in only one each.
        dense = [passage("a"), passage("b")]
        sparse = [passage("c"), passage("b")]
        fused = reciprocal_rank_fusion(dense, sparse)
        self.assertEqual(fused[0].id, "b")
        self.assertAlmostEqual(fused[0].fused_score, 1 / 62 + 1 / 62)

    def test_fusion_records_where_each_passage_came_from(self) -> None:
        fused = reciprocal_rank_fusion([passage("a")], [passage("b"), passage("a")])
        found = {item.id: item for item in fused}
        self.assertEqual((found["a"].dense_rank, found["a"].sparse_rank), (1, 2))
        self.assertEqual((found["b"].dense_rank, found["b"].sparse_rank), (None, 1))

    def test_limit_truncates_the_merged_ranking(self) -> None:
        dense = [passage("a"), passage("b"), passage("c")]
        self.assertEqual(len(reciprocal_rank_fusion(dense, [], limit=2)), 2)

    def test_empty_inputs_produce_no_results(self) -> None:
        self.assertEqual(reciprocal_rank_fusion([], []), [])


class SparseVectorTests(unittest.TestCase):
    def test_term_ids_are_stable_across_processes(self) -> None:
        # Regression guard: the built-in hash() is randomised per process, which
        # would silently break every stored sparse vector on restart.
        self.assertEqual(term_id("session"), term_id("session"))
        self.assertNotEqual(term_id("session"), term_id("cookie"))

    def test_identifiers_are_split_into_subwords(self) -> None:
        tokens = tokenize("set_session_cookie getUserName")
        self.assertIn("set_session_cookie", tokens)
        self.assertIn("session", tokens)
        self.assertIn("getusername", tokens)
        self.assertIn("user", tokens)

    def test_stop_words_and_single_characters_are_dropped(self) -> None:
        self.assertEqual(tokenize("the a of x"), [])

    def test_term_frequency_saturates(self) -> None:
        weights = [sparse_vector("qdrant " * count)[1][0] for count in (1, 2, 3, 4)]
        self.assertEqual(weights, sorted(weights), "more occurrences must weigh more")
        # Each additional occurrence adds less than the one before it.
        gains = [later - earlier for earlier, later in zip(weights, weights[1:])]
        self.assertTrue(all(b < a for a, b in zip(gains, gains[1:])), gains)
        # However often a term repeats, its weight is bounded by k1 + 1.
        self.assertLess(sparse_vector("qdrant " * 1000)[1][0], 2.2)

    def test_empty_text_produces_an_empty_vector(self) -> None:
        self.assertEqual(sparse_vector("the the the"), ([], []))


class ChunkingTests(unittest.TestCase):
    def test_prose_passages_overlap(self) -> None:
        passages = split_prose("alpha " * 500, chunk_size=120, overlap=20)
        self.assertGreater(len(passages), 1)
        self.assertTrue(set(passages[0].split()) & set(passages[1].split()))

    def test_prose_passages_respect_the_size_limit(self) -> None:
        passages = split_prose("word " * 2000, chunk_size=200, overlap=20)
        self.assertTrue(all(len(item) <= 200 for item in passages))

    def test_code_is_never_split_mid_line(self) -> None:
        source = "\n".join(f"line_{index} = {index}" for index in range(200))
        original = set(source.splitlines())
        passages = split_code(source, chunk_size=200, overlap_lines=2)
        self.assertGreater(len(passages), 1)
        for item in passages:
            for line in item.splitlines():
                self.assertIn(line, original)

    def test_pathologically_long_lines_are_wrapped(self) -> None:
        passages = split_code("x" * 5000, chunk_size=1000)
        self.assertTrue(all(len(item) <= 1000 for item in passages))

    def test_blank_input_produces_no_passages(self) -> None:
        self.assertEqual(split_prose("   \n\n  "), [])
        self.assertEqual(split_code("   \n\n  "), [])

    def test_invalid_overlap_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            split_prose("text", chunk_size=100, overlap=100)


class DocumentTests(unittest.TestCase):
    def test_text_documents_become_a_single_unnumbered_page(self) -> None:
        pages = extract_pages(b"SourceSync test document", ".txt")
        self.assertEqual(pages, [Page(number=None, text="SourceSync test document")])

    def test_non_utf8_text_is_rejected(self) -> None:
        with self.assertRaises(SourceError):
            extract_pages(b"\xff\xfe invalid", ".txt")

    def test_unsupported_extensions_are_rejected(self) -> None:
        with self.assertRaises(SourceError):
            extract_pages(b"data", ".docx")

    def test_oversized_documents_are_rejected(self) -> None:
        with self.assertRaises(SourceTooLarge):
            extract_pages(b"x" * (16 * 1024 * 1024), ".txt")

    def test_passages_carry_their_page_number(self) -> None:
        pages = [Page(number=1, text="alpha " * 100), Page(number=2, text="beta " * 100)]
        passages = passages_from_document(pages, "report.pdf")
        self.assertEqual({item.page_number for item in passages}, {1, 2})
        self.assertTrue(all(item.source_name == "report.pdf" for item in passages))

    def test_embedding_text_includes_the_location(self) -> None:
        item = Passage(text="body", index=0, source_name="report.pdf", page_number=7)
        self.assertTrue(item.embedding_text.startswith("# report.pdf (page 7)"))


class RepositoryTests(unittest.TestCase):
    def test_valid_urls_are_normalised(self) -> None:
        result = validate_github_url("https://github.com/owner/repository.git")
        self.assertEqual(result["url"], "https://github.com/owner/repository")
        self.assertEqual(result["name"], "owner/repository")

    def test_non_github_and_malformed_urls_are_rejected(self) -> None:
        for url in (
            "https://example.com/owner/repository",
            "http://github.com/owner/repository",
            "https://github.com/owner",
            "https://github.com/owner/repository/tree/main",
            "https://github.com/owner/repository?tab=readme",
        ):
            with self.subTest(url=url), self.assertRaises(SourceError):
                validate_github_url(url)

    def test_generated_and_binary_files_are_skipped(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("repo/README", "docs")
            archive.writestr("repo/src/main.py", "value = 1")
            archive.writestr("repo/node_modules/package.js", "ignored")
            archive.writestr("repo/package-lock.json", "{}")
            archive.writestr("repo/image.png", b"binary")
        with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as archive:
            self.assertEqual(eligible_members(archive), ["repo/README", "repo/src/main.py"])

    def test_the_archive_root_directory_is_stripped_from_paths(self) -> None:
        passages = passages_from_file("owner-repo-abc123/src/main.py", "value = 1", "owner/repo")
        self.assertEqual(passages[0].file_path, "src/main.py")


if __name__ == "__main__":
    unittest.main()
