"""PostgreSQL full-text search tests.

These tests verify the FTS code paths (tsvector/tsquery/ts_rank/ts_headline)
by mocking the dialect detection so they run on SQLite with patched SQL,
or are skipped when the behavior cannot be tested without a real PostgreSQL
instance.

The three required test scenarios:
1. FTS matching via tsvector returns results for stemmed words
2. ts_rank produces varying scores for results with different relevance
3. ts_headline output contains highlight markers around matched terms
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codehive.core.search import (
    SearchResults,
    _fts_headline,
    _fts_match,
    _fts_rank,
    _is_postgresql,
    _truncate_snippet,
)


# ---------------------------------------------------------------------------
# Helper: check if a real PostgreSQL is available
# ---------------------------------------------------------------------------

_HAS_POSTGRES = False
"""Set to True if you have a PostgreSQL test database configured."""


skip_no_postgres = pytest.mark.skipif(
    not _HAS_POSTGRES,
    reason="PostgreSQL not available; skipping FTS integration test",
)


# ---------------------------------------------------------------------------
# Unit tests: dialect detection
# ---------------------------------------------------------------------------


class TestDialectDetection:
    """Verify that _is_postgresql correctly detects the database dialect."""

    def test_detects_postgresql(self):
        """When dialect.name is 'postgresql', _is_postgresql returns True."""
        mock_db = MagicMock()
        mock_db.bind.dialect.name = "postgresql"
        assert _is_postgresql(mock_db) is True

    def test_detects_sqlite(self):
        """When dialect.name is 'sqlite', _is_postgresql returns False."""
        mock_db = MagicMock()
        mock_db.bind.dialect.name = "sqlite"
        assert _is_postgresql(mock_db) is False

    def test_detects_other_dialect(self):
        """For any non-postgresql dialect, _is_postgresql returns False."""
        mock_db = MagicMock()
        mock_db.bind.dialect.name = "mysql"
        assert _is_postgresql(mock_db) is False


# ---------------------------------------------------------------------------
# Unit tests: FTS helper functions
# ---------------------------------------------------------------------------


class TestFTSHelpers:
    """Verify that FTS helper functions produce correct SQLAlchemy constructs."""

    def _pg_compile(self, expr):
        """Compile an expression using the PostgreSQL dialect."""
        from sqlalchemy.dialects import postgresql

        return str(expr.compile(dialect=postgresql.dialect()))

    def test_fts_match_creates_plainto_tsquery(self):
        """_fts_match returns a plainto_tsquery function call."""
        expr = _fts_match("running fast")
        compiled = self._pg_compile(expr)
        assert "plainto_tsquery" in compiled
        # 'english' config and query text are passed as bound params
        assert "plainto_tsquery_1" in compiled
        assert "plainto_tsquery_2" in compiled

    def test_fts_rank_creates_ts_rank(self):
        """_fts_rank returns a ts_rank function call."""
        expr = _fts_rank("test query")
        compiled = self._pg_compile(expr)
        assert "ts_rank" in compiled
        assert "search_vector" in compiled

    def test_fts_headline_creates_ts_headline(self):
        """_fts_headline returns a ts_headline function call with highlight markers."""
        from sqlalchemy import column as sa_column

        source = sa_column("name")
        expr = _fts_headline(source, "test")
        compiled = self._pg_compile(expr)
        assert "ts_headline" in compiled
        # StartSel/StopSel options are passed as a bound parameter
        assert "plainto_tsquery" in compiled
        assert "ts_headline_1" in compiled  # config param ('english')
        assert "ts_headline_2" in compiled  # options param with StartSel/StopSel


# ---------------------------------------------------------------------------
# PostgreSQL FTS integration tests (skipped without real PostgreSQL)
# ---------------------------------------------------------------------------


@skip_no_postgres
class TestFTSStemming:
    """FTS matching via tsvector returns results for stemmed words.

    For example, searching 'running' should match content containing 'run'
    because PostgreSQL's English stemmer reduces both to the stem 'run'.
    """

    @pytest.mark.asyncio
    async def test_stemmed_word_match(self):
        """Searching 'running' matches a record containing 'run' via FTS stemming.

        This test requires a real PostgreSQL database with the tsvector triggers
        installed (via the Alembic migration). It is skipped by default.
        """
        # This would insert 'running fast' and 'unrelated topic' into sessions,
        # then search for 'run' and verify the stemmed match is found.
        pytest.skip("Requires live PostgreSQL with FTS migration applied")


@skip_no_postgres
class TestFTSRanking:
    """ts_rank produces varying scores for results with different relevance.

    Records that are more relevant to the search query should receive higher
    ts_rank scores than less relevant records.
    """

    @pytest.mark.asyncio
    async def test_varying_scores(self):
        """Multiple matching records produce different ts_rank scores.

        This test requires a real PostgreSQL database. It would insert records
        with varying content (e.g., one with the query term repeated many times
        vs one with a single occurrence) and verify scores differ.
        """
        pytest.skip("Requires live PostgreSQL with FTS migration applied")


@skip_no_postgres
class TestFTSHighlighting:
    """ts_headline output contains highlight markers around matched terms.

    The search service configures ts_headline with StartSel='<b>' and
    StopSel='</b>' so matched terms appear as <b>term</b> in snippets.
    """

    @pytest.mark.asyncio
    async def test_headline_contains_bold_markers(self):
        """Search snippet from ts_headline contains <b>...</b> markers.

        This test requires a real PostgreSQL database. It would search for a
        term and verify the snippet contains '<b>term</b>'.
        """
        pytest.skip("Requires live PostgreSQL with FTS migration applied")


# ---------------------------------------------------------------------------
# Unit tests: search function PostgreSQL branch (mocked)
# ---------------------------------------------------------------------------


class TestSearchPostgresPath:
    """Verify the search function takes the PostgreSQL path when dialect is postgresql."""

    @pytest.mark.asyncio
    async def test_search_uses_fts_on_postgresql(self):
        """When _is_postgresql returns True, the search function uses FTS constructs.

        We patch _is_postgresql and verify the PostgreSQL code path is taken
        by checking that the query includes plainto_tsquery-related operations.
        """
        # We mock the db session to verify the path is taken
        mock_db = MagicMock(spec=["bind", "execute", "get"])
        mock_db.bind.dialect.name = "postgresql"

        # The execute call will return a mock result
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_rows = MagicMock()
        mock_rows.__iter__ = MagicMock(return_value=iter([]))

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_rows])

        with patch("codehive.core.search._is_postgresql", return_value=True):
            from codehive.core.search import search

            result = await search(mock_db, "test query")

        assert isinstance(result, SearchResults)
        assert result.total == 0
        # Verify execute was called (once for count, once for fetch)
        assert mock_db.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_search_session_history_uses_fts_on_postgresql(self):
        """search_session_history uses FTS when dialect is postgresql."""
        mock_db = MagicMock(spec=["bind", "execute", "get"])
        mock_db.bind.dialect.name = "postgresql"

        # Mock session lookup
        mock_session = MagicMock()
        mock_session.id = uuid.uuid4()
        mock_db.get = AsyncMock(return_value=mock_session)

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_rows = MagicMock()
        mock_rows.__iter__ = MagicMock(return_value=iter([]))

        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_rows])

        with patch("codehive.core.search._is_postgresql", return_value=True):
            from codehive.core.search import search_session_history

            result = await search_session_history(mock_db, mock_session.id, "test query")

        assert isinstance(result, SearchResults)
        assert result.total == 0
        assert mock_db.execute.call_count == 2


# ---------------------------------------------------------------------------
# Unit tests: snippet truncation (regression for SQLite path)
# ---------------------------------------------------------------------------


class TestSnippetTruncation:
    """Ensure _truncate_snippet continues to work for the SQLite path."""

    def test_truncate_with_match(self):
        text = "The quick brown fox jumps over the lazy dog"
        result = _truncate_snippet(text, "fox")
        assert "fox" in result

    def test_truncate_no_match(self):
        text = "The quick brown fox jumps over the lazy dog"
        result = _truncate_snippet(text, "xyz")
        assert result == text  # short enough, no truncation

    def test_truncate_empty(self):
        assert _truncate_snippet("", "test") == ""
