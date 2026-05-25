import os
import pytest
from unittest.mock import MagicMock
from reviewer.context_fetcher import (
    extract_imports_js,
    extract_imports_ts,
    extract_imports_php,
    extract_imports,
    language_for_path,
    parse_changed_paths,
    is_ignored,
    JSPathResolver,
    PHPPathResolver,
    ContextFetcher,
    estimate_tokens,
    check_context_window,
    ContextTooLargeError,
    CONTEXT_WINDOWS,
)


def test_language_for_path_js():
    assert language_for_path("src/handler.js") == "javascript"
    assert language_for_path("src/handler.mjs") == "javascript"
    assert language_for_path("src/handler.jsx") == "javascript"


def test_language_for_path_ts():
    assert language_for_path("src/types.ts") == "typescript"
    assert language_for_path("src/types.tsx") == "tsx"


def test_language_for_path_php():
    assert language_for_path("src/Service.php") == "php"


def test_language_for_path_unsupported():
    assert language_for_path("main.go") is None
    assert language_for_path("README.md") is None


def test_extract_imports_js_basic():
    assert extract_imports_js("import { foo } from './utils';") == {"./utils"}


def test_extract_imports_js_default():
    assert extract_imports_js("import foo from './foo';") == {"./foo"}


def test_extract_imports_js_namespace():
    assert extract_imports_js("import * as x from 'pkg';") == {"pkg"}


def test_extract_imports_js_dynamic():
    assert extract_imports_js("const m = import('./dyn');") == {"./dyn"}


def test_extract_imports_js_reexport():
    assert extract_imports_js("export { a } from './re';") == {"./re"}


def test_extract_imports_js_string_literal_is_not_import():
    src = 'const s = "import x from \'y\'";'
    assert extract_imports_js(src) == set()


def test_extract_imports_ts_type_only():
    assert extract_imports_ts("import type { User } from './models';") == {"./models"}


def test_extract_imports_php_simple():
    assert extract_imports_php("<?php use App\\Services\\UserService;") == {"App\\Services\\UserService"}


def test_extract_imports_php_grouped():
    assert extract_imports_php("<?php use App\\{A, B};") == {"App\\A", "App\\B"}


def test_extract_imports_php_grouped_nested():
    result = extract_imports_php("<?php use App\\Sub\\{X\\Y, Z};")
    assert result == {"App\\Sub\\X\\Y", "App\\Sub\\Z"}


def test_extract_imports_php_aliased_use():
    """Regression: `use Foo\\Bar as Baz;` previously added both `Foo\\Bar` and
    the alias `Baz` to the import set. The alias is not a resolvable namespace
    and caused wasted resolution attempts. Now only the source namespace is
    extracted."""
    result = extract_imports_php("<?php use App\\Services\\UserService as US;")
    assert result == {"App\\Services\\UserService"}


def test_extract_imports_php_grouped_with_alias():
    """Regression: grouped imports with aliases (`use App\\{Foo, Bar as B};`)
    previously yielded `App\\Foo` and `App\\Bar as B` (the literal " as B"
    suffix included in the namespace). Now the alias is stripped."""
    result = extract_imports_php("<?php use App\\{Foo, Bar as B};")
    assert result == {"App\\Foo", "App\\Bar"}


def test_extract_imports_dispatches_by_path():
    assert extract_imports("import x from './a';", "src/x.js") == {"./a"}
    assert extract_imports("<?php use A\\B;", "src/x.php") == {"A\\B"}
    assert extract_imports("package main", "src/x.go") == set()


def test_parse_changed_paths_extracts_b_side():
    diff = (
        "diff --git a/src/handler.js b/src/handler.js\n"
        "index 1..2 100644\n"
        "--- a/src/handler.js\n"
        "+++ b/src/handler.js\n"
        "@@ -1 +1,2 @@\n"
        "+console.log('hi');\n"
        "diff --git a/src/Service.php b/src/Service.php\n"
        "--- a/src/Service.php\n"
        "+++ b/src/Service.php\n"
    )
    assert parse_changed_paths(diff) == ["src/handler.js", "src/Service.php"]


def test_is_ignored_matches_bare_and_nested():
    assert is_ignored("package-lock.json", ["package-lock.json"])
    assert is_ignored("frontend/package-lock.json", ["package-lock.json"])
    assert not is_ignored("src/handler.js", ["package-lock.json"])


def test_js_resolver_relative(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "utils.js").write_text("export const x = 1;")
    (tmp_path / "src" / "handler.js").write_text("import {x} from './utils';")
    resolver = JSPathResolver(str(tmp_path), lambda p: os.path.isfile(os.path.join(str(tmp_path), p)))
    resolved = resolver.resolve("./utils", "src/handler.js")
    assert resolved == os.path.normpath("src/utils.js")


def test_js_resolver_tsconfig_alias(tmp_path):
    (tmp_path / "tsconfig.json").write_text(
        '{"compilerOptions": {"baseUrl": ".", "paths": {"@app/*": ["src/*"]}}}'
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "utils.ts").write_text("export const x = 1;")
    resolver = JSPathResolver(str(tmp_path), lambda p: os.path.isfile(os.path.join(str(tmp_path), p)))
    resolved = resolver.resolve("@app/utils", "src/handler.ts")
    assert resolved == os.path.normpath("src/utils.ts")


def test_js_resolver_preserves_urls_in_tsconfig_values(tmp_path):
    """Regression: the JSONC comment stripper previously truncated URLs in
    string values because `//.*$` matched the `//` after the protocol scheme.
    A tsconfig with a URL value in a path target must still parse and resolve
    relative aliases correctly."""
    (tmp_path / "tsconfig.json").write_text(
        '{\n'
        '  // a real comment that should be stripped\n'
        '  "compilerOptions": {\n'
        '    "baseUrl": ".",\n'
        '    "paths": {"@app/*": ["src/*"]},\n'
        '    "_docs": "see https://example.com/docs for details"\n'
        '  }\n'
        '}\n'
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "utils.ts").write_text("export const x = 1;")
    resolver = JSPathResolver(str(tmp_path), lambda p: os.path.isfile(os.path.join(str(tmp_path), p)))
    assert resolver.resolve("@app/utils", "src/handler.ts") == os.path.normpath("src/utils.ts")


def test_js_resolver_unresolved_returns_none(tmp_path):
    resolver = JSPathResolver(str(tmp_path), lambda p: os.path.isfile(os.path.join(str(tmp_path), p)))
    assert resolver.resolve("nonexistent-package", "src/x.js") is None


def test_js_resolver_index_file(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "utils").mkdir()
    (tmp_path / "src" / "utils" / "index.ts").write_text("")
    (tmp_path / "src" / "handler.ts").write_text("")
    resolver = JSPathResolver(str(tmp_path), lambda p: os.path.isfile(os.path.join(str(tmp_path), p)))
    assert resolver.resolve("./utils", "src/handler.ts") == os.path.normpath("src/utils/index.ts")


def test_php_resolver_psr4(tmp_path):
    (tmp_path / "composer.json").write_text(
        '{"autoload": {"psr-4": {"App\\\\": "src/"}}}'
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "Services").mkdir()
    (tmp_path / "src" / "Services" / "UserService.php").write_text("<?php")
    resolver = PHPPathResolver(str(tmp_path), lambda p: os.path.isfile(os.path.join(str(tmp_path), p)))
    resolved = resolver.resolve("App\\Services\\UserService")
    assert resolved == os.path.normpath("src/Services/UserService.php")


def test_php_resolver_unresolved_returns_none(tmp_path):
    resolver = PHPPathResolver(str(tmp_path), lambda p: os.path.isfile(os.path.join(str(tmp_path), p)))
    assert resolver.resolve("Foo\\Bar\\Baz") is None


def test_php_resolver_bare_namespace_returns_none(tmp_path):
    (tmp_path / "composer.json").write_text(
        '{"autoload": {"psr-4": {"App\\\\": "src/"}}}'
    )
    (tmp_path / "src").mkdir()
    resolver = PHPPathResolver(str(tmp_path), lambda p: os.path.isfile(os.path.join(str(tmp_path), p)))
    assert resolver.resolve("App") is None
    assert resolver.resolve("App\\") is None


def _make_config(*, changed=False, related=False, depth=1):
    cfg = MagicMock()
    cfg.fetch_changed_full = changed
    cfg.fetch_related_files = related
    cfg.fetch_related_depth = depth
    return cfg


def _make_vcs(file_map: dict, sha: str = "head-sha"):
    vcs = MagicMock()
    vcs.head_sha = sha
    vcs.get_file_content.side_effect = lambda path, ref: file_map.get(path)
    return vcs


def test_fetch_for_diff_no_op_when_features_off(tmp_path):
    diff = "diff --git a/src/a.js b/src/a.js\n"
    vcs = _make_vcs({"src/a.js": "// a"})
    fetcher = ContextFetcher(vcs, _make_config(), ignore_patterns=[], repo_root=str(tmp_path))
    assert fetcher.fetch_for_diff(diff) == {}
    vcs.get_file_content.assert_not_called()


def test_fetch_for_diff_changed_only(tmp_path):
    diff = "diff --git a/src/a.js b/src/a.js\ndiff --git a/src/b.js b/src/b.js\n"
    vcs = _make_vcs({"src/a.js": "// a", "src/b.js": "// b"})
    fetcher = ContextFetcher(
        vcs, _make_config(changed=True), ignore_patterns=[], repo_root=str(tmp_path),
    )
    result = fetcher.fetch_for_diff(diff)
    assert result == {"src/a.js": "// a", "src/b.js": "// b"}
    assert vcs.get_file_content.call_count == 2


def test_fetch_for_diff_aiignore_blocks(tmp_path):
    diff = "diff --git a/package-lock.json b/package-lock.json\ndiff --git a/src/a.js b/src/a.js\n"
    vcs = _make_vcs({"src/a.js": "// a", "package-lock.json": "{}"})
    fetcher = ContextFetcher(
        vcs, _make_config(changed=True),
        ignore_patterns=["package-lock.json"],
        repo_root=str(tmp_path),
    )
    result = fetcher.fetch_for_diff(diff)
    assert "src/a.js" in result
    assert "package-lock.json" not in result


def test_fetch_for_diff_related_follows_one_hop(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "utils.js").write_text("")
    (tmp_path / "src" / "handler.js").write_text("")
    diff = "diff --git a/src/handler.js b/src/handler.js\n"
    vcs = _make_vcs({
        "src/handler.js": "import {x} from './utils';",
        "src/utils.js": "export const x = 1;",
    })
    fetcher = ContextFetcher(
        vcs, _make_config(changed=True, related=True, depth=1),
        ignore_patterns=[], repo_root=str(tmp_path),
    )
    result = fetcher.fetch_for_diff(diff)
    assert result["src/handler.js"] == "import {x} from './utils';"
    assert result[os.path.normpath("src/utils.js")] == "export const x = 1;"


def test_fetch_for_diff_dedupes_shared_import(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "utils.js").write_text("")
    (tmp_path / "src" / "a.js").write_text("")
    (tmp_path / "src" / "b.js").write_text("")
    diff = "diff --git a/src/a.js b/src/a.js\ndiff --git a/src/b.js b/src/b.js\n"
    vcs = _make_vcs({
        "src/a.js": "import {x} from './utils';",
        "src/b.js": "import {x} from './utils';",
        "src/utils.js": "export const x = 1;",
    })
    fetcher = ContextFetcher(
        vcs, _make_config(changed=True, related=True, depth=1),
        ignore_patterns=[], repo_root=str(tmp_path),
    )
    fetcher.fetch_for_diff(diff)
    call_paths = [call.args[0] for call in vcs.get_file_content.call_args_list]
    assert call_paths.count(os.path.normpath("src/utils.js")) == 1


def test_fetch_for_diff_unsupported_language_fallback(tmp_path):
    diff = "diff --git a/main.go b/main.go\n"
    vcs = _make_vcs({"main.go": "package main"})
    fetcher = ContextFetcher(
        vcs, _make_config(changed=True, related=True, depth=2),
        ignore_patterns=[], repo_root=str(tmp_path),
    )
    result = fetcher.fetch_for_diff(diff)
    assert result == {"main.go": "package main"}


def test_estimate_tokens_is_quarter_of_length():
    assert estimate_tokens("a" * 400) == 100
    assert estimate_tokens("") == 0


def test_check_context_window_passes_under_limit():
    check_context_window("system", "user", "gpt-4o")


def test_check_context_window_raises_over_limit():
    huge_user = "x" * (CONTEXT_WINDOWS["gpt-4o"] * 4)
    with pytest.raises(ContextTooLargeError):
        check_context_window("", huge_user, "gpt-4o")


def test_check_context_window_uses_default_for_unknown_model():
    huge = "x" * (200_000 * 4)
    with pytest.raises(ContextTooLargeError):
        check_context_window("", huge, "totally-unknown-model")


def test_overflow_error_names_real_env_var():
    """Regression guard: the actionable error message MUST name AI_FETCH_CHANGED_FULL
    (the real variable), not the AI_FETCH_FULL_FILES typo that previously sent
    operators chasing a variable that does not exist in Config."""
    huge = "x" * (CONTEXT_WINDOWS["gpt-4o"] * 4)
    with pytest.raises(ContextTooLargeError) as exc_info:
        check_context_window("", huge, "gpt-4o")
    message = str(exc_info.value)
    assert "AI_FETCH_CHANGED_FULL" in message
    assert "AI_FETCH_FULL_FILES" not in message
