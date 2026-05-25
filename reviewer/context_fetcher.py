import json
import os
import re
import fnmatch
from typing import Optional


_PARSERS = {}


def _ensure_tree_sitter_available():
    if _PARSERS:
        return
    try:
        import tree_sitter
        import tree_sitter_javascript
        import tree_sitter_typescript
        import tree_sitter_php
    except ImportError as exc:
        raise RuntimeError(
            "tree-sitter packages are required for AI_FETCH_RELATED_FILES. "
            "Install tree-sitter, tree-sitter-javascript, tree-sitter-typescript, "
            "and tree-sitter-php, or unset AI_FETCH_RELATED_FILES."
        ) from exc

    _PARSERS["javascript"] = tree_sitter.Parser(tree_sitter.Language(tree_sitter_javascript.language()))
    _PARSERS["typescript"] = tree_sitter.Parser(tree_sitter.Language(tree_sitter_typescript.language_typescript()))
    _PARSERS["tsx"] = tree_sitter.Parser(tree_sitter.Language(tree_sitter_typescript.language_tsx()))
    _PARSERS["php"] = tree_sitter.Parser(tree_sitter.Language(tree_sitter_php.language_php()))


_JS_TS_EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")
_PHP_EXTENSIONS = (".php",)


def language_for_path(path: str) -> Optional[str]:
    ext = os.path.splitext(path)[1]
    if ext in (".ts",):
        return "typescript"
    if ext in (".tsx",):
        return "tsx"
    if ext in (".js", ".jsx", ".mjs", ".cjs"):
        return "javascript"
    if ext in _PHP_EXTENSIONS:
        return "php"
    return None


def _collect_import_strings(node, out: set):
    if node.type == "import_statement" or node.type == "export_statement":
        for child in node.children:
            if child.type == "string":
                out.add(_string_literal_value(child))
        return
    if node.type == "call_expression":
        # Dynamic import('x')
        callee = node.child_by_field_name("function")
        if callee is not None and callee.text == b"import":
            args = node.child_by_field_name("arguments")
            if args is not None:
                for arg in args.children:
                    if arg.type == "string":
                        out.add(_string_literal_value(arg))
        return
    for child in node.children:
        _collect_import_strings(child, out)


def _string_literal_value(string_node) -> str:
    for child in string_node.children:
        if child.type == "string_fragment":
            return child.text.decode("utf-8", errors="ignore")
    raw = string_node.text.decode("utf-8", errors="ignore")
    if len(raw) >= 2 and raw[0] in ("'", '"', "`") and raw[-1] == raw[0]:
        return raw[1:-1]
    return raw


def _extract_imports(source: str, language: str) -> set:
    _ensure_tree_sitter_available()
    parser = _PARSERS[language]
    tree = parser.parse(source.encode("utf-8"))
    found = set()
    _collect_import_strings(tree.root_node, found)
    return found


def extract_imports_js(source: str) -> set:
    return _extract_imports(source, "javascript")


def extract_imports_ts(source: str) -> set:
    return _extract_imports(source, "typescript")


def extract_imports_tsx(source: str) -> set:
    return _extract_imports(source, "tsx")


def _collect_php_use(node, out: set):
    if node.type == "namespace_use_declaration":
        prefix_name = None
        group_node = None
        clause_nodes = []
        for child in node.children:
            if child.type == "namespace_name":
                prefix_name = child.text.decode("utf-8", errors="ignore")
            elif child.type == "namespace_use_group":
                group_node = child
            elif child.type == "namespace_use_clause":
                clause_nodes.append(child)

        if group_node is not None:
            group_prefix = (prefix_name + "\\") if prefix_name else ""
            for child in group_node.children:
                if child.type == "namespace_use_clause":
                    member = child.text.decode("utf-8", errors="ignore").strip()
                    if member:
                        # Drop any "as Alias" suffix; PHP namespaces have no
                        # spaces, so the first whitespace-delimited token is
                        # always the original namespace path.
                        member = member.split()[0]
                        out.add(group_prefix + member)
            return

        for clause in clause_nodes:
            for grandchild in clause.children:
                if grandchild.type in ("qualified_name", "namespace_name", "name"):
                    out.add(grandchild.text.decode("utf-8", errors="ignore"))
                    # Only the first identifier in the clause is the original
                    # namespace. Subsequent children are the "as Alias" target,
                    # which is not a resolvable namespace specifier.
                    break
        return
    for child in node.children:
        _collect_php_use(child, out)


def extract_imports_php(source: str) -> set:
    _ensure_tree_sitter_available()
    parser = _PARSERS["php"]
    tree = parser.parse(source.encode("utf-8"))
    found = set()
    _collect_php_use(tree.root_node, found)
    return {s.lstrip("\\") for s in found if s}


def extract_imports(source: str, path: str) -> set:
    language = language_for_path(path)
    if language is None:
        return set()
    if language == "php":
        return extract_imports_php(source)
    return _extract_imports(source, language)


_JS_RESOLUTION_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".d.ts")
_JS_INDEX_FILES = tuple(f"index{ext}" for ext in _JS_RESOLUTION_SUFFIXES)


def _load_json_safely(path: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        # Strip JSONC-style comments. The negative lookbehind prevents the
        # `//` in URLs (e.g. `"baseUrl": "https://example.com"`) from being
        # treated as a line comment: URLs always have a letter or `:` before
        # `//`, while real comments start at indentation or after JSON
        # punctuation. This is a heuristic, not a full string-aware parser.
        text = re.sub(r"(?<![a-zA-Z:])//.*?$|/\*.*?\*/", "", text, flags=re.MULTILINE | re.DOTALL)
        return json.loads(text)
    except (OSError, json.JSONDecodeError):
        return None


class JSPathResolver:
    def __init__(self, repo_root: str, file_exists):
        self.repo_root = repo_root
        self._file_exists = file_exists
        self._aliases = self._load_tsconfig_paths()
        self._package_imports = self._load_package_imports()

    def _load_tsconfig_paths(self):
        tsconfig = _load_json_safely(os.path.join(self.repo_root, "tsconfig.json"))
        if not tsconfig:
            return {}
        compiler = tsconfig.get("compilerOptions") or {}
        base_url = compiler.get("baseUrl") or "."
        paths = compiler.get("paths") or {}
        out = {}
        for alias, targets in paths.items():
            normalized_targets = []
            for target in targets:
                normalized_targets.append(os.path.normpath(os.path.join(base_url, target)))
            out[alias] = normalized_targets
        return out

    def _load_package_imports(self):
        package = _load_json_safely(os.path.join(self.repo_root, "package.json"))
        if not package:
            return {}
        imports = package.get("imports") or {}
        return imports if isinstance(imports, dict) else {}

    def resolve(self, specifier: str, from_file: str) -> Optional[str]:
        for alias, targets in self._aliases.items():
            resolved = self._try_alias(specifier, alias, targets)
            if resolved:
                return resolved

        if specifier in self._package_imports:
            candidate = self._package_imports[specifier]
            if isinstance(candidate, str):
                return self._existing_path(candidate.removeprefix("./"))

        if specifier.startswith("."):
            base_dir = os.path.dirname(from_file)
            base = os.path.normpath(os.path.join(base_dir, specifier))
            return self._try_extensions(base)

        return None

    def _try_alias(self, specifier: str, alias: str, targets) -> Optional[str]:
        if alias.endswith("/*") and specifier.startswith(alias[:-1]):
            remainder = specifier[len(alias) - 1:]
            for target in targets:
                base = target.removesuffix("/*").rstrip("/")
                resolved = self._try_extensions(os.path.join(base, remainder.lstrip("/")))
                if resolved:
                    return resolved
        elif alias == specifier:
            for target in targets:
                resolved = self._try_extensions(target)
                if resolved:
                    return resolved
        return None

    def _try_extensions(self, base: str) -> Optional[str]:
        candidates = [base]
        candidates.extend(base + ext for ext in _JS_RESOLUTION_SUFFIXES)
        candidates.extend(os.path.join(base, index) for index in _JS_INDEX_FILES)
        for candidate in candidates:
            normalized = os.path.normpath(candidate)
            if self._file_exists(normalized):
                return normalized
        return None

    def _existing_path(self, candidate: str) -> Optional[str]:
        normalized = os.path.normpath(candidate)
        if self._file_exists(normalized):
            return normalized
        return self._try_extensions(normalized)


class PHPPathResolver:
    def __init__(self, repo_root: str, file_exists):
        self.repo_root = repo_root
        self._file_exists = file_exists
        self._psr4 = self._load_psr4_map()

    def _load_psr4_map(self):
        composer = _load_json_safely(os.path.join(self.repo_root, "composer.json"))
        if not composer:
            return []
        autoload = composer.get("autoload") or {}
        autoload_dev = composer.get("autoload-dev") or {}
        merged = []
        for source in (autoload.get("psr-4"), autoload_dev.get("psr-4")):
            if not isinstance(source, dict):
                continue
            for prefix, target in source.items():
                if isinstance(target, str):
                    merged.append((prefix, [target]))
                elif isinstance(target, list):
                    merged.append((prefix, [t for t in target if isinstance(t, str)]))
        merged.sort(key=lambda item: len(item[0]), reverse=True)
        return merged

    def resolve(self, specifier: str) -> Optional[str]:
        specifier = specifier.lstrip("\\")
        for prefix, targets in self._psr4:
            if not specifier.startswith(prefix):
                continue
            remainder = specifier[len(prefix):]
            if not remainder:
                # Bare namespace import (e.g. `use App;`) has no single file target.
                continue
            relative_path = remainder.replace("\\", "/") + ".php"
            for target in targets:
                candidate = os.path.normpath(os.path.join(target, relative_path))
                if self._file_exists(candidate):
                    return candidate
        return None


_DIFF_HEADER_RE = re.compile(r"^diff --git a/(.*?) b/(.*?)$")


def parse_changed_paths(diff_text: str):
    paths = []
    for line in diff_text.splitlines():
        match = _DIFF_HEADER_RE.match(line.strip())
        if match:
            paths.append(match.group(2))
    return paths


def is_ignored(path: str, patterns) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, f"*/{pattern}"):
            return True
    return False


class ContextFetcher:
    def __init__(self, vcs_provider, config, ignore_patterns, repo_root=None):
        self.vcs = vcs_provider
        self.config = config
        self.ignore_patterns = ignore_patterns
        self.repo_root = repo_root or os.getcwd()
        self._cache = {}
        self._js_resolver = None
        self._php_resolver = None

    def _file_exists(self, repo_relative_path: str) -> bool:
        return os.path.isfile(os.path.join(self.repo_root, repo_relative_path))

    def _ensure_resolvers(self):
        if self._js_resolver is None:
            self._js_resolver = JSPathResolver(self.repo_root, self._file_exists)
        if self._php_resolver is None:
            self._php_resolver = PHPPathResolver(self.repo_root, self._file_exists)

    def _fetch_cached(self, path: str) -> Optional[str]:
        ref = self.vcs.head_sha
        key = (path, ref)
        if key in self._cache:
            return self._cache[key]
        content = self.vcs.get_file_content(path, ref)
        self._cache[key] = content
        return content

    def _resolve_specifier(self, specifier: str, from_file: str) -> Optional[str]:
        language = language_for_path(from_file)
        if language in ("javascript", "typescript", "tsx"):
            return self._js_resolver.resolve(specifier, from_file)
        if language == "php":
            return self._php_resolver.resolve(specifier)
        return None

    def fetch_for_diff(self, diff_text: str) -> dict:
        if not self.config.fetch_changed_full and (
            not self.config.fetch_related_files or self.config.fetch_related_depth == 0
        ):
            return {}

        changed_paths = [
            path for path in parse_changed_paths(diff_text)
            if not is_ignored(path, self.ignore_patterns)
        ]
        if not changed_paths:
            return {}

        fetched = {}

        if self.config.fetch_changed_full:
            for path in changed_paths:
                content = self._fetch_cached(path)
                if content is not None:
                    fetched[path] = content

        if self.config.fetch_related_files and self.config.fetch_related_depth > 0:
            self._ensure_resolvers()
            seeds = []
            for path in changed_paths:
                content = fetched.get(path) or self._fetch_cached(path)
                if content is None:
                    continue
                seeds.append((path, content))
            self._traverse_related(seeds, fetched)

        return fetched

    def _traverse_related(self, seeds, fetched: dict):
        depth_limit = self.config.fetch_related_depth
        current_layer = list(seeds)
        visited = set(path for path, _ in current_layer)

        for _ in range(depth_limit):
            next_layer = []
            for from_path, content in current_layer:
                language = language_for_path(from_path)
                if language is None:
                    continue
                try:
                    specifiers = extract_imports(content, from_path)
                except RuntimeError:
                    raise
                except Exception as exc:
                    print(
                        f"WARNING: tree-sitter parse failed for {from_path} "
                        f"({type(exc).__name__}: {exc}); related imports for this "
                        "file will be skipped."
                    )
                    specifiers = set()
                for specifier in specifiers:
                    resolved = self._resolve_specifier(specifier, from_path)
                    if not resolved or resolved in visited:
                        continue
                    if is_ignored(resolved, self.ignore_patterns):
                        visited.add(resolved)
                        continue
                    resolved_content = self._fetch_cached(resolved)
                    visited.add(resolved)
                    if resolved_content is None:
                        continue
                    fetched[resolved] = resolved_content
                    next_layer.append((resolved, resolved_content))
            if not next_layer:
                break
            current_layer = next_layer


class ContextTooLargeError(RuntimeError):
    pass


CONTEXT_WINDOWS = {
    "claude-sonnet-4-6": 200_000,
    "claude-opus-4-7": 200_000,
    "claude-3-5-sonnet-latest": 200_000,
    "gemini-2.5-pro": 1_048_576,
    "gemini-2.0-flash": 1_048_576,
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
}

_DEFAULT_CONTEXT_WINDOW = 128_000
_SAFETY_FRACTION = 0.8


def estimate_tokens(text: str) -> int:
    return len(text) // 4


def check_context_window(system_prompt: str, user_prompt: str, model_name: str):
    window = CONTEXT_WINDOWS.get(model_name, _DEFAULT_CONTEXT_WINDOW)
    budget = int(window * _SAFETY_FRACTION)
    estimated = estimate_tokens(system_prompt) + estimate_tokens(user_prompt)
    if estimated > budget:
        raise ContextTooLargeError(
            f"context too large: disable AI_FETCH_CHANGED_FULL, lower AI_FETCH_RELATED_DEPTH, "
            f"or reduce the PR scope (estimated {estimated} tokens; budget {budget} for {model_name})"
        )
