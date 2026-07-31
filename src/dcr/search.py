"""FTS5 search engine for Windsurf Cascade conversations.

Provides full-text search across rounds, steps, and checkpoints
with BM25 ranking, filters (project, date, type), and snippets.
Auto-syncs the database before search to ensure fresh results.
Archived conversations (whose .pb file was removed) are preserved
and remain searchable — the database is a permanent archive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dcr.indexer import DEFAULT_DB_PATH, Indexer


@dataclass
class SearchResult:
    """A single search match."""

    conversation_id: int
    cascade_id: str
    title: str
    project_path: str
    git_branch: str
    model: str
    created_at: float | None
    updated_at: float | None
    source_table: str  # "rounds", "steps", or "checkpoints"
    row_id: int
    round_number: int | None = None
    step_index: int | None = None
    snippet: str = ""
    score: float = 0.0


@dataclass
class SearchResults:
    """Collection of search results with metadata."""

    query: str
    total: int
    results: list[SearchResult] = field(default_factory=list)
    sync_info: dict[str, Any] | None = None


class SearchEngine:
    """FTS5 search engine with filters and auto-sync."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        auto_sync: bool = True,
    ) -> None:
        """Initialize the search engine.

        Args:
            db_path: Path to the SQLite database.
            auto_sync: If True, sync database before each search.
        """
        self.indexer = Indexer(db_path=db_path)
        self.auto_sync = auto_sync

    def _ensure_synced(self) -> dict[str, Any] | None:
        """Sync the database if auto_sync is enabled."""
        if not self.auto_sync:
            return None
        return self.indexer.sync()

    def search(
        self,
        query: str,
        limit: int = 50,
        project: str | None = None,
        date_from: float | None = None,
        date_to: float | None = None,
        source_table: str | None = None,
        source_type: str | None = None,
    ) -> SearchResults:
        """Search conversations with FTS5 and optional filters.

        Args:
            query: FTS5 query string (supports MATCH syntax).
            limit: Maximum number of results.
            project: Filter by project path (exact or prefix match).
            date_from: Filter conversations created after this timestamp.
            date_to: Filter conversations created before this timestamp.
            source_table: Restrict search to one table ("rounds", "steps",
                "checkpoints", "tool_calls"). If None, searches all four.
            source_type: Restrict to source type ("cascade" or "devin_local").
                If None, searches both sources.

        Returns:
            SearchResults with ranked matches.
        """
        sync_info = self._ensure_synced()
        self.indexer.init_schema()

        # Build the conversation filter conditions
        conv_filters: list[str] = []
        params: list[Any] = []

        if project:
            conv_filters.append("(c.project_path = ? OR c.project_path LIKE ?)")
            params.extend([project, project + "%"])

        if date_from is not None:
            conv_filters.append("c.created_at >= ?")
            params.append(date_from)

        if date_to is not None:
            conv_filters.append("c.created_at <= ?")
            params.append(date_to)

        if source_type:
            conv_filters.append("c.source_type = ?")
            params.append(source_type)

        # Determine which tables to search
        tables: list[str]
        if source_table:
            tables = [source_table]
        else:
            tables = ["rounds", "steps", "checkpoints", "tool_calls"]

        # Escape query for safe FTS5 usage
        fts_query = self._escape_fts_query(query)
        if not fts_query:
            return SearchResults(query=query, total=0, sync_info=sync_info)

        all_results: list[SearchResult] = []

        for table in tables:
            results = self._search_table(
                table, fts_query, conv_filters, params, limit
            )
            all_results.extend(results)

        # Sort by score (BM25: lower is better in SQLite, so negate)
        all_results.sort(key=lambda r: r.score)

        # Deduplicate: keep best score per (conversation_id, source_table, row_id)
        seen: set[tuple[int, str, int]] = set()
        unique: list[SearchResult] = []
        for r in all_results:
            key = (r.conversation_id, r.source_table, r.row_id)
            if key not in seen:
                seen.add(key)
                unique.append(r)

        truncated = unique[:limit]

        return SearchResults(
            query=query,
            total=len(unique),
            results=truncated,
            sync_info=sync_info,
        )

    def _search_table(
        self,
        table: str,
        fts_query: str,
        conv_filters: list[str],
        params: list[Any],
        limit: int,
    ) -> list[SearchResult]:
        """Search a single FTS5 table and join with conversations."""
        fts_table = f"{table}_fts"

        # Build table-specific select columns
        if table == "rounds":
            table_cols = "t.round_number, NULL as step_index"
            join_col = "t.conversation_id"
        elif table == "steps":
            table_cols = "NULL as round_number, t.step_index"
            join_col = "t.conversation_id"
        elif table == "checkpoints":
            table_cols = "NULL as round_number, t.step_index"
            join_col = "t.conversation_id"
        elif table == "tool_calls":
            table_cols = "NULL as round_number, NULL as step_index"
            join_col = "t.conversation_id"
        else:
            return []

        sql = f"""
            SELECT bm25({fts_table}) as score,
                   c.id, c.cascade_id, c.title, c.project_path,
                   c.git_branch, c.model, c.created_at, c.updated_at,
                   t.id as row_id, {table_cols},
                   snippet({fts_table}, 0, '>>>', '<<<', '...', 20) as snippet
            FROM {fts_table}
            JOIN {table} t ON t.id = {fts_table}.rowid
            JOIN conversations c ON c.id = {join_col}
            WHERE {fts_table} MATCH ?
            {"AND " + " AND ".join(conv_filters) if conv_filters else ""}
            ORDER BY score
            LIMIT ?
        """

        # Params: fts_query first, then conv filter params, then limit
        all_params = [fts_query] + list(params) + [limit]

        try:
            cur = self.indexer.conn.execute(sql, all_params)
            columns = [d[0] for d in cur.description]
            results: list[SearchResult] = []
            for row in cur.fetchall():
                row_dict = dict(zip(columns, row))
                results.append(
                    SearchResult(
                        conversation_id=row_dict["id"],
                        cascade_id=row_dict["cascade_id"],
                        title=row_dict["title"] or "",
                        project_path=row_dict["project_path"] or "",
                        git_branch=row_dict["git_branch"] or "",
                        model=row_dict["model"] or "",
                        created_at=row_dict["created_at"],
                        updated_at=row_dict["updated_at"],
                        source_table=table,
                        row_id=row_dict["row_id"],
                        round_number=row_dict["round_number"],
                        step_index=row_dict["step_index"],
                        snippet=row_dict["snippet"] or "",
                        score=row_dict["score"],
                    )
                )
            return results
        except Exception:
            return []

    @staticmethod
    def _escape_fts_query(query: str) -> str:
        """Escape a query string for safe FTS5 MATCH.

        Wraps each token in double quotes to prevent FTS5 syntax injection.
        Preserves basic operators (AND, OR, NOT) if uppercase.
        """
        if not query or not query.strip():
            return ""

        # Split on whitespace but preserve operators
        tokens = query.split()
        escaped: list[str] = []

        for token in tokens:
            upper = token.upper()
            if upper in ("AND", "OR", "NOT"):
                escaped.append(upper)
            elif token.startswith('"') and token.endswith('"'):
                escaped.append(token)
            else:
                # Wrap in quotes, escape internal quotes
                clean = token.replace('"', '""')
                escaped.append(f'"{clean}"')

        return " ".join(escaped)

    def search_conversations(
        self,
        query: str,
        limit: int = 20,
        project: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search and return one result per conversation (best match).

        Args:
            query: Search query.
            limit: Max conversations to return.
            project: Filter by project path.

        Returns:
            List of dicts with conversation info and best matching snippet.
        """
        results = self.search(query, limit=limit * 3, project=project)

        seen: set[int] = set()
        convs: list[dict[str, Any]] = []
        for r in results.results:
            if r.conversation_id in seen:
                continue
            seen.add(r.conversation_id)
            convs.append(
                {
                    "conversation_id": r.conversation_id,
                    "cascade_id": r.cascade_id,
                    "title": r.title,
                    "project_path": r.project_path,
                    "git_branch": r.git_branch,
                    "model": r.model,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                    "best_snippet": r.snippet,
                    "source_table": r.source_table,
                    "score": r.score,
                }
            )
            if len(convs) >= limit:
                break

        return convs

    def close(self) -> None:
        """Close the underlying database connection."""
        self.indexer.close()

    def __enter__(self) -> SearchEngine:
        self.indexer.init_schema()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
