"""
Git automation helpers. Uses the system `git` CLI via subprocess so it
relies on whatever auth (SSH key / credential manager) you already have
set up for git on this machine.
"""

import re
import subprocess
from pathlib import Path


class GitOpsError(Exception):
    """Raised when a git step fails, with the captured output attached."""


class DuplicateEntryError(Exception):
    """Raised when one or more queue names in the new block already exist in the target file."""

    def __init__(self, duplicate_names):
        self.duplicate_names = duplicate_names
        names_list = "\n".join(f"  - {n}" for n in duplicate_names)
        super().__init__(
            "The following entries already exist in the target file:\n"
            f"{names_list}\n"
            "Nothing was changed. Tick 'Add anyway' if you really want to add "
            "this block regardless."
        )


def extract_names(block_text):
    """Pull every `name: "..."` value out of a rendered YAML block."""
    return re.findall(r'name:\s*"([^"]+)"', block_text)


def extract_subscription_values(block_text):
    """Pull every quoted topic string out of a block of subscription list items."""
    return re.findall(r'-\s*"([^"]+)"', block_text)


TARGET_QUEUE_MARKER_RE = re.compile(r'^#\s*TARGET_QUEUE:\s*"([^"]+)"\s*$', re.MULTILINE)


def is_subscription_template(template_text):
    """
    A 'subscription-only' template starts with a
    `# TARGET_QUEUE: "SomeAlreadyExistingQueueName"` marker line, followed
    by just the subscription list lines to add under that existing queue -
    as opposed to a normal template that defines a whole new queue entry.
    """
    return template_text.lstrip().startswith("# TARGET_QUEUE:")


def parse_subscription_template(template_text):
    """
    Split a subscription-only template into (target_queue_name, body),
    where body is the raw subscription lines (with placeholders still in).
    """
    m = TARGET_QUEUE_MARKER_RE.search(template_text)
    if not m:
        raise GitOpsError(
            "Subscription template is missing a '# TARGET_QUEUE: \"...\"' "
            "header line as its first line."
        )
    target_queue_name = m.group(1)
    body = template_text[m.end():].strip("\n")
    return target_queue_name, body


REPLACE_SUBSCRIPTIONS_MARKER_RE = re.compile(
    r'^#\s*REPLACE_SUBSCRIPTIONS_OF:\s*"([^"]+)"\s*$', re.MULTILINE
)


def is_replace_subscriptions_template(template_text):
    """
    A 'replace subscriptions' template starts with a
    `# REPLACE_SUBSCRIPTIONS_OF: "SomeAlreadyExistingQueueName"` marker
    line, followed by the FULL new set of subscription lines that should
    REPLACE (not add to) that existing queue's current subscriptions.

    The queue name may itself contain {STORE}/{REGION}/{COUNTRY}
    placeholders (e.g. "SCX_STO_{STORE}_TRANSACTIONAL_CONSUMER_V1_Q"), for
    queues that exist once PER STORE rather than one fixed queue shared by
    all stores - the caller is responsible for substituting those before
    passing the queue name to replace_subscriptions_in_queue.
    """
    return template_text.lstrip().startswith("# REPLACE_SUBSCRIPTIONS_OF:")


def parse_replace_subscriptions_template(template_text):
    """Split a replace-subscriptions template into (target_queue_name,
    body) - body is the raw new subscription lines (placeholders still in)."""
    m = REPLACE_SUBSCRIPTIONS_MARKER_RE.search(template_text)
    if not m:
        raise GitOpsError(
            "Replace-subscriptions template is missing a "
            "'# REPLACE_SUBSCRIPTIONS_OF: \"...\"' header line as its first line."
        )
    target_queue_name = m.group(1)
    body = template_text[m.end():].strip("\n")
    return target_queue_name, body


def is_list_append_template(template_text):
    """
    An 'append to list' template starts with a `# APPEND_TO_LIST` marker
    line, followed by one or more plain list-item lines (e.g.
    `- "#P2P/QUE/SCX_STO_{STORE}_SALES_STOP_UPDATED_V1_Q"`) to insert right
    after the last existing line matching that same pattern, anywhere in
    the file - with no surrounding named queue entry involved (e.g. a flat
    ACL exceptions list).
    """
    return template_text.lstrip().startswith("# APPEND_TO_LIST")


def parse_list_append_template(template_text):
    """Strip the '# APPEND_TO_LIST' marker line and return the rest (the
    list-item line(s) to insert, with placeholders still in)."""
    stripped = template_text.lstrip()
    newline_pos = stripped.find("\n")
    if newline_pos == -1:
        raise GitOpsError(
            "'# APPEND_TO_LIST' template has no content after the marker line."
        )
    body = stripped[newline_pos + 1:].strip("\n")
    if not body:
        raise GitOpsError(
            "'# APPEND_TO_LIST' template has no list-item line after the marker."
        )
    return body


def build_line_anchor_regex(line_template):
    """
    Turn a full list-item line like
    '- "#P2P/QUE/SCX_STO_{STORE}_SALES_STOP_UPDATED_V1_Q"' into a regex
    that matches that same line for ANY store/region/country, so we can
    find every existing line matching this pattern in the file.
    """
    parts = PLACEHOLDER_RE.split(line_template.strip())
    escaped = [re.escape(p) for p in parts]
    pattern = r"[A-Za-z0-9_]+".join(escaped)
    return re.compile(r'^([ \t]*)' + pattern + r'[ \t\r]*$', re.MULTILINE)


def build_line_anchor_regex_with_store_capture(line_template):
    """Like build_line_anchor_regex, but specifically captures the digits
    at the {STORE} placeholder's position, so matches can be sorted/
    compared numerically by store."""
    tokens = re.split(r"(\{[A-Z_]+\})", line_template.strip())
    pattern_parts = []
    for token in tokens:
        if token == "{STORE}":
            pattern_parts.append(r"(\d+)")
        elif PLACEHOLDER_RE.fullmatch(token):
            pattern_parts.append(r"[A-Za-z0-9_]+")
        else:
            pattern_parts.append(re.escape(token))
    pattern = "".join(pattern_parts)
    return re.compile(r'^([ \t]*)' + pattern + r'[ \t\r]*$', re.MULTILINE)


def insert_list_lines_after_last_match(
    file_path, template_body, rendered_body, log=None, sort_by_store=False, new_store=None,
):
    """
    Insert rendered_body (one or more already-rendered list-item lines)
    into the flat list of existing lines matching the same pattern as
    template_body's last line (with placeholders wildcarded). Used for
    flat lists (no named parent entry), e.g. ACL exception lists.

    Default behavior: insert right after the LAST existing matching line.

    sort_by_store: if True, keep the list in numeric store order instead
    - new_store (the store number being added) is compared against every
    existing matching line's own store number, and the new line is
    inserted right before the first line with a BIGGER store number. If
    no bigger one exists (or new_store can't be parsed as a number),
    falls back to the normal "after the last match" behavior above.
    """

    def _log(msg):
        if log:
            log(msg)

    path = Path(file_path)
    if not path.exists():
        raise GitOpsError(f"Target YAML file not found: {file_path}")

    content = read_file_exact(path)
    eol = detect_eol(content)
    if not content.endswith("\n"):
        content += eol

    template_lines = [ln for ln in template_body.strip("\n").splitlines() if ln.strip()]
    if not template_lines:
        raise GitOpsError("Template has no list-item line to match/insert.")
    anchor_line_template = template_lines[-1]

    insertion_index = None
    indent = ""
    match_count = 0

    if sort_by_store and new_store is not None:
        try:
            new_store_int = int(new_store)
        except (TypeError, ValueError):
            new_store_int = None
        if new_store_int is not None:
            store_anchor_regex = build_line_anchor_regex_with_store_capture(anchor_line_template)
            all_matches = list(store_anchor_regex.finditer(content))
            match_count = len(all_matches)
            result = find_next_bigger_store_position(content, store_anchor_regex, new_store_int)
            if result is not None:
                insertion_index, indent_len = result
                indent = " " * indent_len
                _log("Found a bigger existing store number - inserting before it to keep numeric order.")

    if insertion_index is None:
        anchor_regex = build_line_anchor_regex(anchor_line_template)
        matches = list(anchor_regex.finditer(content))
        match_count = len(matches)
        if not matches:
            raise GitOpsError(
                f"Could not find any existing line matching the pattern for "
                f"'{anchor_line_template.strip()}' in the file - nothing to insert after."
            )
        last_match = matches[-1]
        indent = last_match.group(1)
        insertion_index = content.index("\n", last_match.end()) + 1
        _log(f"Found {match_count} existing matching line(s) - inserted after the last one.")

    rendered_lines = [ln.strip() for ln in rendered_body.strip("\n").splitlines() if ln.strip()]
    if not rendered_lines:
        raise GitOpsError("No rendered list-item line(s) to insert.")
    formatted = eol.join(f"{indent}{ln}" for ln in rendered_lines) + eol
    formatted = to_file_eol(formatted, eol)

    new_content = content[:insertion_index] + formatted + content[insertion_index:]
    write_file_exact(path, new_content)


def find_duplicates_multi(repo_path, items):
    """
    Check a batch of items against whatever's already in EACH item's own
    target file (items may point at different files within the same repo).
    Returns the combined, de-duplicated list of names/topics that already
    exist.
    """
    duplicates = []
    seen = set()
    # Cache file contents so we only read each distinct file once.
    file_cache = {}

    for item in items:
        if item.get("type") == "replace_subscriptions":
            # Not an "addition" - it intentionally overwrites whatever is
            # there, so the usual duplicate check doesn't apply here.
            continue

        full_path = Path(repo_path) / item["yaml_relative_path"]
        key = str(full_path)
        if key not in file_cache:
            if full_path.exists():
                existing_content = read_file_exact(full_path)
                file_cache[key] = (
                    set(re.findall(r'name:\s*"([^"]+)"', existing_content)),
                    set(re.findall(r'-\s*"([^"]+)"', existing_content)),
                )
            else:
                file_cache[key] = (set(), set())
        existing_names, existing_topics = file_cache[key]

        if item.get("type") in ("subscription", "list_line"):
            candidates = extract_subscription_values(item["rendered_lines"])
            existing_set = existing_topics
        else:
            candidates = extract_names(item["block_text"])
            existing_set = existing_names

        for c in candidates:
            if c in existing_set and c not in seen:
                duplicates.append(c)
                seen.add(c)
    return duplicates


def run_git(args, cwd, check=True):
    """Run a git command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        raise GitOpsError(
            "Could not run 'git' on this computer - it isn't installed, or "
            "isn't on this Windows account's PATH.\n\n"
            "Fix: install Git for Windows (https://git-scm.com/download/win). "
            "During setup, make sure the option \"Git from the command line "
            "and also from 3rd-party software\" is selected (NOT \"Use Git "
            "from Git Bash only\"). Then close and reopen QTomate.exe."
        )
    except OSError as e:
        raise GitOpsError(
            f"Could not start git in '{cwd}': {e}\n\n"
            "This usually means the repo folder path is invalid, inaccessible, "
            "or (on Windows) too long/deeply nested for this account. Try "
            "cloning the repo somewhere with a shorter path, e.g. C:\\repos\\...,"
            " and update the repo path in QTomate's sidebar."
        )
    if check and result.returncode != 0:
        raise GitOpsError(
            f"git {' '.join(args)} failed:\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
    return result.returncode, result.stdout, result.stderr


def ensure_git_available():
    """
    Preflight check: confirm 'git' itself can be launched at all, before
    doing anything else. Gives a clean, specific error immediately instead
    of a raw Python traceback surfacing from deep inside some later step.
    """
    try:
        subprocess.run(["git", "--version"], capture_output=True, text=True)
    except FileNotFoundError:
        raise GitOpsError(
            "Could not run 'git' on this computer - it isn't installed, or "
            "isn't on this Windows account's PATH.\n\n"
            "Fix: install Git for Windows (https://git-scm.com/download/win). "
            "During setup, make sure the option \"Git from the command line "
            "and also from 3rd-party software\" is selected (NOT \"Use Git "
            "from Git Bash only\"). Then close and reopen QTomate.exe."
        )
    except OSError as e:
        raise GitOpsError(f"Could not run 'git --version' on this computer: {e}")


def ensure_repo_exists(repo_path):
    path = Path(repo_path)
    if not path.exists():
        raise GitOpsError(f"Repo path does not exist: {repo_path}")
    if not (path / ".git").exists():
        raise GitOpsError(f"Not a git repository (no .git folder): {repo_path}")


def has_uncommitted_changes(repo_path):
    _, out, _ = run_git(["status", "--porcelain"], cwd=repo_path)
    return bool(out.strip())


def checkout_base_branch(repo_path, base_branch):
    run_git(["checkout", base_branch], cwd=repo_path)


def pull_latest(repo_path, remote, base_branch):
    run_git(["pull", remote, base_branch], cwd=repo_path)


INVALID_BRANCH_CHARS_RE = re.compile(r'[\s~^:?*\[\\]|\.\.|@\{|//|^-|-$|^\.|\.$|^/|/$')


def create_feature_branch(repo_path, branch_name):
    if INVALID_BRANCH_CHARS_RE.search(branch_name) or not branch_name.strip():
        raise GitOpsError(
            f"'{branch_name}' isn't a valid git branch name (no spaces, and no "
            "~ ^ : ? * [ \\ characters, consecutive dots, or leading/trailing "
            "dashes/dots/slashes). Edit the 'Feature branch name' field and try again."
        )
    # -B creates the branch if it doesn't exist, or resets it if it does.
    run_git(["checkout", "-B", branch_name], cwd=repo_path)


PLACEHOLDER_RE = re.compile(r"\{[A-Z_]+\}")


def detect_eol(content):
    """Return the dominant line ending used in the file."""
    return "\r\n" if "\r\n" in content else "\n"


def to_file_eol(text, eol):
    """Normalize a block of text to use the given line ending style."""
    normalized = text.replace("\r\n", "\n")
    return normalized.replace("\n", eol)


def read_file_exact(path):
    """
    Read a file's text WITHOUT any newline translation, so CRLF vs LF is
    preserved exactly as it is on disk. Path.read_text() always performs
    universal-newline translation (silently turning every \\r\\n into \\n)
    with no way to opt out, which would otherwise rewrite an entire CRLF
    file to LF on every single run of this tool.
    """
    return path.read_bytes().decode("utf-8")


def write_file_exact(path, text):
    """Write text back out WITHOUT any newline translation (see read_file_exact)."""
    path.write_bytes(text.encode("utf-8"))


def _line_indent(text_line):
    """Number of leading spaces/tabs on a line (line should have \\r stripped already)."""
    return len(text_line) - len(text_line.lstrip(" \t"))


def find_block_end(content, start_pos, base_indent_len):
    """
    Starting at start_pos, scan forward and return the position right
    after the LAST actual (non-comment, non-blank) line that is still
    part of this entry.

    Comment lines (and blank lines) are skipped over entirely and never
    count as "still part of the entry" NOR as a stopping boundary by
    themselves - real files are not always consistent about indenting
    trailing divider/header comments correctly (they're sometimes indented
    to match the previous entry's fields by mistake), so indentation alone
    on a comment line is not a reliable signal. Only a genuine (non-comment)
    YAML line at or above this entry's own indentation marks where the next
    unrelated thing starts - and even then, the returned boundary is right
    after the last REAL line of this entry, not at that stopping line,
    so any trailing comments in between are correctly left OUTSIDE this
    entry's block (available to precede whatever is inserted next).
    """
    pos = start_pos
    n = len(content)
    last_data_end = start_pos
    while pos < n:
        nl = content.find("\n", pos)
        line_end = nl if nl != -1 else n
        line = content[pos:line_end].rstrip("\r")
        stripped = line.strip()
        next_pos = line_end + 1 if nl != -1 else n

        if stripped == "" or stripped.startswith("#"):
            # Blank line or comment - never part of the entry's real data,
            # and never itself a stopping point either.
            pos = next_pos
            continue

        if _line_indent(line) <= base_indent_len:
            # Genuine YAML content at or above this entry's own level -
            # this is where the next unrelated thing starts.
            return last_data_end

        # Still genuinely part of this entry's own body.
        last_data_end = next_pos
        pos = next_pos

    return last_data_end


def get_first_entry_name(template_text):
    """
    Return the `name` value of the FIRST top-level entry in a template
    (e.g. the "_DMQ" entry that precedes the "_Q" entry). Used to find
    where a whole new store's block should be inserted BEFORE an
    existing store with a bigger number, when sorting entries by store.
    """
    names = re.findall(r'^- name: "([^"]+)"', template_text, re.MULTILINE)
    return names[0] if names else None


def build_anchor_regex_with_store_capture(name_template):
    """
    Like build_anchor_regex, but specifically captures the digits at the
    {STORE} placeholder's position (other placeholders stay wildcarded,
    uncaptured), so matches can be sorted/compared numerically by store.
    """
    tokens = re.split(r"(\{[A-Z_]+\})", name_template)
    pattern_parts = []
    for token in tokens:
        if token == "{STORE}":
            pattern_parts.append(r"(\d+)")
        elif PLACEHOLDER_RE.fullmatch(token):
            pattern_parts.append(r"[A-Za-z0-9_]+")
        else:
            pattern_parts.append(re.escape(token))
    pattern = "".join(pattern_parts)
    return re.compile(r'^([ \t]*)- name: "' + pattern + r'"[ \t\r]*$', re.MULTILINE)


def find_next_bigger_store_position(content, anchor_regex, new_store_int):
    """
    Among all entries matching anchor_regex (which must capture the store
    number as group 2), find the one with the SMALLEST store number that
    is still bigger than new_store_int, and return (position of the start
    of that entry's line, its indentation length). Returns None if no
    existing entry has a bigger store number (i.e. the new one belongs at
    the end, or there are no existing entries at all).
    """
    candidates = []
    for m in anchor_regex.finditer(content):
        try:
            store_int = int(m.group(2))
        except (ValueError, IndexError):
            continue
        if store_int > new_store_int:
            candidates.append((store_int, m))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0])
    _, match = candidates[0]
    return match.start(), len(match.group(1))


def _splice_block(content, target_pos, block_for_file, eol, blank_line_separator):
    """Insert block_for_file at target_pos, normalizing to exactly one
    blank line (or none) on both sides, per blank_line_separator."""
    before = content[:target_pos].rstrip("\r\n")
    after = content[target_pos:]
    if blank_line_separator:
        return before + eol + eol + block_for_file + eol + eol + after
    return before + eol + block_for_file + eol + after


def get_last_entry_name(template_text):
    """
    Return the `name` value of the LAST top-level entry in a template
    (e.g. the "_Q" entry that follows the "_DMQ" entry). This is used as
    the anchor to find where this queue type's existing entries live.
    """
    names = re.findall(r'^- name: "([^"]+)"', template_text, re.MULTILINE)
    return names[-1] if names else None


def build_anchor_regex(name_template):
    """
    Turn a name like 'SCX_STO_{STORE}_TRANSACTIONAL_CONSUMER_V1_Q' into a
    regex that matches that same entry for ANY store/region/country, so we
    can find every existing entry of this queue type in the file. Allows
    (and captures) any leading indentation, since some files nest their
    queue list under a top-level key (e.g. 'queues:') and others don't.
    """
    parts = PLACEHOLDER_RE.split(name_template)
    escaped = [re.escape(p) for p in parts]
    pattern = r"[A-Za-z0-9_]+".join(escaped)
    return re.compile(r'^([ \t]*)- name: "' + pattern + r'"[ \t\r]*$', re.MULTILINE)


def find_cluster_insertion_index(content, anchor_regex):
    """
    Find the position right after the LAST existing entry of this queue
    type's full body (past all its indented/subscription lines), i.e.
    where a new entry of the same type should be inserted to stay in
    that "cluster", along with that entry's indentation level (so the
    new block can be indented to match). Returns None if no existing
    entry of this type is found.
    """
    matches = list(anchor_regex.finditer(content))
    if not matches:
        return None

    last_match = matches[-1]
    entry_indent_len = len(last_match.group(1))
    end = find_block_end(content, last_match.end(), entry_indent_len)
    return end, entry_indent_len


def insert_block_in_cluster(
    file_path, template_text, block_text, log=None, blank_line_separator=True,
    sort_by_store=False, new_store=None,
):
    """
    Insert block_text into the cluster of existing entries of the same
    queue type (found via template_text's entry name(s), wildcarded
    across store/region/country).

    Default behavior: insert right after the LAST existing entry of this
    type - i.e. at the end of that "cluster" - instead of at the end of
    the whole file. Falls back to appending at the end of the file if no
    existing entry of this queue type is found (e.g. the very first one
    being added).

    sort_by_store: if True, keep the cluster in numeric store order
    instead of always appending at the end - new_store (the store number
    being added, as a string or int) is compared against every existing
    entry's own store number, and the block is inserted right before the
    first existing entry with a BIGGER store number. If no bigger one
    exists (or new_store can't be parsed as a number), falls back to the
    normal "after the last entry" behavior above.

    blank_line_separator: whether to put a blank line before/after the
    new block. Most files use blank lines between entries (default True);
    set to False for files that pack entries with no gaps.
    """

    def _log(msg):
        if log:
            log(msg)

    path = Path(file_path)
    if not path.exists():
        raise GitOpsError(f"Target YAML file not found: {file_path}")

    content = read_file_exact(path)
    eol = detect_eol(content)
    if not content.endswith("\n"):
        content += eol

    insertion_index = None
    entry_indent_len = 0
    insert_before = False

    if sort_by_store and new_store is not None:
        try:
            new_store_int = int(new_store)
        except (TypeError, ValueError):
            new_store_int = None
        first_name = get_first_entry_name(template_text)
        if new_store_int is not None and first_name:
            store_anchor_regex = build_anchor_regex_with_store_capture(first_name)
            result = find_next_bigger_store_position(content, store_anchor_regex, new_store_int)
            if result is not None:
                insertion_index, entry_indent_len = result
                insert_before = True

    if insertion_index is None:
        # Either sort_by_store is off, no bigger store exists yet (this
        # one belongs at the end), or the store number wasn't parseable -
        # fall back to the normal "after the last entry" behavior.
        last_name = get_last_entry_name(template_text)
        if last_name:
            anchor_regex = build_anchor_regex(last_name)
            result = find_cluster_insertion_index(content, anchor_regex)
            if result is not None:
                insertion_index, entry_indent_len = result

    # Reindent every non-blank line of the new block to match the base
    # indentation the file actually uses for this list (e.g. 0 if entries
    # sit at column 0, or 2 if nested under a 'queues:' key, etc). The
    # template's own internal (relative) indentation is preserved.
    base_prefix = " " * entry_indent_len
    block_lines = block_text.strip("\n").splitlines()
    reindented = "\n".join((base_prefix + ln) if ln.strip() else ln for ln in block_lines)
    block_for_file = to_file_eol(reindented, eol)

    if insertion_index is None:
        _log(
            "No existing entries of this queue type found in the file - "
            "appending to the end of the file instead of a cluster."
        )
        if not content.endswith(eol):
            content += eol
        new_content = content + block_for_file + eol
    elif insert_before:
        _log(f"Found a bigger existing store number - inserting before it to keep numeric order.")
        new_content = _splice_block(content, insertion_index, block_for_file, eol, blank_line_separator)
    else:
        _log("Found the matching queue cluster - inserting after its last entry.")
        new_content = _splice_block(content, insertion_index, block_for_file, eol, blank_line_separator)

    write_file_exact(path, new_content)


def _find_sorted_subscription_insertions(
    entry_text, entry_offset, template_body, new_lines, new_store_int,
):
    """
    Work out WHERE (absolute file offsets) the new subscription group must
    go so the queue's subscriptions stay in ascending store order.

    A "group" is everything the template renders for one store, e.g.
        #
        - ".../full/.../STO/222"
        - ".../update/.../STO/222"
    The group is always moved as ONE unit - never split up.

    Each {STORE} line of the template becomes a regex matching that same
    topic for ANY store (capturing the store number). The next bigger
    store is the existing store with the smallest number above the new
    one; the new group goes right before that store's group (including
    that group's own leading '#' separator line, so separators stay
    one-per-group). If no bigger store exists, the group is added after
    the last existing store line.

    Returns [(insertion_offset, indent, [lines])] or None when nothing in
    the queue matched (caller falls back to plain appending).
    """
    template_lines = [ln.strip() for ln in template_body.strip("\n").splitlines() if ln.strip()]
    if len(template_lines) != len(new_lines):
        return None
    store_idx = [i for i, t in enumerate(template_lines) if "{STORE}" in t]
    if not store_idx:
        return None
    first = store_idx[0]
    lead = new_lines[:first]      # separator/comment lines before the first topic, e.g. "#"
    core = new_lines[first:]      # the topic lines themselves

    hits = []  # (line_start, line_end_incl_newline, store_int, indent)
    for i in store_idx:
        rx = build_line_anchor_regex_with_store_capture(template_lines[i])
        for m in rx.finditer(entry_text):
            try:
                store_int = int(m.group(2))
            except (ValueError, IndexError):
                continue
            line_end = entry_text.find("\n", m.end())
            end = line_end + 1 if line_end != -1 else len(entry_text)
            hits.append((m.start(), end, store_int, m.group(1)))
    if not hits:
        return None

    bigger = [h for h in hits if h[2] > new_store_int]
    if not bigger:
        # Belongs at the end: after the last existing topic line.
        last = max(hits, key=lambda h: h[1])
        return [(entry_offset + last[1], last[3], lead + core)]

    next_store = min(h[2] for h in bigger)
    anchor = min((h for h in bigger if h[2] == next_store), key=lambda h: h[0])
    anchor_start, indent = anchor[0], anchor[3]

    if lead:
        before_lines = entry_text[:anchor_start].split("\n")[:-1]
        if len(before_lines) >= len(lead) and \
                [ln.strip() for ln in before_lines[-len(lead):]] == [ln.strip() for ln in lead]:
            # That group has its own separator line(s) - go in front of them
            # and bring our own separator along, so every group keeps one.
            pos = sum(len(ln) + 1 for ln in before_lines[:-len(lead)])
            return [(entry_offset + pos, indent, lead + core)]
        # First group in the list (no separator above it): put ours first
        # and add the separator after it instead.
        return [(entry_offset + anchor_start, indent, core + lead)]

    return [(entry_offset + anchor_start, indent, core)]


def insert_subscriptions_into_queue(
    file_path, target_queue_name, new_lines_block, log=None,
    sort_by_store=False, new_store=None, template_body=None,
):
    """
    Insert new subscription list items (new_lines_block - one or more
    already-rendered `- "topic"` lines) into the subscriptions list of an
    ALREADY EXISTING queue entry named target_queue_name.

    Default behavior: insert after the LAST existing subscription.

    sort_by_store: if True (and new_store + template_body are given), keep
    the queue's subscriptions in ascending numeric store order instead -
    the new lines are inserted before the first existing subscription
    with a BIGGER store number (see _find_sorted_subscription_insertions).
    Falls back to the default behavior if nothing comparable is found.

    Reindents the new lines to match whatever indentation the file
    actually uses for that entry's subscription items (or, if the queue
    currently has no subscriptions, the indentation implied by its
    'subscriptions:' key).
    """

    def _log(msg):
        if log:
            log(msg)

    path = Path(file_path)
    if not path.exists():
        raise GitOpsError(f"Target YAML file not found: {file_path}")

    content = read_file_exact(path)
    eol = detect_eol(content)
    if not content.endswith("\n"):
        content += eol

    name_regex = re.compile(
        r'^([ \t]*)- name: "' + re.escape(target_queue_name) + r'"[ \t\r]*$', re.MULTILINE
    )
    matches = list(name_regex.finditer(content))
    if not matches:
        raise GitOpsError(
            f"Target queue '{target_queue_name}' was not found in the file - "
            "it must already exist before subscriptions can be added to it."
        )
    match = matches[0]
    entry_indent_len = len(match.group(1))

    entry_end = find_block_end(content, match.end(), entry_indent_len)
    entry_text = content[match.start():entry_end]

    new_lines = [ln.strip() for ln in new_lines_block.strip("\n").splitlines() if ln.strip()]
    if not new_lines:
        raise GitOpsError("No subscription lines to add - the rendered block was empty.")

    item_regex = re.compile(r'^([ \t]*)-\s*"[^"]*"[ \t\r]*$', re.MULTILINE)
    item_matches = list(item_regex.finditer(entry_text))

    sorted_insertions = None
    if sort_by_store and new_store is not None and template_body and item_matches:
        try:
            new_store_int = int(new_store)
        except (TypeError, ValueError):
            new_store_int = None
        if new_store_int is not None:
            sorted_insertions = _find_sorted_subscription_insertions(
                entry_text, match.start(), template_body, new_lines, new_store_int,
            )

    if sorted_insertions:
        _log("Keeping subscriptions in ascending store order - inserting at the sorted position.")
        # Apply back-to-front so earlier offsets stay valid.
        for pos, indent, lines in sorted(sorted_insertions, key=lambda t: t[0], reverse=True):
            formatted = to_file_eol(eol.join(f"{indent}{ln}" for ln in lines) + eol, eol)
            content = content[:pos] + formatted + content[pos:]
        write_file_exact(path, content)
        return

    if item_matches:
        last_item = item_matches[-1]
        indent = last_item.group(1)
        abs_line_end = match.start() + last_item.end()
        insertion_index = content.index("\n", abs_line_end) + 1
        _log(
            f"Found {len(item_matches)} existing subscription(s) under "
            f"'{target_queue_name}' - inserting after the last one."
        )
    else:
        # No existing subscription items yet - anchor after the
        # 'subscriptions:' key itself (handles both 'subscriptions:' and
        # the empty-list shorthand 'subscriptions: []').
        subs_key_regex = re.compile(
            r'^([ \t]*)subscriptions:[ \t]*(\[\s*\])?[ \t\r]*$', re.MULTILINE
        )
        subs_match = subs_key_regex.search(entry_text)
        if not subs_match:
            raise GitOpsError(
                f"Could not find a 'subscriptions:' key under '{target_queue_name}' "
                "to insert into."
            )
        indent = subs_match.group(1) + "  "

        if subs_match.group(2):
            # Rewrite "subscriptions: []" -> "subscriptions:" so items can follow.
            key_line_start = match.start() + subs_match.start()
            key_line_end = match.start() + subs_match.end()
            content = (
                content[:key_line_start]
                + subs_match.group(1) + "subscriptions:"
                + content[key_line_end:]
            )
            insertion_index = content.index("\n", key_line_start) + 1
        else:
            abs_line_end = match.start() + subs_match.end()
            insertion_index = content.index("\n", abs_line_end) + 1

        _log(f"No existing subscriptions under '{target_queue_name}' yet - adding the first ones.")

    formatted = eol.join(f"{indent}{ln}" for ln in new_lines) + eol
    formatted = to_file_eol(formatted, eol)

    new_content = content[:insertion_index] + formatted + content[insertion_index:]
    write_file_exact(path, new_content)


def replace_subscriptions_in_queue(file_path, target_queue_name, new_lines_block, log=None):
    """
    REPLACE the entire subscriptions list of an ALREADY EXISTING queue
    entry named target_queue_name with new_lines_block (one or more
    already-rendered `- "topic"` lines) - removing whatever subscriptions
    it currently has (items and any comments among them), rather than
    adding to them like insert_subscriptions_into_queue does.

    Assumes 'subscriptions:' is the LAST field of the queue entry, which
    is true for every template this tool works with - everything from
    right after that key down to the end of the entry is treated as the
    list to replace.
    """

    def _log(msg):
        if log:
            log(msg)

    path = Path(file_path)
    if not path.exists():
        raise GitOpsError(f"Target YAML file not found: {file_path}")

    content = read_file_exact(path)
    eol = detect_eol(content)
    if not content.endswith("\n"):
        content += eol

    name_regex = re.compile(
        r'^([ \t]*)- name: "' + re.escape(target_queue_name) + r'"[ \t\r]*$', re.MULTILINE
    )
    matches = list(name_regex.finditer(content))
    if not matches:
        raise GitOpsError(
            f"Target queue '{target_queue_name}' was not found in the file - "
            "it must already exist before its subscriptions can be replaced."
        )
    match = matches[0]
    entry_indent_len = len(match.group(1))
    entry_end = find_block_end(content, match.end(), entry_indent_len)
    entry_text = content[match.start():entry_end]

    subs_key_regex = re.compile(
        r'^([ \t]*)subscriptions:[ \t]*(\[\s*\])?[ \t\r]*$', re.MULTILINE
    )
    subs_match = subs_key_regex.search(entry_text)
    if not subs_match:
        raise GitOpsError(
            f"Could not find a 'subscriptions:' key under '{target_queue_name}' to replace."
        )

    new_lines = [ln.strip() for ln in new_lines_block.strip("\n").splitlines() if ln.strip()]
    if not new_lines:
        raise GitOpsError("No subscription lines to replace with - the rendered block was empty.")

    # Reuse whatever indentation the file already uses for this entry's
    # items if any currently exist, otherwise fall back to the
    # subscriptions: key's own indent + 2 spaces.
    item_regex = re.compile(r'^([ \t]*)-\s*"[^"]*"[ \t\r]*$', re.MULTILINE)
    existing_item_match = item_regex.search(entry_text[subs_match.end():])
    indent = existing_item_match.group(1) if existing_item_match else subs_match.group(1) + "  "

    formatted = eol.join(f"{indent}{ln}" for ln in new_lines) + eol
    formatted = to_file_eol(formatted, eol)

    key_line_start = match.start() + subs_match.start()
    key_line_end = match.start() + subs_match.end()

    if subs_match.group(2) is not None:
        # Was "subscriptions: []" (empty-list shorthand) - nothing to
        # strip, just rewrite the key line and put the new items after it.
        key_only = subs_match.group(1) + "subscriptions:"
        new_content = content[:key_line_start] + key_only + eol + formatted + content[entry_end:]
        removed_count = 0
    else:
        replace_from = content.index("\n", key_line_end) + 1
        removed_count = len(item_regex.findall(content[replace_from:entry_end]))
        new_content = content[:replace_from] + formatted + content[entry_end:]

    write_file_exact(path, new_content)
    _log(
        f"Replaced {removed_count} existing subscription(s) under "
        f"'{target_queue_name}' with {len(new_lines)} new one(s)."
    )


def git_add(repo_path, relative_file_paths):
    """relative_file_paths may be a single path string or a list of paths."""
    if isinstance(relative_file_paths, str):
        relative_file_paths = [relative_file_paths]
    run_git(["add"] + list(relative_file_paths), cwd=repo_path)


def git_commit(repo_path, message):
    run_git(["commit", "-m", message], cwd=repo_path)


def git_push(repo_path, remote, branch_name):
    returncode, out, err = run_git(["push", "-u", remote, branch_name], cwd=repo_path, check=False)
    if returncode != 0:
        if "non-fast-forward" in err or "[rejected]" in err or "fetch first" in err:
            raise GitOpsError(
                f"Push to '{remote}/{branch_name}' was rejected because a branch with "
                "that name already exists on the remote with commits your local branch "
                "doesn't have - most likely from an earlier run of this tool for the "
                "same store/region (its PR may still be open).\n\n"
                "Fix: either change the 'Feature branch name' field to something new "
                "before running Execute again, or merge/close the existing "
                f"'{branch_name}' branch on GitHub first.\n\n"
                f"Git said:\n{err}"
            )
        raise GitOpsError(f"git push failed:\nstdout: {out}\nstderr: {err}")


def run_full_workflow(
    repo_path,
    remote,
    base_branch,
    branch_name,
    items,
    commit_message,
    log,
    force=False,
):
    """
    Runs the whole flow end-to-end for one or more selections THAT ALL
    LIVE IN THE SAME REPO, combined into a single branch/commit/push
    (one PR) - even if they touch different YAML files within that repo.

    `items` is a list of dicts. Each item must include its own
    "yaml_relative_path" (items in one call may point at different files
    within this same repo), and is one of:
      - a full new-queue item: {"type": "queue", "yaml_relative_path": ..., "template_text": ..., "block_text": ...}
      - a subscription-only item: {"type": "subscription", "yaml_relative_path": ..., "target_queue_name": ..., "rendered_lines": ...}

    `log` is a callable(str) used to report progress back to the caller
    (e.g. st.write in the Streamlit app).

    Raises DuplicateEntryError (before anything is written) if any name/
    topic across all items already exists in its target file, unless
    force=True.
    """
    if not items:
        raise GitOpsError("No queue selections were provided.")

    ensure_git_available()
    ensure_repo_exists(repo_path)

    log("Checking working tree is clean...")
    if has_uncommitted_changes(repo_path):
        raise GitOpsError(
            "The repo has uncommitted local changes. Please commit, stash, "
            "or discard them before running this tool."
        )

    log(f"Checking out base branch '{base_branch}'...")
    checkout_base_branch(repo_path, base_branch)

    log(f"Pulling latest '{base_branch}' from '{remote}'...")
    pull_latest(repo_path, remote, base_branch)

    log("Checking for duplicate entries...")
    duplicates = find_duplicates_multi(repo_path, items)
    if duplicates and not force:
        raise DuplicateEntryError(duplicates)
    if duplicates and force:
        log(f"Warning: proceeding anyway despite existing entries: {', '.join(duplicates)}")

    log(f"Creating/switching to feature branch '{branch_name}'...")
    create_feature_branch(repo_path, branch_name)

    touched_files = []
    for item in items:
        full_yaml_path = Path(repo_path) / item["yaml_relative_path"]
        if item["yaml_relative_path"] not in touched_files:
            touched_files.append(item["yaml_relative_path"])

        if item.get("type") == "subscription":
            log(f"Adding subscriptions into '{item['target_queue_name']}' ({item['yaml_relative_path']})...")
            insert_subscriptions_into_queue(
                full_yaml_path, item["target_queue_name"], item["rendered_lines"], log=log,
                sort_by_store=item.get("sort_by_store", False),
                new_store=item.get("new_store"),
                template_body=item.get("template_body"),
            )
        elif item.get("type") == "replace_subscriptions":
            log(f"Replacing subscriptions of '{item['target_queue_name']}' ({item['yaml_relative_path']})...")
            replace_subscriptions_in_queue(
                full_yaml_path, item["target_queue_name"], item["rendered_lines"], log=log
            )
        elif item.get("type") == "list_line":
            log(f"Adding list line(s) into '{item['yaml_relative_path']}'...")
            insert_list_lines_after_last_match(
                full_yaml_path, item["template_body"], item["rendered_lines"], log=log,
                sort_by_store=item.get("sort_by_store", False),
                new_store=item.get("new_store"),
            )
        else:
            log(f"Inserting new block into '{item['yaml_relative_path']}'...")
            insert_block_in_cluster(
                full_yaml_path, item["template_text"], item["block_text"], log=log,
                blank_line_separator=item.get("blank_line_separator", True),
                sort_by_store=item.get("sort_by_store", False),
                new_store=item.get("new_store"),
            )

    log("Staging changes...")
    git_add(repo_path, touched_files)

    log("Committing...")
    git_commit(repo_path, commit_message)

    log(f"Pushing branch '{branch_name}' to '{remote}'...")
    git_push(repo_path, remote, branch_name)

    log("Done. Branch pushed - go to GitHub to open the pull request.")